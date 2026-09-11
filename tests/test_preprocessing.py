from src.preprocessing import (
    clean_text,
    tokenize,
    lemmatize_token,
    preprocess_text,
    expand_contractions,
    get_normalized_string
)


def test_expand_contractions():
    assert "what is" in expand_contractions("what's")
    assert "can not" in expand_contractions("can't")
    assert "i am" in expand_contractions("i'm")


def test_clean_text():
    cleaned = clean_text("Hello, World! What's up?!")
    assert cleaned == "hello world what is up"


def test_tokenize():
    tokens = tokenize("Hello, world! Book a table.")
    assert "hello" in tokens
    assert "world" in tokens
    assert "book" in tokens
    assert "table" in tokens


def test_lemmatization():
    assert lemmatize_token("booking") in ["book", "booking"]
    assert lemmatize_token("tables") in ["table", "tables"]
    assert lemmatize_token("consultations") in ["consultation", "consultations"]


def test_preprocess_pipeline():
    res = preprocess_text("I am looking to book tables!", remove_stopwords=True)
    assert "book" in res or "booking" in res
    assert "look" in res or "looking" in res
    assert "table" in res or "tables" in res
    assert "i" not in res


def test_normalized_string():
    norm = get_normalized_string("What's your location?")
    assert isinstance(norm, str)
    assert len(norm) > 0
