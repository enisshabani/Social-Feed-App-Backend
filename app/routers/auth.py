"""
KaPak - Authentication Router
Endpoints: register, login, refresh token, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    ForgotPasswordRequest,
)
from app.core.email import send_reset_password_email, create_super_simple_token

router = APIRouter()

# --- VARIABLAT PËR KUFIZIMIN KUNDËR BRUTE FORCE ---
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
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

    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        display_name=user_data.display_name or user_data.username,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
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

    # Create access token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
        }
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.
    Requires a valid JWT token.
    """
    return current_user


from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import uuid

# Projekti ynë në Firebase
FIREBASE_PROJECT_ID = "kapak-3af75"

class GoogleAuthRequest(BaseModel):
    token: str

@router.post("/google")
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Identifikimi me Google (Nga Firebase). Nëse përdoruesi nuk ekziston, krijohet një i ri.
    Nëse ekziston, thjesht i kthehet JWT token i login.
    """
    try:
        # 1. Verifikojmë tokenin i cili vjen nga Frontend (Firebase ID Token)
        idinfo = id_token.verify_firebase_token(payload.token, requests.Request(), audience=FIREBASE_PROJECT_ID)
        
        google_email = idinfo['email']
        google_name = idinfo.get('name', '')
        
        # 2. Kontrollojmë nëse e kemi këtë email në db tonë
        user = db.query(User).filter(User.email == google_email).first()
        
        if not user:
            # 3. Nëse NUK është ky email asnjëherë te ne, regjistroje automatikisht!
            base_username = google_email.split('@')[0]
            # Në rast se username i tij (i emailit) ekziston, shtojmë një fjalë unik
            existing_user = db.query(User).filter(User.username == base_username).first()
            if existing_user:
                base_username = f"{base_username}_{str(uuid.uuid4())[:4]}"
                
            user = User(
                username=base_username,
                email=google_email,
                # Fjalkalimi do te jete random pasi kyçet gjithmonë me Google
                hashed_password=hash_password(str(uuid.uuid4())),
                display_name=google_name,
                is_verified=True # Nga Google është e verifikuar gjithmonë!
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
        # 4. Në fund pavarësisht u krijua nga e para app o ekzistontë, bëj logout:
        # Bëjmë update llogarinë (që t'i gjenerohet tokeni ynë vendor)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
            }
        )
        return {"access_token": access_token, "token_type": "bearer"}
        
    except ValueError:
        # Tokeni i Google ka skaduar, ose dikush e shkroi manualisht
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Validimi me Google dështoi",
        )

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Kërkesë për rishkrim të fjalëkalimit.
    Lidhet me backend-in për të parë nëse ekziston emaili.
    Nuk kthen gabim nëse emaili nuk ekziston (për arsye sigurie/enumerimi).
    Nëse gjendet, këtu do të shtohej logjika e dërgimit të email-it.
    """
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        # Për siguri, shpesh këshillohet të kthehet i njëjti mesazh suksesi
        # në mënyrë që hakerat të mos mund të gjejnë se cili email ekziston.
        pass
    else:
        # Përdoruesi u gjet në DB! Tani dërgojmë emailin me Token tek kutia tij
        reset_token = create_super_simple_token()

        # Përderisa kjo kërkon async ne duhet ti definojmë funskionin 'forgot_password' me **async def**
        await send_reset_password_email(email_to=user.email, reset_token=reset_token)

    return {"message": "Kërkesa u regjistrua. Nëse ky email ekziston, një link për rishkrimin e fjalëkalimit është dërguar."}
