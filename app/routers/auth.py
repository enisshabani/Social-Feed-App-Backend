"""
KaPak - Authentication Router
Endpoints: register, login, refresh token, me.
"""

import base64
import io
import json
import random
import re
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
import qrcode
from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from google.auth.transport import requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.email import send_reset_password_email
from app.core.middleware import normalize_tenant_id
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password, verify_token
from app.models.user import User
from app.schemas.user import (
    ForgotPasswordRequest,
    LoginResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    Token,
    TwoFactorEnableResponse,
    TwoFactorLoginRequest,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    UserCreate,
    UserResponse,
)

router = APIRouter()

# --- VARIABLAT PËR KUFIZIMIN KUNDËR BRUTE FORCE ---
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
RESET_TOKENS = {}
TRUSTED_DEVICE_TOKEN_EXPIRE_DAYS = 30
TWO_FACTOR_ISSUER = "KaPak"

def _user_query(db: Session):
    return db.query(User).execution_options(skip_tenant_filter=True)


def _tenant_user_query(db: Session, tenant_id: str):
    return _user_query(db).filter(User.tenant_id == normalize_tenant_id(tenant_id))


def _global_user_by_email(db: Session, email: str) -> Optional[User]:
    return _user_query(db).filter(User.email == email).first()


def _global_user_by_username(db: Session, username: str) -> Optional[User]:
    return _user_query(db).filter(User.username == username).first()


def _load_backup_codes(user: User) -> list[str]:
    if not user.backup_codes:
        return []

    try:
        codes = json.loads(user.backup_codes)
        if isinstance(codes, list):
            return [str(code) for code in codes]
    except json.JSONDecodeError:
        pass

    return [code.strip() for code in user.backup_codes.splitlines() if code.strip()]


def _normalize_2fa_code(code: str) -> str:
    return code.strip().replace(" ", "").replace("-", "")


def _generate_backup_codes(count: int = 8) -> list[str]:
    alphabet = string.ascii_uppercase + string.digits
    return [
        "".join(random.choices(alphabet, k=10))
        for _ in range(count)
    ]


def _verify_totp_code(user: User, code: str) -> bool:
    if not user.two_factor_secret:
        return False

    try:
        totp = pyotp.TOTP(user.two_factor_secret)
        return bool(totp.verify(_normalize_2fa_code(code), valid_window=1))
    except Exception:
        return False


def _verify_two_factor_code(user: User, code: str, *, consume_backup_code: bool, db: Session) -> bool:
    normalized_code = _normalize_2fa_code(code)
    if _verify_totp_code(user, normalized_code):
        return True

    backup_codes = _load_backup_codes(user)
    if normalized_code not in backup_codes:
        return False

    if consume_backup_code:
        backup_codes.remove(normalized_code)
        user.backup_codes = json.dumps(backup_codes) if backup_codes else None
        db.commit()

    return True


