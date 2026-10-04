from sqlmodel import Session, select

from db.database import engine
from db.models.volunteer_model import Skill


DEFAULT_SKILLS = [
    "First Aid",
    "Translation",
    "Diving",
    "Search & Rescue",
    "Teamwork",
    "CPR",
    "Logistics",
]


def seed_skills():
    with Session(engine) as session:
        for skill_name in DEFAULT_SKILLS:
            existing_skill = session.exec(
                select(Skill).where(Skill.name == skill_name)
            ).first()

            if existing_skill:
                continue

            session.add(Skill(name=skill_name))

        session.commit()

    print("Default volunteer skills seeded successfully.")


if __name__ == "__main__":
    seed_skills()
