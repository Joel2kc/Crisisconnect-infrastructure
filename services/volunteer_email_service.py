from services.email_service import send_email_safe

async def send_volunteer_verified_email(to: str, full_name: str) -> None:
    await send_email_safe(
        to=to, subject="CrisisConnect — You're verified!",
        template_name="volunteer_verified.html",
        context={"full_name": full_name},
    )

async def send_volunteer_suspended_email(to: str, full_name: str) -> None:
    await send_email_safe(
        to=to, subject="CrisisConnect — Volunteer status update",
        template_name="volunteer_suspended.html",
        context={"full_name": full_name},
    )
