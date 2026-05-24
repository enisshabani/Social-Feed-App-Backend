import re

from sqlalchemy.orm import Session

from app.models.hashtag import ContentHashtag, Hashtag


def extract_hashtags(content: str) -> list[str]:
    if not content:
        return []
    tags = re.findall(r"#(\w+)", content)
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        lower = tag.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result


def get_or_create_hashtag(name: str, db: Session, tenant_id: str) -> Hashtag:
    hashtag = db.query(Hashtag).filter(Hashtag.name == name).first()
    if not hashtag:
        hashtag = Hashtag(name=name, mention_count=0, tenant_id=tenant_id)
        db.add(hashtag)
        db.flush()
    hashtag.mention_count += 1
    return hashtag


def link_hashtags_to_post(
    post_id: int,
    hashtag_names: list[str],
    db: Session,
    tenant_id: str,
) -> None:
    for name in hashtag_names:
        hashtag = get_or_create_hashtag(name, db, tenant_id)
        link = ContentHashtag(
            hashtag_id=hashtag.id,
            post_id=post_id,
            tenant_id=tenant_id,
        )
        db.add(link)
    db.commit()
