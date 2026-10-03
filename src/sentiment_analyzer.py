import re
from typing import Dict, Any, Tuple


class SentimentAnalyzer:
    """
    Contextual Sentiment & Emotion Analyzer for Chatbots:
    Detects polarity (Positive, Neutral, Negative, Frustrated/Angry),
    computes sentiment intensity scores, and determines if human agent escalation is required.
    """

    POSITIVE_WORDS = {
        "great", "good", "excellent", "awesome", "amazing", "wonderful", "fantastic",
        "love", "perfect", "helpful", "thank", "thanks", "appreciate", "nice", "glad",
        "super", "brilliant", "pleased", "happy", "fast", "easy"
    }

    NEGATIVE_WORDS = {
        "bad", "terrible", "horrible", "awful", "poor", "slow", "annoying", "disappointed",
        "useless", "broken", "wrong", "hate", "issue", "problem", "difficult", "confusing",
        "error", "bug", "ridiculous", "worst", "waste"
    }

    FRUSTRATED_WORDS = {
        "stupid", "idiot", "angry", "furious", "unacceptable", "nonsense", "human",
        "agent", "talk to a person", "real person", "representative", "manager", "support agent",
        "useless bot", "shut up", "worst service", "waste of time", "fed up", "garbage"
    }

    EMPATHY_PREFIXES = {
        "frustrated": "I completely understand your frustration, and I apologize for the difficulty. ",
        "negative": "I'm sorry to hear you're experiencing trouble. ",
        "positive": "That's wonderful to hear! "
    }

    @classmethod
    def analyze(cls, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment, emotion intensity, and escalation necessity.
        Returns a structured dictionary with sentiment label, score, and flags.
        """
        if not text:
            return {"sentiment": "neutral", "score": 0.0, "is_frustrated": False, "needs_escalation": False}

        text_lower = text.lower().strip()
        words = re.findall(r"\b\w+\b", text_lower)

        pos_count = sum(1 for w in words if w in cls.POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in cls.NEGATIVE_WORDS)
        frust_count = sum(1 for w in words if w in cls.FRUSTRATED_WORDS)

        # Check for phrase-level escalation requests
        escalation_patterns = [
            r"\b(talk to (a |an )?(human|person|agent|representative|manager))\b",
            r"\b(connect me to (a |an )?(human|person|agent))\b",
            r"\b(get me a human)\b",
            r"\b(transfer to (a |an )?agent)\b",
            r"\b(real person please)\b"
        ]
        explicit_escalation = any(re.search(pat, text_lower) for pat in escalation_patterns)

        # Exclamation and caps emphasis
        has_caps = len(text) > 4 and text.isupper()
        has_exclamation = "!" in text

        # Compute polarity score (-1.0 to +1.0)
        total_signals = pos_count + neg_count + (frust_count * 2)
        if total_signals == 0:
            score = 0.0
            sentiment = "neutral"
        else:
            raw_score = (pos_count - neg_count - (frust_count * 1.5)) / total_signals
            score = round(max(-1.0, min(1.0, raw_score)), 2)

            if frust_count >= 1 or explicit_escalation or score <= -0.5:
                sentiment = "frustrated"
            elif score > 0.2:
                sentiment = "positive"
            elif score < -0.2:
                sentiment = "negative"
            else:
                sentiment = "neutral"

        is_frustrated = sentiment == "frustrated" or explicit_escalation
        needs_escalation = is_frustrated or explicit_escalation

        return {
            "sentiment": sentiment,
            "score": score,
            "is_frustrated": is_frustrated,
            "needs_escalation": needs_escalation,
            "empathy_prefix": cls.EMPATHY_PREFIXES.get(sentiment, "")
        }
