from src.matcher import RuleMatcher


def test_rule_matcher_exact():
    matcher = RuleMatcher(intents_path="data/intents.json")
    tag, conf, method = matcher.match("hi")
    assert tag == "greeting"
    assert conf == 1.0
    assert method == "exact"


def test_rule_matcher_regex():
    matcher = RuleMatcher(intents_path="data/intents.json")
    tag, conf, method = matcher.match("book an appointment for next week")
    assert tag == "book_appointment"
    assert conf >= 0.85
    assert method == "regex"


def test_rule_matcher_keyword_overlap():
    matcher = RuleMatcher(intents_path="data/intents.json")
    tag, conf, method = matcher.match("could you please tell me your opening times")
    assert tag == "business_hours"
    assert conf >= 0.5


def test_rule_matcher_fuzzy_typo():
    matcher = RuleMatcher(intents_path="data/intents.json")
    tag, conf, method = matcher.match("helo ther")
    assert tag == "greeting"
    assert method == "fuzzy" or method == "keyword_overlap"


def test_rule_matcher_fallback():
    matcher = RuleMatcher(intents_path="data/intents.json")
    tag, conf, method = matcher.match("quantum physics entanglement tensor field")
    assert tag == "fallback"
