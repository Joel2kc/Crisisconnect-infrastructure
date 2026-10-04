import random
from datetime import datetime
from sqlmodel import Session, select
from enums.incident import EmergencyType

TYPE_CODES = {
    EmergencyType.fire: "FIRE",
    EmergencyType.medical: "MED",
    EmergencyType.accident: "ACC",
    EmergencyType.crime: "CRM",
    EmergencyType.flood: "FLD",
    EmergencyType.others: "OTH",
}


def generate_reference_code(session: Session, model, emergency_type: EmergencyType) -> str:
    """
    Generates a unique, human-readable incident reference code, e.g.
    CC-MED-2026-4507 - the code a citizen without an account uses to
    look up their report later.
    """
    year = datetime.utcnow().year
    type_code = TYPE_CODES[emergency_type]

    for _ in range(20):
        suffix = random.randint(1000, 9999)
        code = f"CC-{type_code}-{year}-{suffix}"

        existing = session.exec(
            select(model).where(model.reference_code == code)
        ).first()

        if not existing:
            return code

    raise RuntimeError("Could not generate a unique reference code after 20 attempts.")
    