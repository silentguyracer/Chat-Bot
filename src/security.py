import os
import re
import html
import time
from typing import Dict, List, Tuple, Optional
from fastapi import HTTPException, Security, Request, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Configurable master API key (can be overridden via environment variable)
DEFAULT_API_KEY = os.getenv("CHATBOT_API_KEY", "chatbot-secret-key-2026")


class SecurityConfig:
    """Security configurations for API authentication and rate limiting."""
    ENFORCE_API_KEY = os.getenv("ENFORCE_API_KEY", "false").lower() in ("true", "1", "yes")
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # max requests
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))  # per minute


class RateLimiter:
    """
    Sliding window rate limiter tracking request timestamps per client IP.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests_by_ip: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """
        Check if request is allowed.
        Returns (is_allowed, remaining_requests_in_window).
        """
        now = time.time()
        window_start = now - self.window_seconds

        if client_id not in self.requests_by_ip:
            self.requests_by_ip[client_id] = []

        # Filter out timestamps older than window
        timestamps = [t for t in self.requests_by_ip[client_id] if t > window_start]
        self.requests_by_ip[client_id] = timestamps

        if len(timestamps) >= self.max_requests:
            return False, 0

        self.requests_by_ip[client_id].append(now)
        remaining = self.max_requests - len(self.requests_by_ip[client_id])
        return True, remaining


# Global singleton rate limiter
rate_limiter = RateLimiter(
    max_requests=SecurityConfig.RATE_LIMIT_REQUESTS,
    window_seconds=SecurityConfig.RATE_LIMIT_WINDOW_SECONDS
)


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize and validate user input:
    - Enforces length limit
    - Strips malicious HTML / JavaScript tags (XSS protection)
    - Escapes dangerous characters
    """
    if not text:
        return ""

    # Truncate overly long inputs to prevent DOS
    text = text[:max_length]

    # Remove script tags and html tags completely
    text = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)

    # Escape HTML special chars
    text = html.escape(text.strip())

    return text


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> bool:
    """
    Validate API key from request headers.
    Allows unauthenticated requests if ENFORCE_API_KEY is false, but validates if provided.
    """
    if not SecurityConfig.ENFORCE_API_KEY:
        return True

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required 'X-API-Key' header."
        )

    if api_key != DEFAULT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid 'X-API-Key' provided."
        )

    return True


def check_rate_limit(request: Request):
    """Dependency to enforce rate limiting per client IP address."""
    client_ip = request.client.host if request.client else "unknown_ip"
    allowed, remaining = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a moment before sending more requests."
        )
