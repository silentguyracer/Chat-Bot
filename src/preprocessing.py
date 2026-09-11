import re
from typing import List, Set
import nltk

# Ensure required NLTK datasets are downloaded silently if available
try:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)
    nltk.download('stopwords', quiet=True)
    from nltk.tokenize import word_tokenize
    from nltk.stem import WordNetLemmatizer
    from nltk.corpus import stopwords
    _NLTK_AVAILABLE = True
    _lemmatizer = WordNetLemmatizer()
    _stopwords = set(stopwords.words('english'))
except Exception:
    _NLTK_AVAILABLE = False
    _lemmatizer = None
    _stopwords = {
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're",
        "you've", "you'll", "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he',
        'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's",
        'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
        'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are',
        'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do',
        'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because',
        'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against',
        'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to',
        'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
        'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can',
        'will', 'just', 'don', "don't", 'should', "should've", 'now', 'd', 'll', 'm',
        'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't", 'didn',
        "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven',
        "haven't", 'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't",
        'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't",
        'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
    }

CONTRACTIONS = {
    r"can't": "can not",
    r"won't": "will not",
    r"n't": " not",
    r"'re": " are",
    r"'s": " is",
    r"'d": " would",
    r"'ll": " will",
    r"'t": " not",
    r"'ve": " have",
    r"'m": " am",
}


def expand_contractions(text: str) -> str:
    """Expand standard English contractions."""
    for pattern, replacement in CONTRACTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def clean_text(text: str) -> str:
    """Lowercase, expand contractions, and remove unwanted special characters."""
    if not text:
        return ""
    text = text.lower().strip()
    text = expand_contractions(text)
    # Remove special punctuation while keeping alphanumeric and basic whitespace
    text = re.sub(r"[^a-zA-Z0-9\s:/@-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """Tokenize a string into words."""
    cleaned = clean_text(text)
    if not cleaned:
        return []
    if _NLTK_AVAILABLE:
        try:
            return word_tokenize(cleaned)
        except Exception:
            pass
    # Fallback whitespace regex tokenizer
    return re.findall(r"\b\w+\b", cleaned)


def lemmatize_token(token: str) -> str:
    """Lemmatize an individual token."""
    token_lower = token.lower()
    if _NLTK_AVAILABLE and _lemmatizer:
        try:
            # Try verb first then noun
            lemma = _lemmatizer.lemmatize(token_lower, pos='v')
            if lemma == token_lower:
                lemma = _lemmatizer.lemmatize(token_lower, pos='n')
            return lemma
        except Exception:
            pass
    # Basic rule-based fallback suffix stripper
    if token_lower.endswith("ies") and len(token_lower) > 4:
        return token_lower[:-3] + "y"
    if token_lower.endswith("ing") and len(token_lower) > 4:
        return token_lower[:-3]
    if token_lower.endswith("ed") and len(token_lower) > 3:
        return token_lower[:-2]
    if token_lower.endswith("s") and not token_lower.endswith("ss") and len(token_lower) > 2:
        return token_lower[:-1]
    return token_lower


def preprocess_text(text: str, remove_stopwords: bool = False) -> List[str]:
    """
    Complete NLP preprocessing pipeline:
    clean -> tokenize -> lemmatize -> (optional) filter stopwords.
    """
    tokens = tokenize(text)
    lemmas = [lemmatize_token(t) for t in tokens if t]
    if remove_stopwords:
        lemmas = [w for w in lemmas if w not in _stopwords]
    return lemmas


def get_normalized_string(text: str, remove_stopwords: bool = False) -> str:
    """Return preprocessed tokens joined back as a normalized string."""
    tokens = preprocess_text(text, remove_stopwords=remove_stopwords)
    return " ".join(tokens)
