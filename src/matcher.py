import json
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from src.preprocessing import preprocess_text, get_normalized_string, clean_text

try:
    from rapidfuzz import fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    import difflib
    _RAPIDFUZZ_AVAILABLE = False


class RuleMatcher:
    """
    Rule-based Intent Matching Engine supporting:
    - Exact pattern match
    - Regex pattern match
    - Lemmatized keyword-overlap scoring (Jaccard & containment)
    - Fuzzy string matching for typo tolerance
    """

    def __init__(self, intents_path: str = "data/intents.json", min_confidence: float = 0.55):
        self.intents_path = Path(intents_path)
        self.min_confidence = min_confidence
        self.intents: List[Dict[str, Any]] = []
        self.intent_by_tag: Dict[str, Dict[str, Any]] = {}
        self.pattern_index: List[Dict[str, Any]] = []
        self.load_intents()

    def load_intents(self):
        """Load intents from JSON file and pre-process patterns for fast matching."""
        if not self.intents_path.exists():
            raise FileNotFoundError(f"Intents file not found at: {self.intents_path}")

        with open(self.intents_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.intents = data.get("intents", [])
        self.intent_by_tag = {intent["tag"]: intent for intent in self.intents}
        self.pattern_index = []

        for intent in self.intents:
            tag = intent["tag"]
            if tag == "fallback":
                continue

            # Index string patterns
            for pattern in intent.get("patterns", []):
                cleaned_pat = clean_text(pattern)
                tokens = preprocess_text(pattern, remove_stopwords=False)
                tokens_no_stop = preprocess_text(pattern, remove_stopwords=True)
                self.pattern_index.append({
                    "tag": tag,
                    "raw_pattern": pattern,
                    "cleaned_pattern": cleaned_pat,
                    "tokens": set(tokens),
                    "tokens_no_stop": set(tokens_no_stop) if tokens_no_stop else set(tokens),
                    "normalized_str": get_normalized_string(pattern, remove_stopwords=False)
                })

    def match_exact(self, text: str) -> Optional[Tuple[str, float, str]]:
        """Check for exact cleaned string match against any pattern."""
        cleaned_user = clean_text(text)
        for item in self.pattern_index:
            if cleaned_user == item["cleaned_pattern"]:
                return item["tag"], 1.0, "exact"
        return None

    def match_regex(self, text: str) -> Optional[Tuple[str, float, str]]:
        """Check regex rules specified in intents.json."""
        cleaned_user = clean_text(text)
        for intent in self.intents:
            tag = intent.get("tag")
            if tag == "fallback":
                continue
            for regex_pat in intent.get("regex_patterns", []):
                try:
                    if re.search(regex_pat, cleaned_user, re.IGNORECASE):
                        return tag, 0.95, "regex"
                except re.error:
                    continue
        return None

    def match_keyword_overlap(self, text: str) -> Optional[Tuple[str, float, str]]:
        """
        Score intent patterns based on token overlap (Jaccard similarity + containment ratio)
        on lemmatized words.
        """
        user_tokens = set(preprocess_text(text, remove_stopwords=False))
        user_tokens_no_stop = set(preprocess_text(text, remove_stopwords=True))
        if not user_tokens:
            return None

        eval_tokens = user_tokens_no_stop if user_tokens_no_stop else user_tokens

        best_score = 0.0
        best_tag = None

        for item in self.pattern_index:
            pat_tokens = item["tokens_no_stop"] if item["tokens_no_stop"] else item["tokens"]
            if not pat_tokens:
                continue

            intersection = eval_tokens.intersection(pat_tokens)
            if not intersection:
                continue

            # Containment score (how much of the pattern is covered by the user)
            containment = len(intersection) / len(pat_tokens)
            # Jaccard similarity
            union = eval_tokens.union(pat_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0

            # Weighted combination
            score = (0.7 * containment) + (0.3 * jaccard)

            if score > best_score:
                best_score = score
                best_tag = item["tag"]

        if best_tag and best_score >= self.min_confidence:
            return best_tag, round(best_score, 3), "keyword_overlap"

        return None

    def match_fuzzy(self, text: str) -> Optional[Tuple[str, float, str]]:
        """Fuzzy match user text against all indexed patterns for typo tolerance."""
        cleaned_user = clean_text(text)
        if not cleaned_user or len(cleaned_user) < 3:
            return None

        best_score = 0.0
        best_tag = None

        for item in self.pattern_index:
            target = item["cleaned_pattern"]
            if _RAPIDFUZZ_AVAILABLE:
                # WRatio balances Levenshtein, token order, and partial matches
                score = fuzz.WRatio(cleaned_user, target) / 100.0
            else:
                ratio = difflib.SequenceMatcher(None, cleaned_user, target).ratio()
                score = ratio

            if score > best_score:
                best_score = score
                best_tag = item["tag"]

        # 0.72 provides good tolerance for typos (e.g. 'helo ther' -> 'hey there' / 'hello')
        if best_tag and best_score >= 0.72:
            return best_tag, round(best_score, 3), "fuzzy"

        return None

    def match(self, text: str) -> Tuple[str, float, str]:
        """
        Run the complete rule matcher pipeline in order of priority:
        1. Exact match
        2. Regex rules
        3. Keyword overlap
        4. Fuzzy typo match
        5. Fallback
        """
        # 1. Exact Match
        exact_res = self.match_exact(text)
        if exact_res:
            return exact_res

        # 2. Regex Match
        regex_res = self.match_regex(text)
        if regex_res:
            return regex_res

        # 3. Keyword Overlap
        keyword_res = self.match_keyword_overlap(text)
        if keyword_res and keyword_res[1] >= self.min_confidence:
            return keyword_res

        # 4. Fuzzy Typo Match
        fuzzy_res = self.match_fuzzy(text)
        if fuzzy_res:
            return fuzzy_res

        # If keyword overlap has partial match score above 0.45, return with lower confidence
        if keyword_res and keyword_res[1] >= 0.45:
            return keyword_res

        return "fallback", 0.0, "fallback"
