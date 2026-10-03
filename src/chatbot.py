import json
import random
from pathlib import Path
from typing import Dict, Any, Optional

from src.matcher import RuleMatcher
from src.intent_classifier import MLIntentClassifier
from src.entity_extractor import EntityExtractor
from src.dialogue_manager import DialogueManager, DialogueState
from src.database import DatabaseManager
from src.sentiment_analyzer import SentimentAnalyzer
from src.analytics import analytics_engine


class HybridChatbot:
    """
    Advanced Hybrid Chatbot Pipeline:
    1. Sentiment, Emotion & Frustration Analysis
    2. Sub-Dialogue & Digression Handling (Stack-Based Interruption Memory)
    3. Multi-Turn Slot Filling & In-Flight Slot Corrections
    4. 4-Tier Rule Matching Engine (Exact -> Regex -> Keyword Overlap -> Fuzzy)
    5. TF-IDF + Logistic Regression ML Intent Classification Fallback
    6. SQLite Audit Logging & Real-Time Operational Analytics
    """

    INFORMATIONAL_INTENTS = {
        "business_hours", "location", "pricing", "cancellation_policy",
        "bot_identity", "help"
    }

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

        # Initialize SQLite database & engines
        self.db = DatabaseManager(db_path=db_path)
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
        Process user message through full advanced NLP, sentiment, digression, and state pipeline.
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
                "sentiment": "neutral",
                "slots": state.slots,
                "pending_slot": state.pending_slot,
                "active_booking": state.active_booking
            }

        # 1. Sentiment & Frustration Analysis
        sentiment_info = SentimentAnalyzer.analyze(clean_input)
        empathy_prefix = sentiment_info.get("empathy_prefix", "")
        needs_escalation = sentiment_info.get("needs_escalation", False)

        # Handle global reset commands
        if clean_input.lower() in ["/reset", "restart", "start over"]:
            state.reset_all()
            bot_msg = "🔄 Session restarted. How can I help you today?"
            self.db.log_chat_turn(sid, user_input, bot_msg, "reset", "system_command", 1.0, {})
            analytics_engine.log_turn(sid, "reset", sentiment_info["sentiment"], False, clean_input)
            return {
                "response": bot_msg,
                "intent": "reset",
                "method": "system_command",
                "confidence": 1.0,
                "sentiment": sentiment_info["sentiment"],
                "slots": {},
                "pending_slot": None,
                "active_booking": None
            }

        # Handle explicit human agent escalation requests
        if needs_escalation and ("human" in clean_input.lower() or "agent" in clean_input.lower()):
            state.reset_flow()
            bot_msg = (
                "🚨 I have flagged this session for our human support team. "
                "A live representative will review your message shortly. In the meantime, how else can I assist you?"
            )
            self.db.log_chat_turn(sid, user_input, bot_msg, "human_escalation", "sentiment_escalation", 1.0, state.slots)
            analytics_engine.log_turn(sid, "human_escalation", "frustrated", True, clean_input)
            return {
                "response": bot_msg,
                "intent": "human_escalation",
                "method": "sentiment_escalation",
                "confidence": 1.0,
                "sentiment": "frustrated",
                "slots": state.slots,
                "pending_slot": None,
                "active_booking": state.active_booking
            }

        # 2. Check active slot-filling flow
        if state.active_intent and state.pending_slot:
            pending = state.pending_slot
            extracted = EntityExtractor.extract_all(clean_input)

            # Does this utterance provide the pending slot?
            is_answering_pending = False
            if pending == "party_size" and (extracted.get("party_size") or EntityExtractor.extract_party_size(clean_input)):
                is_answering_pending = True
            elif pending == "date" and (extracted.get("date") or EntityExtractor.extract_date(clean_input)):
                is_answering_pending = True
            elif pending == "time" and (extracted.get("time") or EntityExtractor.extract_time(clean_input)):
                is_answering_pending = True
            elif pending == "service" and (extracted.get("service") or EntityExtractor.extract_service(clean_input) or clean_input.lower() in ["consultation", "table", "meeting", "support"]):
                is_answering_pending = True
            elif pending == "name" and len(clean_input.split()) <= 4 and not any(q in clean_input.lower() for q in ["where", "how much", "what time", "hours", "when"]):
                is_answering_pending = True

            # If user asks an informational FAQ question instead of answering
            if not is_answering_pending:
                rule_tag, rule_conf, _ = self.rule_matcher.match(clean_input)
                if rule_tag in self.INFORMATIONAL_INTENTS and rule_conf >= 0.75:
                    side_answer = self._get_static_response(rule_tag)
                    bot_msg = self.dialogue_manager.handle_digression(state, side_answer)
                    self.db.log_chat_turn(sid, user_input, bot_msg, f"digression_{rule_tag}", "digression_handler", rule_conf, state.slots)
                    analytics_engine.log_turn(sid, f"digression_{rule_tag}", sentiment_info["sentiment"], False, clean_input)
                    return {
                        "response": f"{empathy_prefix}{bot_msg}",
                        "intent": f"digression_{rule_tag}",
                        "method": "digression_handler",
                        "confidence": rule_conf,
                        "sentiment": sentiment_info["sentiment"],
                        "slots": dict(state.slots),
                        "pending_slot": state.pending_slot,
                        "active_booking": state.active_booking
                    }

            # Normal slot filling / in-flight slot correction
            bot_msg, is_done = self.dialogue_manager.handle_pending_slot(state, clean_input)
            if is_done and state.active_booking:
                analytics_engine.log_intent_completed("book_appointment")

            full_resp = f"{empathy_prefix}{bot_msg}" if empathy_prefix else bot_msg
            self.db.log_chat_turn(sid, user_input, full_resp, state.active_intent or "book_appointment", "slot_filling", 1.0, state.slots)
            analytics_engine.log_turn(sid, state.active_intent or "book_appointment", sentiment_info["sentiment"], False, clean_input)

            return {
                "response": full_resp,
                "intent": state.active_intent or "book_appointment",
                "method": "slot_filling",
                "confidence": 1.0,
                "sentiment": sentiment_info["sentiment"],
                "slots": dict(state.slots),
                "pending_slot": state.pending_slot,
                "active_booking": state.active_booking
            }

        # 3. Intent Classification (4-Tier Rule Matcher + ML Fallback)
        rule_tag, rule_conf, rule_method = self.rule_matcher.match(clean_input)
        chosen_tag = rule_tag
        chosen_conf = rule_conf
        chosen_method = f"rule_{rule_method}"

        if rule_tag == "fallback" or rule_conf < 0.60:
            ml_tag, ml_conf = self.ml_classifier.predict(clean_input)
            if ml_tag != "fallback" and ml_conf > rule_conf:
                chosen_tag = ml_tag
                chosen_conf = ml_conf
                chosen_method = "ml_classifier"

        # 4. Route intent action
        if chosen_tag == "book_appointment":
            analytics_engine.log_intent_started("book_appointment")
            bot_msg, is_done = self.dialogue_manager.start_intent_flow(state, chosen_tag, clean_input)
        elif chosen_tag == "check_booking_status":
            bot_msg = self.dialogue_manager.handle_check_status(state)
        elif chosen_tag == "cancel_booking":
            bot_msg = self.dialogue_manager.handle_cancel_booking(state)
        else:
            bot_msg = self._get_static_response(chosen_tag)

        if empathy_prefix and chosen_tag != "greeting":
            bot_msg = f"{empathy_prefix}{bot_msg}"

        extracted_entities = EntityExtractor.extract_all(clean_input)

        # Log turn to SQLite and analytics
        self.db.log_chat_turn(
            session_id=sid,
            user_message=user_input,
            bot_response=bot_msg,
            intent=chosen_tag,
            method=chosen_method,
            confidence=chosen_conf,
            slots=dict(state.slots)
        )
        analytics_engine.log_turn(sid, chosen_tag, sentiment_info["sentiment"], needs_escalation, clean_input)

        return {
            "response": bot_msg,
            "intent": chosen_tag,
            "method": chosen_method,
            "confidence": chosen_conf,
            "sentiment": sentiment_info["sentiment"],
            "slots": dict(state.slots),
            "pending_slot": state.pending_slot,
            "active_booking": state.active_booking,
            "extracted_entities": extracted_entities
        }
