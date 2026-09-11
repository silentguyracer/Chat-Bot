from src.intent_classifier import MLIntentClassifier


def test_ml_classifier_training_and_prediction():
    classifier = MLIntentClassifier(
        training_csv_path="data/training_examples.csv",
        intents_json_path="data/intents.json"
    )
    assert classifier.is_trained is True

    # Test distinct phrases
    intent, conf = classifier.predict("i want to make a consultation reservation")
    assert intent == "book_appointment"
    assert conf > 0.3

    intent, conf = classifier.predict("what time do you shut down the store")
    assert intent == "business_hours"
    assert conf > 0.3

    intent, conf = classifier.predict("where is your physical office location")
    assert intent == "location"
    assert conf > 0.3
