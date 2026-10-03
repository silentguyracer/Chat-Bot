import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Depends, Request, WebSocket, WebSocketDisconnect, HTTPException, Header, status
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
from src.analytics import analytics_engine

app = FastAPI(
    title="Advanced Rule-Based & NLP Hybrid Chatbot API",
    description="Advanced conversational API with WebSockets, Voice integration, sentiment analysis, digression handling, SSH Ed25519 authentication, and SQL persistence.",
    version="2.0.0"
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
    sentiment: Optional[str] = "neutral"
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
        "service": "Advanced Hybrid NLP Chatbot v2.0",
        "database": "SQLite Connected",
        "features": {
            "websockets": True,
            "sentiment_analysis": True,
            "digression_handling": True,
            "ssh_ed25519_auth": True
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
    Process user message through advanced NLP, sentiment, digression, and rule engine.
    """
    sanitized_msg = sanitize_input(payload.message)
    if not sanitized_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty after sanitization."
        )

    result = chatbot.respond(sanitized_msg, session_id=payload.session_id)
    return result


# --- Real-Time Full-Duplex WebSocket Endpoint ---

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    Full-duplex real-time streaming WebSocket endpoint.
    Receives JSON messages: {"message": "hello"}
    Sends real-time response payload + typing simulation events.
    """
    await websocket.accept()
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                data = json.loads(data_text)
                user_msg = data.get("message", "").strip()
            except json.JSONDecodeError:
                user_msg = data_text.strip()

            if not user_msg:
                continue

            # Emit typing indicator event
            await websocket.send_json({"type": "typing", "is_typing": True})
            await asyncio.sleep(0.3)

            # Process through hybrid chatbot
            sanitized = sanitize_input(user_msg)
            result = chatbot.respond(sanitized, session_id=session_id)

            # Emit bot response event
            await websocket.send_json({
                "type": "message",
                "payload": result
            })
    except WebSocketDisconnect:
        pass


@app.post(
    "/api/secure-chat",
    response_model=ChatResponse,
    dependencies=[Depends(check_rate_limit)],
    tags=["SSH Security"]
)
async def secure_chat_endpoint(payload: SecureChatRequest):
    """
    Cryptographically authenticated chat endpoint using Ed25519 SSH signature verification.
    """
    raw_payload_bytes = f"{payload.message}:{payload.session_id}".encode("utf-8")
    is_valid = SSHCryptographicSigner.verify_message(
        public_key_openssh=payload.public_key,
        message_bytes=raw_payload_bytes,
        signature_b64=payload.signature
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Ed25519 cryptographic SSH signature."
        )

    sanitized_msg = sanitize_input(payload.message)
    result = chatbot.respond(sanitized_msg, session_id=payload.session_id)
    return result


# --- SSH Key Management Endpoints ---

@app.post("/api/ssh/generate-keys", tags=["SSH Security"])
async def generate_ssh_keys(key_type: str = "ed25519", comment: str = "chatbot-web-client"):
    """Generate fresh SSH keypair (Ed25519 or RSA-4096)."""
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


# --- Analytics & Operations Endpoints ---

@app.get("/api/analytics/dashboard", tags=["Analytics"])
async def get_analytics():
    """Retrieve dialogue funnels, completion rates, and sentiment statistics."""
    return analytics_engine.get_summary()


@app.get("/api/escalations", tags=["Analytics"])
async def get_escalations():
    """Retrieve sessions flagged for human agent handoff."""
    return {
        "escalations": analytics_engine.escalations
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
