# ml_experiments.py
"""
Simple ML experiments for the Mood Machine lab.

This file uses a "real" machine learning library (scikit-learn)
to train a tiny text classifier on the same SAMPLE_POSTS and
TRUE_LABELS that you use with the rule based model.
"""

from typing import List, Tuple

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

from dataset import SAMPLE_POSTS, TRUE_LABELS


def train_ml_model(
    texts: List[str],
    labels: List[str],
) -> Tuple[CountVectorizer, LogisticRegression]:
    """
    Train a simple text classifier using bag of words features
    and logistic regression.

    Steps:
      1. Convert the texts into numeric vectors using CountVectorizer.
      2. Fit a LogisticRegression model on those vectors and labels.

    Returns:
      (vectorizer, model)
    """
    if len(texts) != len(labels):
        raise ValueError(
            "texts and labels must be the same length. "
            "Check SAMPLE_POSTS and TRUE_LABELS in dataset.py."
        )

    if not texts:
        raise ValueError("No training data provided. Add examples in dataset.py.")

    vectorizer = CountVectorizer()
    X = vectorizer.fit_transform(texts)

    model = LogisticRegression(max_iter=1000)
    model.fit(X, labels)

    return vectorizer, model


def evaluate_on_dataset(
    texts: List[str],
    labels: List[str],
    vectorizer: CountVectorizer,
    model: LogisticRegression,
) -> float:
    """
    Evaluate the trained model on a labeled dataset.

    Prints each text with its predicted label and the true label,
    then returns the overall accuracy as a float between 0 and 1.
    """
    if len(texts) != len(labels):
        raise ValueError(
            "texts and labels must be the same length. "
            "Check your dataset."
        )

    X = vectorizer.transform(texts)
    preds = model.predict(X)

    print("=== ML Model Evaluation on Dataset ===")
    correct = 0
    for text, true_label, pred_label in zip(texts, labels, preds):
        is_correct = pred_label == true_label
        if is_correct:
            correct += 1
        print(f'"{text}" -> predicted={pred_label}, true={true_label}')

    accuracy = accuracy_score(labels, preds)
    print(f"\nAccuracy on this dataset: {accuracy:.2f}")
    return accuracy


def predict_single_text(
    text: str,
    vectorizer: CountVectorizer,
    model: LogisticRegression,
) -> str:
    """
    Predict the mood label for a single text string using
    the trained ML model.
    """
    X = vectorizer.transform([text])
    pred = model.predict(X)[0]
    return pred


def run_interactive_loop(
    vectorizer: CountVectorizer,
    model: LogisticRegression,
) -> None:
    """
    Let the user type their own sentences and see the ML model's
    predicted mood label.

    Type 'quit' or press Enter on an empty line to exit.
    """
    print("\n=== Interactive Mood Machine (ML model) ===")
    print("Type a sentence to analyze its mood.")
    print("Type 'quit' or press Enter on an empty line to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input == "" or user_input.lower() == "quit":
            print("Goodbye from the ML Mood Machine.")
            break

        label = predict_single_text(user_input, vectorizer, model)
        print(f"ML model: {label}")


def compare_vectorizers(texts: List[str], labels: List[str]) -> None:
    """
    Train two models — one with CountVectorizer, one with TfidfVectorizer —
    on the same data and compare their training accuracy and predictions.

    Why TF-IDF?
    CountVectorizer counts raw word occurrences. TF-IDF (Term Frequency-Inverse
    Document Frequency) downweights words that appear in many documents, so
    common filler words ("this", "was", "the") carry less weight and
    distinctive words ("janky", "bussin", "hyphy") carry more.

    On a tiny dataset, the difference is often small because every word
    is rare — but the pattern of failures may differ.
    """
    print("\n=== CountVectorizer vs TF-IDF Comparison ===\n")

    for name, VectClass in [("CountVectorizer", CountVectorizer), ("TfidfVectorizer", TfidfVectorizer)]:
        vect = VectClass()
        X = vect.fit_transform(texts)
        clf = LogisticRegression(max_iter=1000)
        clf.fit(X, labels)
        preds = clf.predict(X)
        acc = accuracy_score(labels, preds)
        print(f"[{name}] training accuracy: {acc:.2f}")

        # Show disagreements only — where the two vectorizers produce different results
        # (tracked after both loops via a second pass below)

    # Second pass: side-by-side on each example
    count_vect = CountVectorizer()
    X_count = count_vect.fit_transform(texts)
    clf_count = LogisticRegression(max_iter=1000).fit(X_count, labels)

    tfidf_vect = TfidfVectorizer()
    X_tfidf = tfidf_vect.fit_transform(texts)
    clf_tfidf = LogisticRegression(max_iter=1000).fit(X_tfidf, labels)

    print("\nSide-by-side where predictions DIFFER:")
    found_diff = False
    for text, true in zip(texts, labels):
        p_count = clf_count.predict(count_vect.transform([text]))[0]
        p_tfidf = clf_tfidf.predict(tfidf_vect.transform([text]))[0]
        if p_count != p_tfidf:
            found_diff = True
            print(f'  "{text}"')
            print(f'    true={true}  count={p_count}  tfidf={p_tfidf}')
    if not found_diff:
        print("  (none — both vectorizers agree on all training examples)")

    # Also test both on the same unseen sentences
    unseen = [
        "Oh great, another Monday",
        "that party was hella janky bro",
        "she slay every single time no cap",
        "hella happy today",
        "I went to the store",
        "tired but honestly blessed",
    ]
    print("\nUnseen sentences — Count vs TF-IDF:")
    for text in unseen:
        p_count = clf_count.predict(count_vect.transform([text]))[0]
        p_tfidf = clf_tfidf.predict(tfidf_vect.transform([text]))[0]
        match = "same" if p_count == p_tfidf else "DIFFER"
        print(f'  "{text}" -> count={p_count}, tfidf={p_tfidf}  [{match}]')


if __name__ == "__main__":
    print("Training an ML model on SAMPLE_POSTS and TRUE_LABELS from dataset.py...")
    print("Make sure you have added enough labeled examples before running this.\n")

    # Train the model on the current dataset.
    vectorizer, model = train_ml_model(SAMPLE_POSTS, TRUE_LABELS)

    # Evaluate on the same dataset (training accuracy).
    evaluate_on_dataset(SAMPLE_POSTS, TRUE_LABELS, vectorizer, model)

    # Compare CountVectorizer vs TF-IDF.
    compare_vectorizers(SAMPLE_POSTS, TRUE_LABELS)

    # Let the user try their own examples.
    run_interactive_loop(vectorizer, model)

    print("\nTip: Compare these predictions with the rule based model")
    print("by running `python main.py`. Notice where they fail in")
    print("similar ways and where they fail in different ways.")
