from db.models.user_model import User
from fastapi import HTTPException
from sqlmodel import select
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
from services.auth_service import AuthService
from db.models.refresh_token import RefreshToken
from datetime import datetime, timedelta, timezone
from db.models.user_model import User

load_dotenv()

secret_key = os.getenv("AUTH_SECRET")
ALGORITHM = "HS256"
user_auth_service = AuthService(model=User)

def rotate_token(token: str, session):
    try:
        user_details = jwt.decode(
            token=token,
            key=user_auth_service.get_secret_key(),
            algorithms=[ALGORITHM],
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if user_details.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")

    db_user = session.get(User, int(user_details["sub"]))
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    stored_tokens = session.exec(
        select(RefreshToken).where(RefreshToken.user_id == str(db_user.id))
    ).all()

    if not any(item.refresh_token == token for item in stored_tokens):
        raise HTTPException(status_code=401, detail="Refresh token not recognized")

    payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "phone": db_user.phone,
        "role": db_user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "full_name": db_user.full_name,
    }

    access_token = jwt.encode(payload, user_auth_service.get_secret_key(), algorithm=ALGORITHM)
    return {
        "access_token": access_token,
        "message": "Token refreshed successfully",
    }


async def login_service(user, session):
    return await user_auth_service.login(user, session)

async def forgot_password_service(email: str, session):
    return await user_auth_service.forgot_password(email, session)

def confirm_reset_otp_service(otp: str, session):
    return user_auth_service.confirm_reset_otp(otp, session)

def reset_password_service(reset_token: str, new_password: str, session):
    return user_auth_service.reset_password(reset_token, new_password, session)
