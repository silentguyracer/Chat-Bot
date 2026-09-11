import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path or sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.api import app
from src.ssh_security import SSHKeyManager, SSHCryptographicSigner, SSHTunnelHelper

client = TestClient(app)


def test_ssh_key_generation():
    # Ed25519
    ed_keys = SSHKeyManager.generate_ed25519_keypair(comment="test-key")
    assert "BEGIN OPENSSH PRIVATE KEY" in ed_keys["private_key"]
    assert ed_keys["public_key"].startswith("ssh-ed25519")

    # RSA
    rsa_keys = SSHKeyManager.generate_rsa_keypair(key_size=2048, comment="test-rsa")
    assert "BEGIN OPENSSH PRIVATE KEY" in rsa_keys["private_key"]
    assert rsa_keys["public_key"].startswith("ssh-rsa")


def test_ssh_message_signing_and_verification():
    keys = SSHKeyManager.generate_ed25519_keypair()
    priv = keys["private_key"]
    pub = keys["public_key"]

    msg = b"Book a table for 2 tomorrow at 7pm"
    signature = SSHCryptographicSigner.sign_message(priv, msg)
    assert isinstance(signature, str)
    assert len(signature) > 20

    # 1. Valid verification
    is_valid = SSHCryptographicSigner.verify_message(pub, msg, signature)
    assert is_valid is True

    # 2. Tampered message detection
    tampered_msg = b"Book a table for 99 tomorrow at 7pm"
    is_tampered = SSHCryptographicSigner.verify_message(pub, tampered_msg, signature)
    assert is_tampered is False


def test_secure_chat_api_endpoint():
    keys = SSHKeyManager.generate_ed25519_keypair()
    priv = keys["private_key"]
    pub = keys["public_key"]

    message = "What are your business hours?"
    session_id = "ssh_test_session"
    raw_payload = f"{message}:{session_id}".encode("utf-8")
    sig = SSHCryptographicSigner.sign_message(priv, raw_payload)

    # Valid signed request
    response = client.post(
        "/api/secure-chat",
        json={
            "message": message,
            "session_id": session_id,
            "public_key": pub,
            "signature": sig
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "business_hours"

    # Invalid / forged signature request
    forged_response = client.post(
        "/api/secure-chat",
        json={
            "message": message,
            "session_id": session_id,
            "public_key": pub,
            "signature": "forged_invalid_signature_base64_xyz=="
        }
    )
    assert forged_response.status_code == 401


def test_ssh_keygen_api_endpoint():
    res = client.post("/api/ssh/generate-keys?key_type=ed25519")
    assert res.status_code == 200
    data = res.json()
    assert "private_key" in data
    assert "public_key" in data
    assert data["key_type"] == "ssh-ed25519"
