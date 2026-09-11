import sys
from pathlib import Path
import pytest

# Ensure local project root is first on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path or sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.api import app
from src.security import sanitize_input, rate_limiter

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_chat_endpoint_valid_request():
    response = client.post(
        "/api/chat",
        json={"message": "What are your business hours?", "session_id": "api_test_user"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "business_hours"
    assert "response" in data
    assert len(data["response"]) > 0


def test_chat_multi_turn_booking_flow():
    sid = "api_booking_user"

    # Turn 1
    r1 = client.post("/api/chat", json={"message": "I want to book an appointment", "session_id": sid})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["intent"] == "book_appointment"
    assert d1["pending_slot"] == "name"

    # Turn 2: Name
    r2 = client.post("/api/chat", json={"message": "Bruce Wayne", "session_id": sid})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["slots"].get("name") == "Bruce Wayne"


def test_input_sanitization_xss_protection():
    # Test script tag stripping
    malicious = "<script>alert('XSS')</script>Hello there!"
    sanitized = sanitize_input(malicious)
    assert "<script>" not in sanitized
    assert "alert" not in sanitized
    assert "Hello there!" in sanitized

    # Test via API
    res = client.post(
        "/api/chat",
        json={"message": "<script>evilCode()</script>Hello", "session_id": "xss_test"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "greeting"


def test_rate_limiter_logic():
    client_ip = "test_ip_123"
    # Reset limiter for this IP
    rate_limiter.requests_by_ip[client_ip] = []

    # Send up to max_requests
    for _ in range(rate_limiter.max_requests):
        allowed, remaining = rate_limiter.is_allowed(client_id=client_ip)
        assert allowed is True

    # Next request should be blocked
    blocked, remaining = rate_limiter.is_allowed(client_id=client_ip)
    assert blocked is False
    assert remaining == 0
