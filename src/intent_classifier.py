import os
import json
import pandas as pd
from typing import Tuple, List, Optional
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.preprocessing import get_normalized_string


class MLIntentClassifier:
    """
    Machine Learning Intent Classifier (v4):
    Uses TF-IDF feature extraction + Logistic Regression with probability calibration
    to classify intent when rule matching confidence is low or ambiguous.
    """

    def __init__(
        self,
        training_csv_path: str = "data/training_examples.csv",
        intents_json_path: str = "data/intents.json",
        min_confidence: float = 0.40
    ):
        self.training_csv_path = Path(training_csv_path)
        self.intents_json_path = Path(intents_json_path)
        self.min_confidence = min_confidence
        self.pipeline: Optional[Pipeline] = None
        self.classes_: List[str] = []
        self.is_trained = False
        self.train()

    def _load_data(self) -> Tuple[List[str], List[str]]:
        """Load training texts and labels from CSV and intents.json patterns."""
        texts = []
        labels = []

        # Load from CSV if present
        if self.training_csv_path.exists():
            df = pd.read_csv(self.training_csv_path)
            for _, row in df.iterrows():
                text = str(row.get("text", "")).strip()
                intent = str(row.get("intent", "")).strip()
                if text and intent:
                    norm_text = get_normalized_string(text)
                    texts.append(norm_text)
                    labels.append(intent)

        # Augment with patterns from intents.json
        if self.intents_json_path.exists():
            with open(self.intents_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for intent in data.get("intents", []):
                tag = intent.get("tag")
                if tag and tag != "fallback":
                    for pat in intent.get("patterns", []):
                        norm_pat = get_normalized_string(pat)
                        texts.append(norm_pat)
                        labels.append(tag)

        return texts, labels

    def train(self):
        """Train the TF-IDF + LogisticRegression pipeline."""
        texts, labels = self._load_data()
        if not texts or len(set(labels)) < 2:
            self.is_trained = False
            return

        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                min_df=1
            )),
            ("clf", LogisticRegression(
                C=10.0,
                max_iter=500,
                random_state=42
            ))
        ])

        self.pipeline.fit(texts, labels)
        self.classes_ = list(self.pipeline.classes_)
        self.is_trained = True

    def predict(self, text: str) -> Tuple[str, float]:
        """
        Predict the intent tag and probability confidence for a given input.
        Returns ('fallback', 0.0) if confidence is below threshold or model is not trained.
        """
        if not self.is_trained or not self.pipeline:
            return "fallback", 0.0

        norm_text = get_normalized_string(text)
        if not norm_text:
            return "fallback", 0.0

        try:
            probabilities = self.pipeline.predict_proba([norm_text])[0]
            best_idx = probabilities.argmax()
            best_class = self.classes_[best_idx]
            confidence = float(probabilities[best_idx])

            if confidence >= self.min_confidence:
                return best_class, round(confidence, 3)
            return "fallback", round(confidence, 3)
        except Exception:
            return "fallback", 0.0
