import json
import pytest
import db.database as db_module


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()


def test_save_and_get_message():
    msg_id = db_module.save_message("sess1", "user", "hello", sources=[], emergency=False)
    assert msg_id is not None
    msgs = db_module.get_conversation("sess1")
    assert len(msgs) == 1
    assert msgs[0]["message"] == "hello"
    assert msgs[0]["role"] == "user"
    assert msgs[0]["emergency"] == 0


def test_get_conversation_empty():
    assert db_module.get_conversation("nobody") == []


def test_save_and_load_intake_session():
    session = {
        "step": "greeting",
        "form": {"chief_complaint": "headache"},
        "messages": [{"role": "user", "text": "hi"}],
        "complete": False,
        "emergency": False,
    }
    db_module.save_intake_session("intake1", session)
    loaded = db_module.load_intake_session("intake1")
    assert loaded["step"] == "greeting"
    assert loaded["form"]["chief_complaint"] == "headache"
    assert loaded["messages"][0]["text"] == "hi"
    assert loaded["complete"] is False


def test_load_intake_session_missing():
    assert db_module.load_intake_session("nonexistent") is None


def test_save_intake_session_upsert():
    session = {"step": "greeting", "form": None, "messages": [], "complete": False, "emergency": False}
    db_module.save_intake_session("s1", session)
    session["step"] = "demographics"
    db_module.save_intake_session("s1", session)
    loaded = db_module.load_intake_session("s1")
    assert loaded["step"] == "demographics"


def test_save_and_get_document():
    db_module.save_document("doc1", "test.pdf", "doc1.pdf", "/uploads/doc1.pdf")
    doc = db_module.get_document("doc1")
    assert doc["original_name"] == "test.pdf"
    assert doc["stored_name"] == "doc1.pdf"


def test_get_document_missing():
    assert db_module.get_document("notexist") is None


def test_create_and_get_appointment():
    appt_id = db_module.create_appointment(
        "John Doe", "john@example.com", "annual checkup",
        "2026-04-20", "10:00 AM"
    )
    assert appt_id is not None
    appt = db_module.get_appointment(appt_id)
    assert appt["patient_name"] == "John Doe"
    assert appt["patient_email"] == "john@example.com"
    assert appt["status"] == "pending"
    assert appt["intake_session_id"] is None


def test_create_appointment_with_intake_id():
    appt_id = db_module.create_appointment(
        "Jane Doe", "jane@example.com", "checkup",
        "2026-04-21", "2:00 PM", intake_session_id="intake-abc"
    )
    appt = db_module.get_appointment(appt_id)
    assert appt["intake_session_id"] == "intake-abc"


def test_update_appointment_status():
    appt_id = db_module.create_appointment(
        "Bob", "bob@example.com", "checkup", "2026-04-22", "9:00 AM"
    )
    db_module.update_appointment_status(appt_id, "confirmed")
    appt = db_module.get_appointment(appt_id)
    assert appt["status"] == "confirmed"


def test_get_appointments():
    db_module.create_appointment("A", "a@a.com", "visit", "2026-04-20", "10:00 AM")
    db_module.create_appointment("B", "b@b.com", "visit", "2026-04-21", "11:00 AM")
    appts = db_module.get_appointments()
    assert len(appts) == 2


def test_get_appointment_missing():
    assert db_module.get_appointment("not-a-real-id") is None
