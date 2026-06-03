import pytest
from unittest.mock import patch


def test_is_scheduling_request_detects_book():
    from pipeline.agents.scheduling_agent import is_scheduling_request
    assert is_scheduling_request("I want to book an appointment") is True


def test_is_scheduling_request_detects_schedule():
    from pipeline.agents.scheduling_agent import is_scheduling_request
    assert is_scheduling_request("Can I schedule a visit?") is True


def test_is_scheduling_request_detects_see_a_doctor():
    from pipeline.agents.scheduling_agent import is_scheduling_request
    assert is_scheduling_request("I need to see a doctor") is True


def test_is_scheduling_request_negative():
    from pipeline.agents.scheduling_agent import is_scheduling_request
    assert is_scheduling_request("What are the symptoms of flu?") is False


def test_book_appointment_success():
    from pipeline.agents.scheduling_agent import book_appointment
    with patch("pipeline.agents.scheduling_agent.create_appointment", return_value="test-uuid-1234"):
        result = book_appointment(
            patient_name="Alice",
            email="alice@example.com",
            reason="Annual checkup",
            preferred_date="2026-04-20",
            preferred_time="10:00 AM",
        )
    assert result["success"] is True
    assert "TESTUUID" in result["message"]
    assert "2026-04-20" in result["message"]
    assert "10:00 AM" in result["message"]


def test_book_appointment_missing_name():
    from pipeline.agents.scheduling_agent import book_appointment
    result = book_appointment(
        patient_name="",
        email="alice@example.com",
        reason="checkup",
        preferred_date="2026-04-20",
        preferred_time="10:00 AM",
    )
    assert result["success"] is False
    assert "error" in result


def test_book_appointment_missing_email():
    from pipeline.agents.scheduling_agent import book_appointment
    result = book_appointment(
        patient_name="Alice",
        email="",
        reason="checkup",
        preferred_date="2026-04-20",
        preferred_time="10:00 AM",
    )
    assert result["success"] is False
    assert "error" in result


def test_book_appointment_db_error():
    from pipeline.agents.scheduling_agent import book_appointment
    with patch("pipeline.agents.scheduling_agent.create_appointment", side_effect=Exception("DB locked")):
        result = book_appointment(
            patient_name="Alice",
            email="alice@example.com",
            reason="checkup",
            preferred_date="2026-04-20",
            preferred_time="10:00 AM",
        )
    assert result["success"] is False
    assert "error" in result


def test_book_appointment_missing_date():
    from pipeline.agents.scheduling_agent import book_appointment
    result = book_appointment(
        patient_name="Alice",
        email="alice@example.com",
        reason="checkup",
        preferred_date="",
        preferred_time="10:00 AM",
    )
    assert result["success"] is False
    assert "error" in result
