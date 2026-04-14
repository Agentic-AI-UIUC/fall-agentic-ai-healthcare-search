"""
Appointment scheduling agent.

Provides two public functions:
- is_scheduling_request(message) — keyword check for scheduling intent
- book_appointment(...)          — validate + write to DB, return confirmation
"""

from db.database import create_appointment

BOOKING_KEYWORDS = [
    "book",
    "appointment",
    "schedule",
    "see a doctor",
    "make an appointment",
    "visit",
    "set up a time",
]


def is_scheduling_request(message: str) -> bool:
    """Return True if the message expresses intent to book an appointment."""
    lower = message.lower()
    return any(kw in lower for kw in BOOKING_KEYWORDS)


def book_appointment(
    patient_name: str,
    email: str,
    reason: str,
    preferred_date: str,
    preferred_time: str,
    intake_session_id: str | None = None,
) -> dict:
    """
    Book an appointment and return a confirmation dict.

    Returns:
        {"success": True, "appointment_id": str, "message": str}
        or
        {"success": False, "error": str}
    """
    if not patient_name or not email or not preferred_date or not preferred_time:
        return {"success": False, "error": "Name, email, date, and time are required."}

    try:
        appt_id = create_appointment(
            patient_name=patient_name,
            email=email,
            reason=reason,
            date=preferred_date,
            time=preferred_time,
            intake_session_id=intake_session_id,
        )
    except Exception as exc:
        return {"success": False, "error": f"Could not save appointment: {exc}"}

    return {
        "success": True,
        "appointment_id": appt_id,
        "message": (
            f"Your appointment has been booked for {preferred_date} at {preferred_time}. "
            f"Confirmation ID: {appt_id.replace('-', '')[:8].upper()}. "
            "A healthcare provider will confirm your appointment shortly."
        ),
    }
