from typing import Dict, Any, Optional, List, Tuple
import uuid
from src.entity_extractor import EntityExtractor
from src.database import DatabaseManager


class DialogueState:
    """Represents the dialogue context of a conversation session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id: str = session_id or str(uuid.uuid4())[:8]
        self.active_intent: Optional[str] = None
        self.slots: Dict[str, Any] = {}
        self.required_slots: List[str] = []
        self.slot_prompts: Dict[str, str] = {}
        self.pending_slot: Optional[str] = None
        self.active_booking: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, Any]] = []

    def reset_flow(self):
        """Reset ongoing slot-filling flow while keeping history and completed bookings."""
        self.active_intent = None
        self.slots = {}
        self.required_slots = []
        self.slot_prompts = {}
        self.pending_slot = None

    def reset_all(self):
        """Full reset of the dialogue state."""
        self.reset_flow()
        self.active_booking = None
        self.history = []


class DialogueManager:
    """
    Manages multi-turn conversation flow, slot filling, and contextual memory
    with persistent SQLite database backend.
    """

    def __init__(self, intents_config: Dict[str, Any], db_manager: Optional[DatabaseManager] = None):
        self.intents_config = intents_config
        self.intent_by_tag = {i["tag"]: i for i in intents_config.get("intents", [])}
        self.db = db_manager

    def start_intent_flow(self, state: DialogueState, intent_tag: str, initial_text: str) -> Tuple[str, bool]:
        """
        Initialize a multi-turn slot-filling intent flow (e.g. booking).
        Returns (response_message, is_completed).
        """
        intent_info = self.intent_by_tag.get(intent_tag, {})
        req_slots = intent_info.get("required_slots", [])

        if not req_slots:
            state.reset_flow()
            return "", True

        state.active_intent = intent_tag
        state.required_slots = list(req_slots)
        state.slot_prompts = intent_info.get("slot_prompts", {})
        state.slots = {}

        # Extract whatever entities were already mentioned in the initial message
        extracted = EntityExtractor.extract_all(initial_text)
        for k, v in extracted.items():
            if k in state.required_slots:
                state.slots[k] = v

        # Find the first unfilled slot
        return self._process_next_slot(state)

    def handle_pending_slot(self, state: DialogueState, user_text: str) -> Tuple[str, bool]:
        """
        Process user response when a specific slot is expected.
        """
        pending = state.pending_slot
        if not pending:
            return self._process_next_slot(state)

        # Check if user wants to cancel out of the flow
        user_lower = user_text.lower().strip()
        if user_lower in ["cancel", "stop", "abort", "exit", "nevermind", "quit"]:
            state.reset_flow()
            return "Sure, I've cancelled the current request. How else can I help you?", True

        # Extract value for pending slot
        extracted = EntityExtractor.extract_all(user_text)

        # Handle specific slot extraction logic
        val = None
        if pending == "party_size":
            val = extracted.get("party_size") or EntityExtractor.extract_party_size(user_text)
        elif pending == "date":
            val = extracted.get("date") or EntityExtractor.extract_date(user_text) or user_text.strip()
        elif pending == "time":
            val = extracted.get("time") or EntityExtractor.extract_time(user_text) or user_text.strip()
        elif pending == "service":
            val = extracted.get("service") or EntityExtractor.extract_service(user_text) or user_text.strip().capitalize()
        elif pending == "name":
            val = extracted.get("name") or EntityExtractor.extract_name(user_text) or user_text.strip().title()
        else:
            val = extracted.get(pending) or user_text.strip()

        if val is not None:
            state.slots[pending] = val
            state.pending_slot = None

        # Check if any other slots were also provided in the same message
        for k, v in extracted.items():
            if k in state.required_slots and k not in state.slots:
                state.slots[k] = v

        return self._process_next_slot(state)

    def _process_next_slot(self, state: DialogueState) -> Tuple[str, bool]:
        """Find the next missing slot, prompt for it, or complete if all are filled."""
        for slot in state.required_slots:
            if slot not in state.slots:
                state.pending_slot = slot
                prompt = state.slot_prompts.get(
                    slot,
                    f"Please provide your {slot.replace('_', ' ')}:"
                )
                return prompt, False

        # All slots filled! Complete the flow
        return self._complete_flow(state)

    def _complete_flow(self, state: DialogueState) -> Tuple[str, bool]:
        """Format the completion confirmation message and persist the booking to SQL."""
        if state.active_intent == "book_appointment":
            booking_id = f"BK-{uuid.uuid4().hex[:6].upper()}"
            name = state.slots.get("name", "Valued Guest")
            service = state.slots.get("service", "General Appointment")
            party = state.slots.get("party_size", 1)
            date = state.slots.get("date", "Upcoming")
            time = state.slots.get("time", "Scheduled Time")

            booking_dict = {
                "booking_id": booking_id,
                "session_id": state.session_id,
                "name": name,
                "service": service,
                "party_size": party,
                "date": date,
                "time": time,
                "status": "CONFIRMED"
            }

            state.active_booking = booking_dict

            # Persist to SQLite database
            if self.db:
                self.db.create_booking(booking_dict)

            receipt = (
                f"🎉 **Booking Confirmed!**\n\n"
                f"• **Confirmation Code**: `{booking_id}`\n"
                f"• **Name**: {name}\n"
                f"• **Service**: {service}\n"
                f"• **Party Size**: {party} {'person' if party == 1 else 'people'}\n"
                f"• **Date & Time**: {date} at {time}\n\n"
                f"A confirmation reference has been stored in our database. Let me know if you need any other assistance!"
            )
            state.reset_flow()
            return receipt, True

        state.reset_flow()
        return "Your request has been successfully completed!", True

    def handle_check_status(self, state: DialogueState) -> str:
        """Handle check_booking_status intent with SQL fallback."""
        booking = state.active_booking
        if not booking and self.db:
            booking = self.db.get_latest_booking_by_session(state.session_id, status="CONFIRMED")
            if booking:
                # Map SQL columns to dict format
                state.active_booking = {
                    "booking_id": booking["booking_id"],
                    "name": booking["customer_name"],
                    "service": booking["service"],
                    "party_size": booking["party_size"],
                    "date": booking["booking_date"],
                    "time": booking["booking_time"]
                }
                booking = state.active_booking

        if booking:
            return (
                f"📋 **Your Active Reservation:**\n\n"
                f"• **Booking ID**: `{booking['booking_id']}`\n"
                f"• **Name**: {booking['name']}\n"
                f"• **Service**: {booking['service']}\n"
                f"• **Party**: {booking['party_size']} guests\n"
                f"• **Date & Time**: {booking['date']} at {booking['time']}\n"
            )
        return "You currently do not have any active bookings in this session. Say **'book an appointment'** to schedule one!"

    def handle_cancel_booking(self, state: DialogueState) -> str:
        """Handle cancel_booking intent with SQL database update."""
        booking = state.active_booking
        if not booking and self.db:
            db_booking = self.db.get_latest_booking_by_session(state.session_id, status="CONFIRMED")
            if db_booking:
                booking = {"booking_id": db_booking["booking_id"]}

        if booking:
            b_id = booking['booking_id']
            state.active_booking = None
            if self.db:
                self.db.update_booking_status(b_id, "CANCELLED")
            return f"✅ Your booking (`{b_id}`) has been cancelled. No cancellation fees apply."

        return "There are no active reservations on file to cancel."