def _issue_trusted_device_token(user: User) -> str:
    return create_access_token(
        data={"sub": str(user.id), "type": "trusted_device"},
        expires_delta=timedelta(days=TRUSTED_DEVICE_TOKEN_EXPIRE_DAYS),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
):
    """
    Register a new user account.

    - **username**: 3-50 chars, alphanumeric + underscore only
    - **email**: valid email address
    - **password**: minimum 6 characters
    """
    tenant_id = normalize_tenant_id(x_tenant_id or user_data.tenant_id)

    # Check if username already exists in this tenant
    existing_user = _tenant_user_query(db, tenant_id).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Check if email already exists in this tenant
    existing_email = _tenant_user_query(db, tenant_id).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        display_name=user_data.display_name or user_data.username,
        tenant_id=tenant_id,
        is_verified=True,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    trusted_device_token: Optional[str] = Form(None),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
):
    """
    Login with username and password.
    Returns a JWT access token.
    """

    # 1. Kontrollo nëse përdoruesi (ose IP) është bllokuar
    client_ip = request.client.host if request.client else "unknown"
    tenant_id = normalize_tenant_id(x_tenant_id)
    lock_key = f"{tenant_id}_{form_data.username}_{client_ip}"

    if lock_key in LOGIN_ATTEMPTS:
        attempt_data = LOGIN_ATTEMPTS[lock_key]
        if attempt_data["locked_until"] and attempt_data["locked_until"] > datetime.now(timezone.utc):
            remaining_time = (attempt_data["locked_until"] - datetime.now(timezone.utc)).total_seconds() // 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Llogaria juaj është bllokuar përkohësisht. Ju lutem provoni pas {int(remaining_time)} minutash."
            )

    # Find user by username or email
    user = _tenant_user_query(db, tenant_id).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        # 2. Regjistro provën e dështuar
        if lock_key not in LOGIN_ATTEMPTS:
            LOGIN_ATTEMPTS[lock_key] = {"attempts": 0, "locked_until": None}

        LOGIN_ATTEMPTS[lock_key]["attempts"] += 1

        # Bllokoje nëse kanë kaluar MAX_ATTEMPTS
        if LOGIN_ATTEMPTS[lock_key]["attempts"] >= MAX_ATTEMPTS:
            LOGIN_ATTEMPTS[lock_key]["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Shumë prova të dështuara! Jeni bllokuar për {LOCKOUT_MINUTES} minuta."
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Kredenciale të gabuara. Keni edhe {MAX_ATTEMPTS - LOGIN_ATTEMPTS[lock_key]['attempts']} prova.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Nëse login është me sukses, fshi historikun e dështimeve
    if lock_key in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[lock_key]

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Check 2FA
    if user.two_factor_enabled:
        # Check if trusted device
        is_trusted = False
        if trusted_device_token:
            try:
                payload = verify_token(trusted_device_token)
                if payload.get("type") == "trusted_device" and payload.get("sub") == str(user.id):
                    is_trusted = True
            except Exception:
                pass

        if not is_trusted:
            temp_token = create_access_token(
                data={"sub": str(user.id), "is_2fa_temp": True},
                expires_delta=timedelta(minutes=5)
            )
            return {"requires_2fa": True, "temp_token": temp_token}

    # Create access token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
        }
    )
    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
        }
    )

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/login/2fa", response_model=LoginResponse)
def login_with_2fa(payload: TwoFactorLoginRequest, db: Session = Depends(get_db)):
    """
    Complete login after the user has entered a 2FA code.
    """
    try:
        temp_payload = verify_token(payload.temp_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Temp token i pavlefshëm ose i skaduar.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not temp_payload.get("is_2fa_temp"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Temp token i pavlefshëm.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = temp_payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Temp token i pavlefshëm.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = _user_query(db).filter(User.id == int(user_id)).first()
    if not user or not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Përdoruesi nuk është gati për 2FA.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not _verify_two_factor_code(user, payload.code, consume_backup_code=True, db=db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kodi 2FA është i pavlefshëm.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
        }
    )
    refresh_token = create_refresh_token(
        data={
            "sub": str(user.id),
        }
    )

    response_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

    if payload.remember_device:
        response_data["trusted_device_token"] = _issue_trusted_device_token(user)

    return response_data


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.
    Requires a valid JWT token.
    """
    return current_user


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start 2FA setup by generating a TOTP secret and QR code.
    The secret is only active for login after /2fa/enable succeeds.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA është tashmë i aktivizuar.",
        )

    secret = pyotp.random_base32()
    current_user.two_factor_secret = secret
    db.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name=TWO_FACTOR_ISSUER,
    )

    qr_image = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    qr_code_url = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"

    return {"secret": secret, "qr_code_url": qr_code_url}


@router.post("/2fa/enable", response_model=TwoFactorEnableResponse)
def enable_2fa(
    payload: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enable 2FA after confirming the current TOTP code from the setup secret.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA është tashmë i aktivizuar.",
        )

    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filloni konfigurimin e 2FA para aktivizimit.",
        )

    if not _verify_totp_code(current_user, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kodi 2FA është i pavlefshëm.",
        )

    backup_codes = _generate_backup_codes()
    current_user.two_factor_enabled = True
    current_user.backup_codes = json.dumps(backup_codes)
    db.commit()

    return {
        "message": "2FA u aktivizua me sukses.",
        "backup_codes": backup_codes,
    }


@router.post("/2fa/disable")
def disable_2fa(
    payload: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disable 2FA after verifying an authenticator or recovery code.
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA nuk është i aktivizuar.",
        )

    if not _verify_two_factor_code(current_user, payload.code, consume_backup_code=False, db=db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kodi 2FA është i pavlefshëm.",
        )

    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = None
    db.commit()

    return {"message": "2FA u çaktivizua me sukses."}


@router.post("/2fa/recovery-codes", response_model=TwoFactorEnableResponse)
def regenerate_recovery_codes(
    payload: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Regenerate recovery codes after verifying the current authenticator code.
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA nuk është i aktivizuar.",
        )

    if not _verify_totp_code(current_user, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kodi 2FA është i pavlefshëm.",
        )

    backup_codes = _generate_backup_codes()
    current_user.backup_codes = json.dumps(backup_codes)
    db.commit()

    return {
        "message": "Kodet e rikuperimit u gjeneruan me sukses.",
        "backup_codes": backup_codes,
    }


# Projekti ynë në Firebase
FIREBASE_PROJECT_ID = "kapak-3af75"

class GoogleAuthRequest(BaseModel):
    token: str
    tenant_id: str = "default"
    trusted_device_token: Optional[str] = None

@router.post("/google")
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Identifikimi me Google (Nga Firebase). Nëse përdoruesi nuk ekziston, krijohet një i ri.
    Nëse ekziston, thjesht i kthehet JWT token i login.
    """
    try:
        tenant_id = normalize_tenant_id(payload.tenant_id)
        print("[GOOGLE AUTH] Starting authentication with token...")

        # 1. Verifikojmë tokenin i cili vjen nga Frontend (Firebase ID Token)
        idinfo = id_token.verify_firebase_token(
            payload.token,
            requests.Request(),
            audience=FIREBASE_PROJECT_ID,
            clock_skew_in_seconds=300
        )

        google_email = idinfo.get('email', '')
        google_name = idinfo.get('name', '')
        google_avatar = idinfo.get('picture', '')

        print(f"[GOOGLE AUTH] Token verified. Email: {google_email}, Name: {google_name}")

        if not google_email:
            raise ValueError("Google token nuk përmban email")

        # 2. Kontrollojmë nëse e kemi këtë email në db tonë.
        # The current production database still has global unique indexes on email/username,
        # so social auth must reuse an existing global account instead of failing insert.
        user = _tenant_user_query(db, tenant_id).filter(User.email == google_email).first()
        if not user:
            user = _global_user_by_email(db, google_email)

        if not user:
            print("[GOOGLE AUTH] Përdoruesi nuk ekziston. Duke e krijuar...")

            # 3. Nëse NUK është ky email asnjëherë te ne, regjistroje automatikisht!
            base_username = google_email.split('@')[0]
            base_username = base_username[:40]
            base_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username)

            existing_user = _tenant_user_query(db, tenant_id).filter(User.username == base_username).first()
            if not existing_user:
                existing_user = _global_user_by_username(db, base_username)
            if existing_user:
                base_username = f"{base_username}_{str(uuid.uuid4())[:4]}"

            print(f"[GOOGLE AUTH] Përpiqem të krijohet përdorues me username: {base_username}")

            user = User(
                username=base_username,
                email=google_email,
                hashed_password=hash_password(str(uuid.uuid4())),
                display_name=google_name or base_username,
                avatar_url=google_avatar,
                is_verified=True,
                tenant_id=tenant_id
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = _tenant_user_query(db, tenant_id).filter(User.email == google_email).first()
                if not user:
                    user = _global_user_by_email(db, google_email)
                if not user:
                    raise
            db.refresh(user)

            print(f"[GOOGLE AUTH] Përdoruesi u krijua me ID: {user.id}")
        else:
            print(f"[GOOGLE AUTH] Përdoruesi ekziston me ID: {user.id}")
            if not user.is_active:
                print(f"[GOOGLE AUTH] Llogaria requires reactivation. Reactivating user ID: {user.id}")
                user.is_active = True
                db.commit()
            if google_avatar and not user.avatar_url:
                user.avatar_url = google_avatar
                db.commit()

        # 4. Krijoni JWT token
        if user.two_factor_enabled:
            is_trusted = False
            if payload.trusted_device_token:
                try:
                    tok_payload = verify_token(payload.trusted_device_token)
                    if tok_payload.get("type") == "trusted_device" and tok_payload.get("sub") == str(user.id):
                        is_trusted = True
                except Exception:
                    pass

            if not is_trusted:
                temp_token = create_access_token(
                    data={"sub": str(user.id), "is_2fa_temp": True},
                    expires_delta=timedelta(minutes=5)
                )
                return {"requires_2fa": True, "temp_token": temp_token}

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "tenant_id": user.tenant_id,
            }
        )
        refresh_token = create_refresh_token(
            data={
                "sub": str(user.id),
            }
        )

        print("[GOOGLE AUTH] Token u gjenera me sukses")
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    except ValueError as e:
        print(f"[GOOGLE AUTH ERROR] ValueError: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Validimi me Google dështoi: {str(e)}",
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[GOOGLE AUTH ERROR] Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gabim i brendshëm: {str(e)}",
        )

