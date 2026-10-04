import logging
from random import randint
from jose import jwt, JWTError
from fastapi import HTTPException
from sentry_sdk import session
from sqlmodel import select
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from db.models.refresh_token import RefreshToken
from db.models.password_reset import PasswordReset
from services.email_service import send_email_safe
from core.security import hash_password, verify_password

load_dotenv()

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, model):
        self.model = model

    def get_secret_key(self):
        secret_key = os.getenv("AUTH_SECRET")
        if not secret_key:
            raise HTTPException(status_code=500, detail="AUTH_SECRET is not configured")
        return secret_key

    async def login(self, user, session):
        statement = select(self.model).where(self.model.email == user.email)
        db_user = session.exec(statement).first()

        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(user.password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # TODO: re-enable once email verification flow exists

        # if not db_user.email_verified:
        #     raise HTTPException(status_code=403, detail="Email not verified")

        # if not db_user.is_active:
        #     db_user.is_active = True
        #     session.add(db_user)
        #     session.commit()
        #     session.refresh(db_user)

        if not db_user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")

        payload = {
            "sub": str(db_user.id),
            "email": db_user.email,
            "role": db_user.role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "full_name": db_user.full_name,
        }

        access_token = jwt.encode(payload, self.get_secret_key(), algorithm="HS256")

        refresh_payload = {
            "sub": str(db_user.id),
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(days=3),
        }

        refresh_token = jwt.encode(refresh_payload, self.get_secret_key(), algorithm="HS256")

        # Revoke old refresh tokens before issuing a new one
        old_tokens = session.exec(
            select(RefreshToken).where(RefreshToken.user_id == str(db_user.id))
        ).all()
        for old_token in old_tokens:
            session.delete(old_token)

        new_session = RefreshToken(
            user_id=str(db_user.id),
            refresh_token=refresh_token,
        )

        session.add(new_session)
        session.commit()
        session.refresh(new_session)

        logger.info("User %s logged in successfully", db_user.email)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": db_user.id,
                "full_name": db_user.full_name,
                "email": db_user.email,
                "phone": db_user.phone,
                "role": db_user.role,
                "agency_id": db_user.agency_id,
                "is_active": db_user.is_active,
                "email_verified": db_user.email_verified,
            },
        }

    async def forgot_password(self, email: str, session):
        statement = select(self.model).where(self.model.email == email)
        db_user = session.exec(statement).first()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Remove any existing password reset OTPs for this user
        old_otps = session.exec(
            select(PasswordReset).where(PasswordReset.user_id == str(db_user.id))
        ).all()
        for old_otp in old_otps:
            session.delete(old_otp)

        otp = str(randint(10000, 99999))

        password_reset = PasswordReset(
            user_id=str(db_user.id),
            otp=otp,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        session.add(password_reset)
        session.commit()

        await send_email_safe(
            to=db_user.email,
            subject="Password reset request",
            template_name="password_reset.html",
            context={"otp": otp, "full_name": db_user.full_name},
        )

        logger.info("Password reset OTP sent to %s", db_user.email)

        return {"message": "Password reset OTP has been sent to your email"}

    async def confirm_reset_otp(self, otp: str, session):
      otp_statement = select(PasswordReset).where(PasswordReset.otp == otp)
      reset_record = session.exec(otp_statement).first()

      if not reset_record:
          raise HTTPException(status_code=401, detail="Invalid or expired OTP")
      
      if reset_record.used:
        raise HTTPException(status_code=401, detail="OTP already used")

      #  Derive the user from the reset record
      db_user = session.get(self.model, reset_record.user_id)
      if not db_user:
          raise HTTPException(status_code=404, detail="User not found")

      expires_at = reset_record.expires_at
      if expires_at.tzinfo is None:
          expires_at = expires_at.replace(tzinfo=timezone.utc)

      if expires_at < datetime.now(timezone.utc):
          raise HTTPException(status_code=401, detail="OTP has expired")
        
      reset_record.used = True
      session.add(reset_record)
      session.commit()

      reset_payload = {
          "sub": str(db_user.id),
          "reset_id": reset_record.id,
          "type": "password_reset",
          "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
      }
      reset_token = jwt.encode(reset_payload, self.get_secret_key(), algorithm="HS256")

      return {"reset_token": reset_token}

    async def reset_password(self, reset_token: str, new_password: str, session):
        try:
            reset_payload = jwt.decode(
                reset_token,
                self.get_secret_key(),
                algorithms=["HS256"],
            )
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired reset token")

        if reset_payload.get("type") != "password_reset":
            raise HTTPException(status_code=401, detail="Invalid reset token type")

        try:
            user_id = int(reset_payload["sub"])
            reset_id = int(reset_payload["reset_id"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid or expired reset token")

        db_user = session.get(self.model, user_id)
        reset_record = session.get(PasswordReset, reset_id)

        if not db_user or not reset_record or reset_record.user_id != db_user.id:
            raise HTTPException(status_code=401, detail="Invalid or expired reset token")

        db_user.password_hash = hash_password(new_password)
        session.add(db_user)

        session.delete(reset_record)

        session.commit()
        session.refresh(db_user)

        logger.info("Password reset successfully for user %s", db_user.email)

        return {"message": "Password reset successfully"}