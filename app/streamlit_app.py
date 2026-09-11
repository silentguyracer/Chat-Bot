import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
from src.chatbot import HybridChatbot

st.set_page_config(
    page_title="Hybrid Rule-Based & NLP Chatbot with SQL Storage",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
        border-left: 4px solid #1E88E5;
    }
    .badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-rule { background-color: #E3F2FD; color: #0D47A1; }
    .badge-ml { background-color: #E8F5E9; color: #1B5E20; }
    .badge-slot { background-color: #FFF3E0; color: #E65100; }
    .badge-fallback { background-color: #FFEBEE; color: #B71C1C; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_bot():
    return HybridChatbot()


bot = get_bot()

# Initialize session state for Streamlit chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 Hello! I am your AI assistant. How can I help you today? You can ask about our business hours, location, pricing, or book an appointment!"}
    ]
if "last_meta" not in st.session_state:
    st.session_state.last_meta = {
        "intent": "greeting",
        "method": "system_welcome",
        "confidence": 1.0,
        "slots": {},
        "pending_slot": None,
        "active_booking": None,
        "extracted_entities": {}
    }


def send_message(user_text: str):
    if not user_text.strip():
        return

    # Add user message to UI history
    st.session_state.messages.append({"role": "user", "content": user_text})

    # Query chatbot
    res = bot.respond(user_text, session_id="streamlit_user")
    st.session_state.last_meta = res

    # Add bot message to UI history
    st.session_state.messages.append({"role": "assistant", "content": res["response"]})


# Top Navigation Tabs
tab_chat, tab_database = st.tabs(["💬 Chat & Live Inspector", "🗄️ SQL Database & Analytics"])

# ================= TAB 1: CHAT & INSPECTOR =================
with tab_chat:
    col_chat, col_inspector = st.columns([6, 4], gap="large")

    with col_chat:
        st.markdown('<div class="main-header">🤖 NLP & Rule-Based Chatbot</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Hybrid architecture with SQL backend storage for bookings and conversation logs.</div>', unsafe_allow_html=True)

        # Display chat history
        chat_container = st.container(height=480)
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            send_message(prompt)
            st.rerun()

        # Quick test suggestions
        st.markdown("##### 💡 Quick Test Examples:")
        q_col1, q_col2, q_col3, q_col4 = st.columns(4)
        with q_col1:
            if st.button("🕒 Opening Hours", use_container_width=True):
                send_message("What are your opening hours?")
                st.rerun()
        with q_col2:
            if st.button("📅 Book Table (4 pax)", use_container_width=True):
                send_message("Book a table for 4 people tomorrow at 7pm")
                st.rerun()
        with q_col3:
            if st.button("🔤 Typo Test", use_container_width=True):
                send_message("opning our and locashun")
                st.rerun()
        with q_col4:
            if st.button("💲 Pricing Query", use_container_width=True):
                send_message("How much does a consultation cost?")
                st.rerun()

    with col_inspector:
        st.markdown("### 🔍 Live Dialogue Inspector")
        st.caption("Real-time pipeline diagnostics, intent classification, and conversation state.")

        meta = st.session_state.last_meta
        method = meta.get("method", "none")
        intent = meta.get("intent", "none")
        conf = meta.get("confidence", 0.0)

        badge_class = "badge-rule"
        if "ml" in method:
            badge_class = "badge-ml"
        elif "slot" in method:
            badge_class = "badge-slot"
        elif "fallback" in method:
            badge_class = "badge-fallback"

        with st.container():
            st.markdown(f"""
            <div class="metric-card">
                <strong>Detected Intent:</strong> <code>{intent}</code><br>
                <strong>Routing Method:</strong> <span class="badge {badge_class}">{method.upper()}</span><br>
                <strong>Confidence Score:</strong> {conf:.2f}
            </div>
            """, unsafe_allow_html=True)
            st.progress(min(max(float(conf), 0.0), 1.0))

        # Active Slots and State
        st.markdown("#### 🧩 Conversation Slots")
        slots = meta.get("slots", {})
        pending = meta.get("pending_slot")

        if slots:
            st.json(slots)
        else:
            st.info("No active slots in this turn.")

        if pending:
            st.warning(f"⏳ **Waiting for slot:** `{pending}`")

        # Extracted Entities
        entities = meta.get("extracted_entities", {})
        if entities:
            st.markdown("#### 🏷️ Entities in Last Utterance")
            st.write(entities)

        # Active Booking Card
        booking = meta.get("active_booking")
        if booking:
            st.markdown("#### 🎟️ Active Booking")
            st.success(
                f"**ID:** `{booking.get('booking_id')}`\n\n"
                f"**Name:** {booking.get('name')}\n\n"
                f"**Service:** {booking.get('service')}\n\n"
                f"**Party:** {booking.get('party_size')} guests\n\n"
                f"**Time:** {booking.get('date')} at {booking.get('time')}"
            )

        # Reset Button
        st.divider()
        if st.button("🔄 Reset Conversation State", use_container_width=True):
            bot.reset_session("streamlit_user")
            st.session_state.messages = [
                {"role": "assistant", "content": "👋 Conversation has been reset. How can I help you today?"}
            ]
            st.session_state.last_meta = {
                "intent": "reset",
                "method": "reset",
                "confidence": 1.0,
                "slots": {},
                "pending_slot": None,
                "active_booking": None,
                "extracted_entities": {}
            }
            st.rerun()

# ================= TAB 2: SQL DATABASE VIEWER =================
with tab_database:
    st.markdown("### 🗄️ SQL Database Storage & Audit Logs")
    st.caption("Live persistent data stored in `data/chatbot.db` (SQLite).")

    m_col1, m_col2, m_col3 = st.columns(3)
    bookings_list = bot.db.list_all_bookings(limit=100)
    all_logs = bot.db.get_all_logs(limit=100)
    intent_dist = bot.db.get_intent_distribution()

    with m_col1:
        st.metric("Total Bookings", len(bookings_list))
    with m_col2:
        st.metric("Total Logged Turns", len(all_logs))
    with m_col3:
        st.metric("Unique Intents Recognized", len(intent_dist))

    st.markdown("---")

    col_b, col_l = st.columns(2)

    with col_b:
        st.markdown("#### 📋 Bookings Table (`bookings`)")
        if bookings_list:
            df_b = pd.DataFrame(bookings_list)
            st.dataframe(df_b, use_container_width=True, hide_index=True)
        else:
            st.info("No bookings recorded in the database yet. Try booking an appointment!")

    with col_l:
        st.markdown("#### 📊 Intent Frequency Distribution")
        if intent_dist:
            df_dist = pd.DataFrame(list(intent_dist.items()), columns=["Intent", "Count"]).set_index("Intent")
            st.bar_chart(df_dist)
        else:
            st.info("No intent logs available yet.")

    st.markdown("---")
    st.markdown("#### 📝 Chat Audit Trail (`chat_logs`)")
    if all_logs:
        df_logs = pd.DataFrame(all_logs)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No chat logs recorded yet.")