class GithubAuthRequest(BaseModel):
    token: str
    tenant_id: str = "default"
    trusted_device_token: Optional[str] = None

@router.post("/github")
def github_auth(payload: GithubAuthRequest, db: Session = Depends(get_db)):
    """
    Identifikimi me GitHub (Nga Firebase). Nëse përdoruesi nuk ekziston, krijohet një i ri.
    Nëse ekziston, thjesht i kthehet JWT token i login.
    """
    try:
        tenant_id = normalize_tenant_id(payload.tenant_id)
        print("[GITHUB AUTH] Starting authentication with token...")

        # Verifikojmë Firebase ID Token
        idinfo = id_token.verify_firebase_token(
            payload.token,
            requests.Request(),
            audience=FIREBASE_PROJECT_ID,
            clock_skew_in_seconds=300
        )

        github_email = idinfo.get('email', '')
        if not github_email:
            github_email = idinfo.get('uid', '') + "@github.kapak.com"

        github_name = idinfo.get('name', '')
        github_avatar = idinfo.get('picture', '')

        print(f"[GITHUB AUTH] Token verified. Email: {github_email}, Name: {github_name}")

        if not github_email:
            raise ValueError("GitHub token nuk përmban email ose UID")

        user = _tenant_user_query(db, tenant_id).filter(User.email == github_email).first()
        if not user:
            user = _global_user_by_email(db, github_email)

        if not user:
            print("[GITHUB AUTH] Përdoruesi nuk ekziston. Duke e krijuar...")

            base_username = github_email.split('@')[0]
            base_username = base_username[:40]
            base_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username)

            existing_user = _tenant_user_query(db, tenant_id).filter(User.username == base_username).first()
            if not existing_user:
                existing_user = _global_user_by_username(db, base_username)
            if existing_user:
                base_username = f"{base_username}_{str(uuid.uuid4())[:4]}"

            print(f"[GITHUB AUTH] Përpiqem të krijohet përdorues me username: {base_username}")

            user = User(
                username=base_username,
                email=github_email,
                hashed_password=hash_password(str(uuid.uuid4())),
                display_name=github_name or base_username,
                avatar_url=github_avatar,
                is_verified=True,
                tenant_id=tenant_id
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = _tenant_user_query(db, tenant_id).filter(User.email == github_email).first()
                if not user:
                    user = _global_user_by_email(db, github_email)
                if not user:
                    raise
            db.refresh(user)

            print(f"[GITHUB AUTH] Përdoruesi u krijua me ID: {user.id}")
        else:
            print(f"[GITHUB AUTH] Përdoruesi ekziston me ID: {user.id}")
            if github_avatar and not user.avatar_url:
                user.avatar_url = github_avatar
                db.commit()

        # Krijoni JWT token
        if user.two_factor_enabled:
            is_trusted = False
            if payload.trusted_device_token:
                try:
                    tok_payload = verify_token(payload.trusted_device_token)
                    if tok_payload.get("type") == "trusted_device" and tok_payload.get("sub") == str(user.id):
                        is_trusted = True
                except Exception:
                    pass

            if not is_trusted:
                temp_token = create_access_token(
                    data={"sub": str(user.id), "is_2fa_temp": True},
                    expires_delta=timedelta(minutes=5)
                )
                return {"requires_2fa": True, "temp_token": temp_token}

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "tenant_id": user.tenant_id,
            }
        )
        refresh_token = create_refresh_token(
            data={
                "sub": str(user.id),
            }
        )

        print("[GITHUB AUTH] Token u gjenera me sukses")
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    except ValueError as e:
        print(f"[GITHUB AUTH ERROR] ValueError: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Validimi me GitHub dështoi: {str(e)}",
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[GITHUB AUTH ERROR] Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gabim i brendshëm: {str(e)}",
        )

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
):
    """
    Kërkesë për rishkrim të fjalëkalimit.
    Gjeneron një kod 6-shifror dhe e tregon në alert.
    """
    user = _global_user_by_email(db, request.email)

    if not user:
        return {"message": "Kërkesa u regjistrua. Nëse ky email ekziston, një kod për rishkrimin e fjalëkalimit do të dërgohet."}

    reset_code = ''.join(random.choices(string.digits, k=6))
    RESET_TOKENS[reset_code] = user.email

    return {"message": "Kodi u gjenerua.", "code": reset_code}

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    email = RESET_TOKENS.get(request.token)
    if not email:
        raise HTTPException(status_code=400, detail="Kodi është i pasaktë ose ka skaduar.")

    user = _user_query(db).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Përdoruesi nuk u gjet.")

    user.hashed_password = hash_password(request.new_password)
    db.commit()

    del RESET_TOKENS[request.token]
    return {"message": "Fjalëkalimi u ndryshua me sukses!"}

@router.post("/refresh", response_model=Token)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Kërkon një access token të ri duke përdorur një refresh token të vlefshëm.
    """
    try:
        payload = verify_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        user = _user_query(db).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Create new access token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "tenant_id": user.tenant_id,
            }
        )
        # Mund të rikthejmë të njëjtin refresh_token ose të gjenerojmë një të ri (refresh token rotation)
        # Për thjeshtësi do e rikthejmë të njëjtin në këtë implementim, ose një të ri:
        new_refresh_token = create_refresh_token(
            data={
                "sub": str(user.id),
            }
        )

        return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
