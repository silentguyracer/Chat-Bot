import time
from typing import Dict, Any, List, Optional
from collections import defaultdict


class ConversationAnalytics:
    """
    In-memory and SQL-backed conversation analytics engine:
    Tracks dialogue funnels, slot completion rates, average resolution time,
    sentiment distributions, and human escalation queues.
    """

    def __init__(self):
        self.session_start_times: Dict[str, float] = {}
        self.session_turn_counts: Dict[str, int] = defaultdict(int)
        self.funnels: Dict[str, Dict[str, int]] = {
            "book_appointment": {"started": 0, "completed": 0, "cancelled": 0}
        }
        self.sentiment_counts: Dict[str, int] = defaultdict(int)
        self.escalations: List[Dict[str, Any]] = []

    def log_turn(self, session_id: str, intent: str, sentiment: str, is_escalated: bool = False, message: str = ""):
        """Record a single conversational turn."""
        if session_id not in self.session_start_times:
            self.session_start_times[session_id] = time.time()

        self.session_turn_counts[session_id] += 1
        self.sentiment_counts[sentiment] += 1

        if is_escalated:
            self.escalations.append({
                "session_id": session_id,
                "timestamp": time.time(),
                "trigger_message": message,
                "status": "PENDING_AGENT_HANDOFF"
            })

    def log_intent_started(self, intent: str):
        """Record when a multi-turn flow starts."""
        if intent in self.funnels:
            self.funnels[intent]["started"] += 1

    def log_intent_completed(self, intent: str):
        """Record when a multi-turn flow successfully completes."""
        if intent in self.funnels:
            self.funnels[intent]["completed"] += 1

    def log_intent_cancelled(self, intent: str):
        """Record when a user aborts a multi-turn flow."""
        if intent in self.funnels:
            self.funnels[intent]["cancelled"] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Generate high-level conversion and operational metrics summary."""
        total_sessions = len(self.session_turn_counts)
        total_turns = sum(self.session_turn_counts.values())
        avg_turns_per_session = round(total_turns / total_sessions, 2) if total_sessions > 0 else 0.0

        booking_funnel = self.funnels.get("book_appointment", {"started": 0, "completed": 0})
        started = booking_funnel["started"]
        completed = booking_funnel["completed"]
        completion_rate = round((completed / started) * 100, 1) if started > 0 else 0.0

        return {
            "total_sessions": total_sessions,
            "total_turns": total_turns,
            "avg_turns_per_session": avg_turns_per_session,
            "booking_funnel": {
                "started": started,
                "completed": completed,
                "cancelled": booking_funnel.get("cancelled", 0),
                "completion_rate_pct": completion_rate
            },
            "sentiment_distribution": dict(self.sentiment_counts),
            "pending_escalations": len([e for e in self.escalations if e["status"] == "PENDING_AGENT_HANDOFF"]),
            "recent_escalations": self.escalations[-5:]
        }


# Global singleton analytics engine
analytics_engine = ConversationAnalytics()
