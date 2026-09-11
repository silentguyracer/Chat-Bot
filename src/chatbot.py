import json
import random
from pathlib import Path
from typing import Dict, Any, Optional

from src.matcher import RuleMatcher
from src.intent_classifier import MLIntentClassifier
from src.entity_extractor import EntityExtractor
from src.dialogue_manager import DialogueManager, DialogueState
from src.database import DatabaseManager


class HybridChatbot:
    """
    Unified Chatbot Pipeline:
    1. Checks ongoing multi-turn slot filling (Dialogue State)
    2. Runs Rule Matcher (Exact -> Regex -> Keyword Overlap -> Fuzzy)
    3. If rule confidence is low or fallback, evaluates ML Classifier (TF-IDF + ML)
    4. Extracts entities and coordinates with Dialogue Manager
    5. Persists bookings and audit logs to SQLite Database
    6. Formats response and returns diagnostics
    """

    def __init__(
        self,
        intents_path: str = "data/intents.json",
        training_csv_path: str = "data/training_examples.csv",
        db_path: str = "data/chatbot.db"
    ):
        self.intents_path = Path(intents_path)
        with open(self.intents_path, "r", encoding="utf-8") as f:
            self.intents_config = json.load(f)

        self.intent_by_tag = {
            intent["tag"]: intent for intent in self.intents_config.get("intents", [])
        }

        # Initialize SQLite database manager
        self.db = DatabaseManager(db_path=db_path)

        # Initialize engines
        self.rule_matcher = RuleMatcher(intents_path=str(self.intents_path))
        self.ml_classifier = MLIntentClassifier(
            training_csv_path=training_csv_path,
            intents_json_path=str(self.intents_path)
        )
        self.dialogue_manager = DialogueManager(self.intents_config, db_manager=self.db)
        self.sessions: Dict[str, DialogueState] = {}

    def get_or_create_state(self, session_id: Optional[str] = None) -> DialogueState:
        """Retrieve existing dialogue state or create a new one."""
        sid = session_id or "default"
        if sid not in self.sessions:
            self.sessions[sid] = DialogueState(session_id=sid)
        return self.sessions[sid]

    def reset_session(self, session_id: Optional[str] = None):
        """Reset conversation session."""
        sid = session_id or "default"
        if sid in self.sessions:
            self.sessions[sid].reset_all()

    def _get_static_response(self, intent_tag: str) -> str:
        """Get random response from intents.json."""
        intent = self.intent_by_tag.get(intent_tag)
        if intent and intent.get("responses"):
            return random.choice(intent["responses"])
        fallback = self.intent_by_tag.get("fallback", {})
        responses = fallback.get("responses", ["I'm not sure I understand. Could you rephrase?"])
        return random.choice(responses)

    def respond(self, user_input: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user message, coordinate state, log to SQL database, and return response payload.
        """
        sid = session_id or "default"
        state = self.get_or_create_state(sid)
        clean_input = user_input.strip()

        if not clean_input:
            return {
                "response": "Please type a message to start chatting!",
                "intent": "none",
                "method": "none",
                "confidence": 0.0,
                "slots": state.slots,
                "pending_slot": state.pending_slot,
                "active_booking": state.active_booking
            }

        # Handle global commands
        if clean_input.lower() in ["/reset", "restart", "start over"]:
            state.reset_all()
            bot_msg = "🔄 Session restarted. How can I help you today?"
            self.db.log_chat_turn(sid, user_input, bot_msg, "reset", "system_command", 1.0, {})
            return {
                "response": bot_msg,
                "intent": "reset",
                "method": "system_command",
                "confidence": 1.0,
                "slots": {},
                "pending_slot": None,
                "active_booking": None
            }

        # 1. Check if we are in an active slot-filling flow
        if state.active_intent and state.pending_slot:
            # Check if user is asking to abort/cancel
            if clean_input.lower() in ["cancel", "stop", "nevermind"]:
                state.reset_flow()
                bot_msg = "Booking cancelled. What else would you like to do?"
                self.db.log_chat_turn(sid, user_input, bot_msg, "cancel_flow", "dialogue_manager", 1.0, state.slots)
                return {
                    "response": bot_msg,
                    "intent": "cancel_flow",
                    "method": "dialogue_manager",
                    "confidence": 1.0,
                    "slots": state.slots,
                    "pending_slot": None,
                    "active_booking": state.active_booking
                }

            bot_msg, is_done = self.dialogue_manager.handle_pending_slot(state, clean_input)
            self.db.log_chat_turn(sid, user_input, bot_msg, state.active_intent or "book_appointment", "slot_filling", 1.0, state.slots)
            return {
                "response": bot_msg,
                "intent": state.active_intent or "book_appointment",
                "method": "slot_filling",
                "confidence": 1.0,
                "slots": dict(state.slots),
                "pending_slot": state.pending_slot,
                "active_booking": state.active_booking
            }

        # 2. Run Rule Matching Engine (v1, v2, v3)
        rule_tag, rule_conf, rule_method = self.rule_matcher.match(clean_input)

        chosen_tag = rule_tag
        chosen_conf = rule_conf
        chosen_method = f"rule_{rule_method}"

        # 3. Hybrid ML Classification Fallback (v4)
        if rule_tag == "fallback" or rule_conf < 0.60:
            ml_tag, ml_conf = self.ml_classifier.predict(clean_input)
            if ml_tag != "fallback" and ml_conf > rule_conf:
                chosen_tag = ml_tag
                chosen_conf = ml_conf
                chosen_method = "ml_classifier"

        # 4. Route intent action & generate response
        if chosen_tag == "book_appointment":
            bot_msg, is_done = self.dialogue_manager.start_intent_flow(state, chosen_tag, clean_input)
        elif chosen_tag == "check_booking_status":
            bot_msg = self.dialogue_manager.handle_check_status(state)
        elif chosen_tag == "cancel_booking":
            bot_msg = self.dialogue_manager.handle_cancel_booking(state)
        else:
            bot_msg = self._get_static_response(chosen_tag)

        # Extract entities for diagnostics
        extracted_entities = EntityExtractor.extract_all(clean_input)

        # Log turn to memory and SQL database
        turn_data = {
            "user": user_input,
            "bot": bot_msg,
            "intent": chosen_tag,
            "method": chosen_method,
            "confidence": chosen_conf,
            "extracted_slots": extracted_entities
        }
        state.history.append(turn_data)

        # Persist audit trail to SQLite
        self.db.log_chat_turn(
            session_id=sid,
            user_message=user_input,
            bot_response=bot_msg,
            intent=chosen_tag,
            method=chosen_method,
            confidence=chosen_conf,
            slots=dict(state.slots)
        )

        return {
            "response": bot_msg,
            "intent": chosen_tag,
            "method": chosen_method,
            "confidence": chosen_conf,
            "slots": dict(state.slots),
            "pending_slot": state.pending_slot,
            "active_booking": state.active_booking,
            "extracted_entities": extracted_entities
        }
