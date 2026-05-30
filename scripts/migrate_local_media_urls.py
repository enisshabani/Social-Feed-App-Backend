"""
Convert legacy local media/profile URLs to a public backend origin where possible.

Usage:
  PUBLIC_BACKEND_URL=https://api.example.com python scripts/migrate_local_media_urls.py
  PUBLIC_BACKEND_URL=https://api.example.com python scripts/migrate_local_media_urls.py --dry-run
  PUBLIC_BACKEND_URL=https://api.example.com python scripts/migrate_local_media_urls.py --clear-localhost

Only /uploads/... paths can be made public by prefixing PUBLIC_BACKEND_URL.
localhost URLs outside /uploads are reported because other users cannot access them.
"""

from __future__ import annotations

import argparse
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.post import Media, PostAttachment
from app.models.user import User

LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


def normalize_public_root(value: str) -> str:
    return value.rstrip("/").removesuffix("/api/v1")


def migrate_url(value: str | None, public_root: str, clear_localhost: bool) -> tuple[str | None, str]:
    if not value:
        return value, "empty"

    if value.startswith("/uploads/"):
        return f"{public_root}{value}", "updated"

    try:
        parsed = urlparse(value)
    except ValueError:
        return value, "invalid"

    if parsed.hostname in LOCAL_HOSTS:
        if parsed.path.startswith("/uploads/"):
            suffix = parsed.path
            if parsed.query:
                suffix = f"{suffix}?{parsed.query}"
            return f"{public_root}{suffix}", "updated"
        if clear_localhost:
            return None, "cleared"
        return value, "localhost_unmigrated"

    return value, "unchanged"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clear-localhost", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.PUBLIC_BACKEND_URL:
        raise SystemExit("PUBLIC_BACKEND_URL is required.")

    public_root = normalize_public_root(settings.PUBLIC_BACKEND_URL)
    db = SessionLocal()
    stats: dict[str, int] = {}

    def record(status: str) -> None:
        stats[status] = stats.get(status, 0) + 1

    try:
        for user in db.query(User).all():
            for field in ("avatar_url", "cover_url"):
                next_value, status = migrate_url(getattr(user, field), public_root, args.clear_localhost)
                record(f"users.{field}.{status}")
                if next_value != getattr(user, field):
                    setattr(user, field, next_value)

        for media in db.query(Media).all():
            next_value, status = migrate_url(media.url, public_root, args.clear_localhost)
            record(f"media.url.{status}")
            if next_value != media.url:
                media.url = next_value or ""

        for attachment in db.query(PostAttachment).all():
            next_value, status = migrate_url(attachment.file_url, public_root, args.clear_localhost)
            record(f"post_attachments.file_url.{status}")
            if next_value != attachment.file_url:
                attachment.file_url = next_value or ""

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for key in sorted(stats):
        print(f"{key}: {stats[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
