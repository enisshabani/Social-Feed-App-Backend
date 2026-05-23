"""
KaPak - Authentication Router
Endpoints: register, login, refresh token, me.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, BackgroundTasks

from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import uuid
import re
import random
import string

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, verify_token
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    LoginResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshTokenRequest,
)
from app.core.email import send_reset_password_email, send_verification_email, create_super_simple_token
import pyotp
import qrcode
import io
import base64
import json


router = APIRouter()

# --- VARIABLAT PËR KUFIZIMIN KUNDËR BRUTE FORCE ---
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
RESET_TOKENS = {}
VERIFICATION_TOKENS = {}

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    - **username**: 3-50 chars, alphanumeric + underscore only
    - **email**: valid email address
    - **password**: minimum 6 characters
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
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
        tenant_id=user_data.tenant_id,
        is_verified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Dërgojmë email-in e verifikimit në background
    verification_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    VERIFICATION_TOKENS[verification_token] = new_user.email
    background_tasks.add_task(send_verification_email, new_user.email, verification_token)

    return new_user

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    email = VERIFICATION_TOKENS.get(token)
    if not email:
        raise HTTPException(status_code=400, detail="Token i pavlefshëm ose i skaduar.")
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Përdoruesi nuk u gjet.")
        
    user.is_verified = True
    db.commit()
    
    del VERIFICATION_TOKENS[token]
    
    return {"message": "Email-i juaj u verifikua me sukses!"}


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    trusted_device_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Login with username and password.
    Returns a JWT access token.
    """
    
    # 1. Kontrollo nëse përdoruesi (ose IP) është bllokuar
    client_ip = request.client.host if request.client else "unknown"
    lock_key = f"{form_data.username}_{client_ip}"
    
    if lock_key in LOGIN_ATTEMPTS:
        attempt_data = LOGIN_ATTEMPTS[lock_key]
        if attempt_data["locked_until"] and attempt_data["locked_until"] > datetime.now(timezone.utc):
            remaining_time = (attempt_data["locked_until"] - datetime.now(timezone.utc)).total_seconds() // 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Llogaria juaj është bllokuar përkohësisht. Ju lutem provoni pas {int(remaining_time)} minutash."
            )

    # Find user by username or email
    user = db.query(User).filter(
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


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.
    Requires a valid JWT token.
    """
    return current_user


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
        print(f"[GOOGLE AUTH] Starting authentication with token...")
        
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
        
        # 2. Kontrollojmë nëse e kemi këtë email në db tonë
        user = db.query(User).filter(User.email == google_email).first()
        
        if not user:
            print(f"[GOOGLE AUTH] Përdoruesi nuk ekziston. Duke e krijuar...")
            
            # 3. Nëse NUK është ky email asnjëherë te ne, regjistroje automatikisht!
            base_username = google_email.split('@')[0]
            base_username = base_username[:40]
            base_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username)

            existing_user = db.query(User).filter(User.username == base_username).first()
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
                tenant_id=payload.tenant_id
            )
            db.add(user)
            db.commit()
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
        
        print(f"[GOOGLE AUTH] Token u gjenera me sukses")
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
        print(f"[GITHUB AUTH] Starting authentication with token...")
        
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
        
        user = db.query(User).filter(User.email == github_email).first()
        
        if not user:
            print(f"[GITHUB AUTH] Përdoruesi nuk ekziston. Duke e krijuar...")
            
            base_username = github_email.split('@')[0]
            base_username = base_username[:40]
            base_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username)
            
            existing_user = db.query(User).filter(User.username == base_username).first()
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
                tenant_id=payload.tenant_id
            )
            db.add(user)
            db.commit()
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
        
        print(f"[GITHUB AUTH] Token u gjenera me sukses")
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Kërkesë për rishkrim të fjalëkalimit.
    Dërgon një email me linkun.
    """
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        return {"message": "Kërkesa u regjistrua. Nëse ky email ekziston, një email për rishkrimin e fjalëkalimit do të dërgohet."}
    
    reset_code = ''.join(random.choices(string.digits, k=6))
    RESET_TOKENS[reset_code] = user.email

    background_tasks.add_task(send_reset_password_email, user.email, reset_code)

    return {"message": "Kërkesa u regjistrua. Nëse ky email ekziston, një email për rishkrimin e fjalëkalimit do të dërgohet."}

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    email = RESET_TOKENS.get(request.token)
    if not email:
        raise HTTPException(status_code=400, detail="Kodi është i pasaktë ose ka skaduar.")
        
    user = db.query(User).filter(User.email == email).first()
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
            
        user = db.query(User).filter(User.id == int(user_id)).first()
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
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
