from src.chatbot import HybridChatbot


def test_chatbot_greeting_and_faq():
    bot = HybridChatbot(intents_path="data/intents.json", training_csv_path="data/training_examples.csv")
    res = bot.respond("Hello!", session_id="test_session_1")
    assert res["intent"] == "greeting"
    assert len(res["response"]) > 0

    res2 = bot.respond("What is your price list?", session_id="test_session_1")
    assert res2["intent"] == "pricing"
    assert "50" in res2["response"] or "price" in res2["response"] or "cost" in res2["response"]


def test_chatbot_multi_turn_booking_flow():
    bot = HybridChatbot(intents_path="data/intents.json", training_csv_path="data/training_examples.csv")
    sid = "booking_test_user"

    # Turn 1: Initial request
    r1 = bot.respond("I want to book an appointment", session_id=sid)
    assert r1["intent"] == "book_appointment"
    assert r1["pending_slot"] == "name"

    # Turn 2: Provide name
    r2 = bot.respond("Alice Smith", session_id=sid)
    assert r2["pending_slot"] == "service"
    assert r2["slots"].get("name") == "Alice Smith"

    # Turn 3: Provide service
    r3 = bot.respond("Consultation", session_id=sid)
    assert r3["pending_slot"] == "party_size"

    # Turn 4: Provide party size
    r4 = bot.respond("2 people", session_id=sid)
    assert r4["pending_slot"] == "date"
    assert r4["slots"].get("party_size") == 2

    # Turn 5: Provide date
    r5 = bot.respond("Tomorrow", session_id=sid)
    assert r5["pending_slot"] == "time"

    # Turn 6: Provide time
    r6 = bot.respond("3:00 PM", session_id=sid)
    assert "Booking Confirmed!" in r6["response"]
    assert r6["active_booking"] is not None
    assert r6["active_booking"]["name"] == "Alice Smith"
    assert r6["active_booking"]["party_size"] == 2

    # Turn 7: Check booking status
    r7 = bot.respond("Check my reservation details", session_id=sid)
    assert "Your Active Reservation" in r7["response"]
    assert "Alice Smith" in r7["response"]

    # Turn 8: Cancel booking
    r8 = bot.respond("Please cancel my booking", session_id=sid)
    assert "cancelled" in r8["response"]

    # Turn 9: Check status again after cancellation
    r9 = bot.respond("Do I have any active reservations?", session_id=sid)
    assert "do not have any active bookings" in r9["response"]
