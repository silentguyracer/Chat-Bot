import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Depends, Request, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.chatbot import HybridChatbot
from src.security import (
    sanitize_input,
    verify_api_key,
    check_rate_limit,
    SecurityConfig,
    DEFAULT_API_KEY
)
from src.ssh_security import SSHKeyManager, SSHCryptographicSigner, SSHTunnelHelper

app = FastAPI(
    title="Rule-Based & NLP Hybrid Chatbot API (with SSH Security)",
    description="Production-ready conversational API with rate limiting, input sanitization, Ed25519 SSH signature verification, and SQL persistence.",
    version="1.1.0"
)

# Enable CORS for cross-origin web app embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# Static files mount
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Instantiate singleton chatbot instance
chatbot = HybridChatbot()


# Request / Response Schemas
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User message text")
    session_id: Optional[str] = Field(default="web_user", description="Unique conversation session identifier")


class SecureChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(default="secure_user")
    public_key: str = Field(..., description="OpenSSH Ed25519 Public Key")
    signature: str = Field(..., description="Base64-encoded signature of (message + session_id)")


class ChatResponse(BaseModel):
    response: str
    intent: str
    method: str
    confidence: float
    slots: Dict[str, Any]
    pending_slot: Optional[str] = None
    active_booking: Optional[Dict[str, Any]] = None
    extracted_entities: Optional[Dict[str, Any]] = None


# --- Core Web Endpoints ---

@app.get("/", include_in_schema=False)
async def serve_home():
    """Serve the animated web app for browser testing."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "Chatbot API is running. Visit /docs for OpenAPI documentation."})


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend service status."""
    return {
        "status": "healthy",
        "service": "Rule-Based & NLP Hybrid Chatbot",
        "database": "SQLite Connected",
        "security": {
            "api_key_enforced": SecurityConfig.ENFORCE_API_KEY,
            "rate_limit_per_min": SecurityConfig.RATE_LIMIT_REQUESTS,
            "ssh_ed25519_auth_available": True
        }
    }


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    dependencies=[Depends(check_rate_limit), Depends(verify_api_key)],
    tags=["Chat"]
)
async def chat_endpoint(payload: ChatRequest):
    """
    Process user message through NLP & Rule engine with SQL logging.
    Protected by rate limiting, XSS sanitization, and API key verification.
    """
    sanitized_msg = sanitize_input(payload.message)
    if not sanitized_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty after sanitization."
        )

    result = chatbot.respond(sanitized_msg, session_id=payload.session_id)
    return result


@app.post(
    "/api/secure-chat",
    response_model=ChatResponse,
    dependencies=[Depends(check_rate_limit)],
    tags=["SSH Security"]
)
async def secure_chat_endpoint(payload: SecureChatRequest):
    """
    Cryptographically authenticated chat endpoint.
    Requires incoming request payload to be signed by client's Ed25519 SSH private key.
    """
    # 1. Verify Ed25519 cryptographic signature
    raw_payload_bytes = f"{payload.message}:{payload.session_id}".encode("utf-8")
    is_valid = SSHCryptographicSigner.verify_message(
        public_key_openssh=payload.public_key,
        message_bytes=raw_payload_bytes,
        signature_b64=payload.signature
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Ed25519 cryptographic SSH signature. Request may be tampered or unauthenticated."
        )

    # 2. Sanitize and process
    sanitized_msg = sanitize_input(payload.message)
    result = chatbot.respond(sanitized_msg, session_id=payload.session_id)
    return result


# --- SSH Key Management Endpoints ---

@app.post("/api/ssh/generate-keys", tags=["SSH Security"])
async def generate_ssh_keys(key_type: str = "ed25519", comment: str = "chatbot-web-client"):
    """
    Generate fresh SSH keypair (Ed25519 or RSA-4096) directly in browser for secure API signing or server access.
    """
    if key_type.lower() == "rsa":
        keys = SSHKeyManager.generate_rsa_keypair(key_size=4096, comment=comment)
    else:
        keys = SSHKeyManager.generate_ed25519_keypair(comment=comment)
    return keys


@app.get("/api/ssh/tunnel-command", tags=["SSH Security"])
async def get_tunnel_command(remote_host: str = "your-server-ip.com", remote_user: str = "ubuntu", port: int = 8000):
    """Generate sample SSH forwarding commands."""
    return {
        "forward_tunnel": SSHTunnelHelper.get_forward_tunnel_command(
            remote_user=remote_user, remote_host=remote_host, local_port=port, remote_port=port
        ),
        "reverse_tunnel": SSHTunnelHelper.get_reverse_tunnel_command(
            remote_user=remote_user, remote_host=remote_host, local_port=port, remote_port=port
        )
    }


# --- Admin & Booking Endpoints ---

@app.get("/api/bookings", tags=["Bookings"], dependencies=[Depends(verify_api_key)])
async def get_bookings(session_id: Optional[str] = None, limit: int = 50):
    """Retrieve reservations from the SQL database."""
    if session_id:
        booking = chatbot.db.get_latest_booking_by_session(session_id)
        return {"bookings": [booking] if booking else []}
    return {"bookings": chatbot.db.list_all_bookings(limit=limit)}


@app.get("/api/admin/logs", tags=["Admin"], dependencies=[Depends(verify_api_key)])
async def get_audit_logs(limit: int = 50):
    """Retrieve chat audit trail logs from the database."""
    return {
        "total_records": len(chatbot.db.get_all_logs(limit=limit)),
        "logs": chatbot.db.get_all_logs(limit=limit),
        "intent_distribution": chatbot.db.get_intent_distribution()
    }
