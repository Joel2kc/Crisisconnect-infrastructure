import os
import sys

from sqlmodel import Session, select

from core.security import hash_password
from db.database import engine
from db.models.agency_model import Agency
from db.models.user_model import User
from enums.user import UserRole


def seed_admin():
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    full_name = os.getenv("SEED_ADMIN_NAME", "Crisis Connect Admin")

    if not email or not password:
        print(
            "SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD must be set "
            "(as env variables, not hardcoded here) before running this script."
        )
        sys.exit(1)

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            print(f"An account with {email} already exists - nothing to do.")
            return

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.crisis_connect_admin,
            is_active=True,
            email_verified=True,  # manually provisioned, no verification flow needed
        )
        session.add(admin)
        session.commit()

    print(f"Crisis Connect Admin account created for {email}.")


if __name__ == "__main__":
    seed_admin()