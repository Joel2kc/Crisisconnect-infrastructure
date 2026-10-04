import os
from dotenv import load_dotenv
from sqlmodel import Session, select

from db.database import engine
from db.models.user_model import User
from db.models.agency_model import Agency
from enums.user import UserRole
from core.security import hash_password

load_dotenv()


def seed_government_official():
    email = os.getenv("SEED_GOV_EMAIL")
    password = os.getenv("SEED_GOV_PASSWORD")
    full_name = os.getenv("SEED_GOV_NAME")
    phone = os.getenv("SEED_GOV_PHONE")

    if not email or not password or not full_name:
        raise ValueError(
            "SEED_GOV_EMAIL, SEED_GOV_PASSWORD and SEED_GOV_NAME must be set"
        )

    with Session(engine) as session:
        existing_user = session.exec(
            select(User).where(User.email == email)
        ).first()

        if existing_user:
            print(f"User with email {email} already exists.")
            return

        government_official = User(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=UserRole.government_official,
            is_active=True,
            email_verified=True,
        )

        session.add(government_official)
        session.commit()
        session.refresh(government_official)

        print(
            f"Government official created successfully: "
            f"{government_official.email} (ID: {government_official.id})"
        )


if __name__ == "__main__":
    seed_government_official()