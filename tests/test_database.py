import os
from pathlib import Path
from src.database import DatabaseManager


def test_database_initialization(tmp_path):
    test_db = tmp_path / "test_chat.db"
    db = DatabaseManager(db_path=str(test_db))
    assert test_db.exists()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "bookings" in tables
        assert "chat_logs" in tables


def test_booking_crud_operations(tmp_path):
    test_db = tmp_path / "test_chat.db"
    db = DatabaseManager(db_path=str(test_db))

    booking_data = {
        "booking_id": "BK-TEST01",
        "session_id": "user_123",
        "name": "Sarah Connor",
        "service": "Consultation",
        "party_size": 2,
        "date": "Tomorrow",
        "time": "5:00 PM",
        "status": "CONFIRMED"
    }

    # 1. Create
    success = db.create_booking(booking_data)
    assert success is True

    # 2. Read by ID
    booking = db.get_booking_by_id("BK-TEST01")
    assert booking is not None
    assert booking["customer_name"] == "Sarah Connor"
    assert booking["party_size"] == 2
    assert booking["status"] == "CONFIRMED"

    # 3. Read by Session
    session_booking = db.get_latest_booking_by_session("user_123", status="CONFIRMED")
    assert session_booking is not None
    assert session_booking["booking_id"] == "BK-TEST01"

    # 4. Update Status (Cancel)
    updated = db.update_booking_status("BK-TEST01", "CANCELLED")
    assert updated is True

    # Verify updated status
    booking_after = db.get_booking_by_id("BK-TEST01")
    assert booking_after["status"] == "CANCELLED"

    # 5. List all
    all_bookings = db.list_all_bookings()
    assert len(all_bookings) == 1


def test_chat_logging_and_analytics(tmp_path):
    test_db = tmp_path / "test_chat.db"
    db = DatabaseManager(db_path=str(test_db))

    # Log turn
    success = db.log_chat_turn(
        session_id="user_abc",
        user_message="When are you open?",
        bot_response="We are open Monday through Friday 9am to 8pm.",
        intent="business_hours",
        method="rule_exact",
        confidence=1.0,
        slots={}
    )
    assert success is True

    # Retrieve logs
    logs = db.get_session_logs("user_abc")
    assert len(logs) == 1
    assert logs[0]["intent"] == "business_hours"
    assert logs[0]["user_message"] == "When are you open?"

    # Check intent distribution
    dist = db.get_intent_distribution()
    assert dist.get("business_hours") == 1
