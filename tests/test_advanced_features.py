import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path or sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.api import app
from src.sentiment_analyzer import SentimentAnalyzer
from src.chatbot import HybridChatbot
from src.analytics import analytics_engine

client = TestClient(app)


def test_sentiment_analysis():
    # Positive
    res_pos = SentimentAnalyzer.analyze("This service is great and fantastic!")
    assert res_pos["sentiment"] == "positive"
    assert res_pos["score"] > 0.2

    # Negative / Frustrated
    res_neg = SentimentAnalyzer.analyze("This is useless, connect me to a human representative!")
    assert res_neg["is_frustrated"] is True
    assert res_neg["needs_escalation"] is True


def test_mid_flow_digression_handling():
    bot = HybridChatbot(intents_path="data/intents.json", training_csv_path="data/training_examples.csv")
    sid = "digression_test_user"

    # Turn 1: Start booking
    r1 = bot.respond("I want to book an appointment", session_id=sid)
    assert r1["intent"] == "book_appointment"
    assert r1["pending_slot"] == "name"

    # Turn 2: User interrupts with an FAQ digression (where are you located?)
    r2 = bot.respond("Wait, where is your office located?", session_id=sid)
    assert "digression" in r2["intent"]
    # Check that it answered the location
    assert "123 Innovation Way" in r2["response"]
    # Check that it resumed the booking prompt
    assert "name" in r2["response"].lower()
    assert r2["pending_slot"] == "name"


def test_slot_correction_in_flight():
    bot = HybridChatbot(intents_path="data/intents.json", training_csv_path="data/training_examples.csv")
    sid = "correction_test_user"

    # Start booking with party of 2
    r1 = bot.respond("Book a table for 2 tomorrow at 7pm", session_id=sid)
    assert r1["slots"]["party_size"] == 2
    assert r1["pending_slot"] == "name"

    # In-flight correction: change party size to 5 while giving name
    r2 = bot.respond("My name is Sarah Connor, but actually make it for 5 people", session_id=sid)
    assert r2["active_booking"] is not None
    assert r2["active_booking"]["name"] == "Sarah Connor"
    assert r2["active_booking"]["party_size"] == 5
    assert "booking confirmed" in r2["response"].lower()


def test_analytics_tracking():
    summary = analytics_engine.get_summary()
    assert "total_sessions" in summary
    assert "booking_funnel" in summary
    assert "sentiment_distribution" in summary


def test_websocket_chat_endpoint():
    with client.websocket_connect("/ws/chat/test_ws_user") as websocket:
        websocket.send_json({"message": "What are your business hours?"})

        # Receive typing event
        evt_typing = websocket.receive_json()
        assert evt_typing["type"] == "typing"

        # Receive bot response
        evt_msg = websocket.receive_json()
        assert evt_msg["type"] == "message"
        assert evt_msg["payload"]["intent"] == "business_hours"
