import uuid
from typing import Dict, Any, Optional, List, Tuple
from src.entity_extractor import EntityExtractor
from src.database import DatabaseManager


class DialogueState:
    """
    Advanced Dialogue State tracking:
    - Active intent & slot values
    - Pending required slot
    - Context stack for nested digressions / side questions
    - Active and historical bookings
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id: str = session_id or str(uuid.uuid4())[:8]
        self.active_intent: Optional[str] = None
        self.slots: Dict[str, Any] = {}
        self.required_slots: List[str] = []
        self.slot_prompts: Dict[str, str] = {}
        self.pending_slot: Optional[str] = None
        self.context_stack: List[Dict[str, Any]] = []
        self.active_booking: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, Any]] = []

    def reset_flow(self):
        """Reset current active flow while preserving context stack."""
        self.active_intent = None
        self.slots = {}
        self.required_slots = []
        self.slot_prompts = {}
        self.pending_slot = None

    def reset_all(self):
        """Full reset of session state and context stack."""
        self.reset_flow()
        self.context_stack = []
        self.active_booking = None
        self.history = []

    def push_context(self):
        """Save current active flow onto stack for a digression."""
        if self.active_intent:
            self.context_stack.append({
                "active_intent": self.active_intent,
                "slots": dict(self.slots),
                "required_slots": list(self.required_slots),
                "slot_prompts": dict(self.slot_prompts),
                "pending_slot": self.pending_slot
            })
            self.reset_flow()

    def pop_context(self) -> bool:
        """Restore previous interrupted flow from stack."""
        if self.context_stack:
            saved = self.context_stack.pop()
            self.active_intent = saved["active_intent"]
            self.slots = saved["slots"]
            self.required_slots = saved["required_slots"]
            self.slot_prompts = saved["slot_prompts"]
            self.pending_slot = saved["pending_slot"]
            return True
        return False


class DialogueManager:
    """
    Advanced Dialogue Manager supporting:
    1. Multi-turn slot filling
    2. In-flight slot corrections (e.g. "actually change date to Friday")
    3. Digression handling & graceful sub-dialogue resumption
    4. SQL database persistence & status tracking
    """

    def __init__(self, intents_config: Dict[str, Any], db_manager: Optional[DatabaseManager] = None):
        self.intents_config = intents_config
        self.intent_by_tag = {i["tag"]: i for i in intents_config.get("intents", [])}
        self.db = db_manager

    def start_intent_flow(self, state: DialogueState, intent_tag: str, initial_text: str) -> Tuple[str, bool]:
        """Initialize a multi-turn slot-filling intent flow."""
        intent_info = self.intent_by_tag.get(intent_tag, {})
        req_slots = intent_info.get("required_slots", [])

        if not req_slots:
            state.reset_flow()
            return "", True

        state.active_intent = intent_tag
        state.required_slots = list(req_slots)
        state.slot_prompts = intent_info.get("slot_prompts", {})
        state.slots = {}

        # Extract entities mentioned in initial trigger message
        extracted = EntityExtractor.extract_all(initial_text)
        for k, v in extracted.items():
            if k in state.required_slots:
                state.slots[k] = v

        return self._process_next_slot(state)

    def check_slot_correction(self, state: DialogueState, user_text: str) -> Optional[str]:
        """
        Check if user is modifying/correcting an already-provided slot value
        (e.g., "actually change to 5 people", "make it Friday", "change name to Sarah").
        """
        text_lower = user_text.lower().strip()
        correction_cues = ["actually", "change", "modify", "instead of", "make it", "no wait", "correction"]
        is_correction = any(cue in text_lower for cue in correction_cues)

        if not is_correction or not state.slots:
            return None

        extracted = EntityExtractor.extract_all(user_text)
        updated_slots = []

        for slot_name, new_val in extracted.items():
            if slot_name in state.required_slots and new_val is not None:
                old_val = state.slots.get(slot_name)
                if old_val != new_val:
                    state.slots[slot_name] = new_val
                    updated_slots.append(f"{slot_name.replace('_', ' ')} to **{new_val}**")

        if updated_slots:
            return f"Got it! I've updated your {', and '.join(updated_slots)}. "

        return None

    def handle_pending_slot(self, state: DialogueState, user_text: str) -> Tuple[str, bool]:
        """
        Process user utterance when a specific slot is expected.
        """
        # 1. Check for cancellation
        user_lower = user_text.lower().strip()
        if user_lower in ["cancel", "stop", "abort", "exit", "nevermind", "quit", "restart"]:
            state.reset_flow()
            return "Sure, I've cancelled the current request. How else can I help you?", True

        # 2. Check for slot corrections across the utterance
        correction_msg = self.check_slot_correction(state, user_text)

        pending = state.pending_slot
        if not pending:
            return self._process_next_slot(state)

        extracted = EntityExtractor.extract_all(user_text)
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

        # Also store any other co-occurring entities
        for k, v in extracted.items():
            if k in state.required_slots and k not in state.slots:
                state.slots[k] = v

        prompt, is_done = self._process_next_slot(state)
        if correction_msg and not is_done:
            prompt = correction_msg + prompt

        return prompt, is_done

    def handle_digression(self, state: DialogueState, side_answer: str) -> str:
        """
        Handles an informational side question mid-flow:
        Answers the question and resumes the pending slot flow smoothly.
        """
        prompt = ""
        if state.pending_slot:
            prompt_text = state.slot_prompts.get(
                state.pending_slot,
                f"Please provide your {state.pending_slot.replace('_', ' ')}:"
            )
            prompt = f"\n\n*(Continuing your {state.active_intent.replace('_', ' ')}: {prompt_text})*"

        return f"{side_answer}{prompt}"

    def _process_next_slot(self, state: DialogueState) -> Tuple[str, bool]:
        """Find next missing required slot or trigger completion."""
        for slot in state.required_slots:
            if slot not in state.slots or state.slots[slot] is None:
                state.pending_slot = slot
                prompt = state.slot_prompts.get(
                    slot,
                    f"Please provide your {slot.replace('_', ' ')}:"
                )
                return prompt, False

        return self._complete_flow(state)

    def _complete_flow(self, state: DialogueState) -> Tuple[str, bool]:
        """Finalize booking, persist to SQL, and generate formatted confirmation."""
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

            if self.db:
                self.db.create_booking(booking_dict)

            receipt = (
                f"🎉 **Booking Confirmed!**\n\n"
                f"• **Confirmation Code**: `{booking_id}`\n"
                f"• **Name**: {name}\n"
                f"• **Service**: {service}\n"
                f"• **Party Size**: {party} {'person' if party == 1 else 'people'}\n"
                f"• **Date & Time**: {date} at {time}\n\n"
                f"Your reservation has been secured. Let me know if you need any other assistance!"
            )
            state.reset_flow()
            return receipt, True

        state.reset_flow()
        return "Your request has been successfully completed!", True

    def handle_check_status(self, state: DialogueState) -> str:
        """Look up reservation details from memory or SQLite database."""
        booking = state.active_booking
        if not booking and self.db:
            db_booking = self.db.get_latest_booking_by_session(state.session_id, status="CONFIRMED")
            if db_booking:
                state.active_booking = {
                    "booking_id": db_booking["booking_id"],
                    "name": db_booking["customer_name"],
                    "service": db_booking["service"],
                    "party_size": db_booking["party_size"],
                    "date": db_booking["booking_date"],
                    "time": db_booking["booking_time"]
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
        """Cancel an active booking in memory and SQLite."""
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
