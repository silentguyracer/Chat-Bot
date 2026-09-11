import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class DatabaseManager:
    """
    SQLite backend database manager for persisting bookings,
    conversation logs, and session analytics.
    """

    def __init__(self, db_path: str = "data/chatbot.db", schema_path: str = "data/schema.sql"):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database tables using schema file or embedded DDL."""
        with self.get_connection() as conn:
            if self.schema_path.exists():
                with open(self.schema_path, "r", encoding="utf-8") as f:
                    conn.executescript(f.read())
            else:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id VARCHAR(32) PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    customer_name VARCHAR(128) NOT NULL,
                    service VARCHAR(64) NOT NULL,
                    party_size INTEGER NOT NULL DEFAULT 1,
                    booking_date VARCHAR(64) NOT NULL,
                    booking_time VARCHAR(64) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'CONFIRMED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chat_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(64) NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    intent VARCHAR(64) NOT NULL,
                    method VARCHAR(64) NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    slots_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
            conn.commit()

    # --- Booking Operations ---

    def create_booking(self, booking_data: Dict[str, Any]) -> bool:
        """Insert a new booking record into the database."""
        query = """
        INSERT INTO bookings (
            booking_id, session_id, customer_name, service,
            party_size, booking_date, booking_time, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.utcnow().isoformat()
        try:
            with self.get_connection() as conn:
                conn.execute(query, (
                    booking_data["booking_id"],
                    booking_data.get("session_id", "default"),
                    booking_data.get("name", "Guest"),
                    booking_data.get("service", "General"),
                    int(booking_data.get("party_size", 1)),
                    str(booking_data.get("date", "N/A")),
                    str(booking_data.get("time", "N/A")),
                    booking_data.get("status", "CONFIRMED"),
                    now,
                    now
                ))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error on create_booking: {e}")
            return False

    def get_booking_by_id(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve booking by its unique booking_id."""
        query = "SELECT * FROM bookings WHERE booking_id = ?"
        with self.get_connection() as conn:
            row = conn.execute(query, (booking_id,)).fetchone()
            if row:
                return dict(row)
        return None

    def get_latest_booking_by_session(self, session_id: str, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve the latest booking for a session (optionally filtered by status)."""
        if status:
            query = "SELECT * FROM bookings WHERE session_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1"
            params = (session_id, status)
        else:
            query = "SELECT * FROM bookings WHERE session_id = ? ORDER BY created_at DESC LIMIT 1"
            params = (session_id,)

        with self.get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            if row:
                return dict(row)
        return None

    def update_booking_status(self, booking_id: str, new_status: str) -> bool:
        """Update status of a booking (e.g., 'CANCELLED', 'CONFIRMED')."""
        query = "UPDATE bookings SET status = ?, updated_at = ? WHERE booking_id = ?"
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(query, (new_status, now, booking_id))
            conn.commit()
            return cursor.rowcount > 0

    def list_all_bookings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve all bookings in descending order of creation."""
        query = "SELECT * FROM bookings ORDER BY created_at DESC LIMIT ?"
        with self.get_connection() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # --- Chat Logging & Analytics ---

    def log_chat_turn(
        self,
        session_id: str,
        user_message: str,
        bot_response: str,
        intent: str,
        method: str,
        confidence: float,
        slots: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Log a complete conversation turn to the database."""
        query = """
        INSERT INTO chat_logs (
            session_id, user_message, bot_response, intent, method, confidence, slots_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        slots_str = json.dumps(slots or {})
        try:
            with self.get_connection() as conn:
                conn.execute(query, (
                    session_id,
                    user_message,
                    bot_response,
                    intent,
                    method,
                    float(confidence),
                    slots_str
                ))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error on log_chat_turn: {e}")
            return False

    def get_session_logs(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch chat history logs for a specific session."""
        query = "SELECT * FROM chat_logs WHERE session_id = ? ORDER BY log_id ASC LIMIT ?"
        with self.get_connection() as conn:
            rows = conn.execute(query, (session_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_all_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch latest chat logs across all sessions."""
        query = "SELECT * FROM chat_logs ORDER BY log_id DESC LIMIT ?"
        with self.get_connection() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_intent_distribution(self) -> Dict[str, int]:
        """Get aggregated count of queries by intent."""
        query = "SELECT intent, COUNT(*) as count FROM chat_logs GROUP BY intent ORDER BY count DESC"
        with self.get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return {r["intent"]: r["count"] for r in rows}
