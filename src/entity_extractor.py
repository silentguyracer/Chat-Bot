import re
from typing import Dict, Any, Optional

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1, "couple": 2, "pair": 2
}

SERVICES = [
    "consultation", "table", "dinner", "lunch", "breakfast",
    "meeting", "support", "session", "haircut",
    "checkup", "tour", "demo"
]


class EntityExtractor:
    """Extracts domain entities and dialogue slots from user text."""

    @staticmethod
    def extract_party_size(text: str) -> Optional[int]:
        """Extract number of people/guests from input."""
        # Check patterns like "for 4 people", "table for 2", "party of 5", "3 guests"
        pattern = r"\b(?:for|party of|table for)?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|couple)\s*(?:people|persons?|guests?|pax)?\b"
        match = re.search(r"\b(?:for|party of|table for)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|couple)\b", text, re.IGNORECASE)
        if match:
            val = match.group(1).lower()
            return int(val) if val.isdigit() else NUMBER_WORDS.get(val, 1)

        match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|couple)\s+(?:people|persons?|guests?|pax)\b", text, re.IGNORECASE)
        if match:
            val = match.group(1).lower()
            return int(val) if val.isdigit() else NUMBER_WORDS.get(val, 1)

        # Standalone digits if input is short like "4" or "2"
        text_strip = text.strip()
        if text_strip.isdigit() and 1 <= int(text_strip) <= 50:
            return int(text_strip)
        if text_strip.lower() in NUMBER_WORDS:
            return NUMBER_WORDS[text_strip.lower()]

        return None

    @staticmethod
    def extract_date(text: str) -> Optional[str]:
        """Extract date information (relative days, weekdays, or explicit dates)."""
        # Relative dates
        rel_match = re.search(r"\b(today|tomorrow|day after tomorrow|tonight)\b", text, re.IGNORECASE)
        if rel_match:
            return rel_match.group(1).lower()

        # Day of week (e.g., this Friday, next Monday)
        dow_match = re.search(r"\b(?:this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text, re.IGNORECASE)
        if dow_match:
            return dow_match.group(0).strip().title()

        # Calendar formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD
        cal_match = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b", text)
        if cal_match:
            return cal_match.group(1)

        # Month and Day e.g., "September 15th", "15 Sept", "Oct 4"
        month_match = re.search(
            r"\b(?:on\s+)?((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*)\b",
            text,
            re.IGNORECASE
        )
        if month_match:
            return month_match.group(1).strip()

        return None

    @staticmethod
    def extract_time(text: str) -> Optional[str]:
        """Extract time information (e.g. 5pm, 2:30 PM, 14:00, noon, morning)."""
        # Exact time format with am/pm or minutes
        time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))\b", text, re.IGNORECASE)
        if time_match:
            return time_match.group(1).strip().upper()

        # 24-hour format: 14:00, 09:30
        hhmm_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        if hhmm_match:
            return hhmm_match.group(0)

        # General periods
        period_match = re.search(r"\b(morning|afternoon|evening|night|noon|lunchtime|dinnertime)\b", text, re.IGNORECASE)
        if period_match:
            return period_match.group(1).lower()

        return None

    @staticmethod
    def extract_name(text: str) -> Optional[str]:
        """Extract person name from introduction or slot reply."""
        # e.g. "My name is Sahil", "I am Alice", "Name: Bob", "Under John Doe"
        name_patterns = [
            r"\b(?:my name is|i am|i'm|name is|call me|under the name|under)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
            r"\b(?:my name is|i am|i'm|name is|call me|under the name|under)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\b",
            r"^name[:=\s]+([a-zA-Z\s]+)$"
        ]
        for pat in name_patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Filter out common false positives
                if extracted.lower() not in ["here", "ready", "interested", "looking", "asking", "trying"]:
                    return extracted.title()

        # If user directly types just a 1 or 2 word name during name slot prompt
        clean = text.strip()
        words = clean.split()
        if 1 <= len(words) <= 3 and all(w.isalpha() for w in words):
            # Make sure it's not a common command or stopword
            if clean.lower() not in ["hi", "hello", "yes", "no", "ok", "sure", "cancel", "help", "none"]:
                return clean.title()

        return None

    @staticmethod
    def extract_service(text: str) -> Optional[str]:
        """Extract service type requested."""
        text_lower = text.lower()
        for s in SERVICES:
            if re.search(rf"\b{s}\b", text_lower):
                return s.capitalize()
        return None

    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        """Extract email address."""
        match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
        return match.group(0) if match else None

    @staticmethod
    def extract_phone(text: str) -> Optional[str]:
        """Extract phone number."""
        match = re.search(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
        return match.group(0) if match else None

    @classmethod
    def extract_all(cls, text: str) -> Dict[str, Any]:
        """Extract all identifiable entities from user input."""
        entities = {}
        party = cls.extract_party_size(text)
        if party is not None:
            entities["party_size"] = party

        date_val = cls.extract_date(text)
        if date_val:
            entities["date"] = date_val

        time_val = cls.extract_time(text)
        if time_val:
            entities["time"] = time_val

        service_val = cls.extract_service(text)
        if service_val:
            entities["service"] = service_val

        name_val = cls.extract_name(text)
        if name_val:
            entities["name"] = name_val

        email_val = cls.extract_email(text)
        if email_val:
            entities["email"] = email_val

        phone_val = cls.extract_phone(text)
        if phone_val:
            entities["phone"] = phone_val

        return entities
