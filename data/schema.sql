-- SQL Schema for Rule-Based & NLP Hybrid Chatbot Backend

-- 1. Bookings Table: Persists all customer reservations and statuses
CREATE TABLE IF NOT EXISTS bookings (
    booking_id VARCHAR(32) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    customer_name VARCHAR(128) NOT NULL,
    service VARCHAR(64) NOT NULL,
    party_size INTEGER NOT NULL DEFAULT 1,
    booking_date VARCHAR(64) NOT NULL,
    booking_time VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'CONFIRMED', -- 'CONFIRMED', 'CANCELLED', 'COMPLETED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by session and status
CREATE INDEX IF NOT EXISTS idx_bookings_session_id ON bookings(session_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);

-- 2. Chat Logs Table: Full audit trail of user messages, classifications, and responses
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

-- Index for session history and intent analytics
CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_intent ON chat_logs(intent);
