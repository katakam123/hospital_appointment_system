
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    require_roles,
    verify_password,
    get_current_user,
)
from app.database import get_db
from app.models import Patient, RefreshToken, User


router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


def create_token_response(db: Session, user: User) -> dict:
    access_token = create_access_token(user)
    refresh_token, expires_at = create_refresh_token(user)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 30 * 60,
    }


def get_valid_refresh_record(
    db: Session,
    refresh_token: str,
) -> tuple[dict, RefreshToken]:
    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")

    user_id = payload.get("sub")
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    record = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == hash_refresh_token(refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
        .first()
    )

    if record is None:
        raise HTTPException(
            status_code=401,
            detail="Refresh token is invalid or revoked",
        )

    expiry = record.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    return payload, record


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(request.email).lower()

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = User(
        full_name=request.full_name.strip(),
        email=email,
        hashed_password=hash_password(request.password),
        role="patient",
        is_active=True,
    )

    try:
        db.add(user)
        db.flush()

        patient = Patient(
            user_id=user.id,
            phone=request.phone,
            date_of_birth=request.date_of_birth,
            gender=request.gender,
            address=request.address,
        )
        db.add(patient)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # In Swagger, enter the user's email in the "username" field.
    email = form_data.username.strip().lower()

    user = db.query(User).filter(User.email == email).first()

    if (
        not user
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")

    return create_token_response(db, user)


@router.post("/refresh")
def refresh_access_token(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):
    payload, record = get_valid_refresh_record(db, request.refresh_token)

    user = db.query(User).filter(User.id == int(payload["sub"])).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or unavailable")

    # The refresh token remains valid until it expires or is revoked.
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": 30 * 60,
    }


@router.post("/logout")
def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db),
):
    _, record = get_valid_refresh_record(db, request.refresh_token)
    record.revoked_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# Reusable role dependencies for future protected routers:
admin_only = require_roles("admin")
doctor_only = require_roles("doctor")
patient_only = require_roles("patient")



