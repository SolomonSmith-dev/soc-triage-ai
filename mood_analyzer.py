# mood_analyzer.py
"""
Rule based mood analyzer for short text snippets.

This class starts with very simple logic:
  - Preprocess the text
  - Look for positive and negative words
  - Compute a numeric score
  - Convert that score into a mood label
"""

import re
import string
from typing import List, Tuple, Optional

from dataset import POSITIVE_WORDS, NEGATIVE_WORDS, WORD_WEIGHTS, EMOTICON_MAP


class MoodAnalyzer:
    """
    A rule based mood classifier with negation handling, word weighting,
    emoticon support, and a mixed sentiment label.
    """

    def __init__(
        self,
        positive_words: Optional[List[str]] = None,
        negative_words: Optional[List[str]] = None,
    ) -> None:
        # Use the default lists from dataset.py if none are provided.
        positive_words = positive_words if positive_words is not None else POSITIVE_WORDS
        negative_words = negative_words if negative_words is not None else NEGATIVE_WORDS

        # Store as sets for O(1) lookup.
        self.positive_words = set(w.lower() for w in positive_words)
        self.negative_words = set(w.lower() for w in negative_words)

        # Word weights: unlisted words default to 1.
        self.word_weights = {k.lower(): v for k, v in WORD_WEIGHTS.items()}

        # Negation words: if any of these immediately precede a sentiment word,
        # the sentiment is flipped. Decision: keep this set small and explicit.
        # Contractions like "don't" become "dont" after punctuation stripping,
        # so we store both forms.
        self.negation_words = {
            "not", "never", "no",
            "don't", "dont",
            "won't", "wont",
            "can't", "cant",
            "isn't", "isnt",
            "wasn't", "wasnt",
        }

    # ---------------------------------------------------------------------
    # Preprocessing
    # ---------------------------------------------------------------------

    def preprocess(self, text: str) -> List[str]:
        """
        Convert raw text into a list of tokens the model can work with.

        Steps in order (order matters):
          1. Replace ASCII emoticons before punctuation stripping removes their chars.
          2. Lowercase.
          3. Normalize elongated words: 3+ repeated chars -> 2 (e.g. "soooo" -> "soo").
             Decision: reduces to 2, not 1, because single-char reduction is lossy
             ("goood" -> "god"). Two keeps the shape recognizable for inspection.
          4. Split on whitespace.
          5. Strip ASCII punctuation from token edges; preserve unicode (emoji).
             Decision: strip edges only, not internals, so "it's" stays "it's".
        """
        # Step 1: replace ASCII emoticons with their sentiment word.
        # Must happen before lowercasing+punctuation removal erase the emoticon structure.
        for emoticon, word in EMOTICON_MAP.items():
            text = text.replace(emoticon, f" {word} ")

        # Step 2: lowercase.
        text = text.strip().lower()

        # Step 3: reduce 3+ repeated characters to 2.
        text = re.sub(r"(.)\1{2,}", r"\1\1", text)

        # Step 4: split.
        raw_tokens = text.split()

        # Step 5: strip ASCII punctuation from token edges, keep unicode intact.
        # string.punctuation = !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~
        tokens = []
        for token in raw_tokens:
            cleaned = token.strip(string.punctuation)
            if cleaned:
                tokens.append(cleaned)

        return tokens

    # ---------------------------------------------------------------------
    # Core analysis (private)
    # ---------------------------------------------------------------------

    def _analyze(self, text: str) -> Tuple[int, List[str], List[str]]:
        """
        Run the full scoring pass and return (score, pos_hits, neg_hits).

        This is the single source of truth for scoring logic.
        score_text, predict_label, and explain all call this instead of
        duplicating the token loop — one loop to change, one place to debug.

        Enhancements applied here:
          - Word weighting: "hate" counts as -2, "bad" as -1.
          - Negation: if the previous token is a negation word, flip the signal.
        """
        tokens = self.preprocess(text)
        score = 0
        pos_hits: List[str] = []
        neg_hits: List[str] = []

        for i, token in enumerate(tokens):
            negated = i > 0 and tokens[i - 1] in self.negation_words
            weight = self.word_weights.get(token, 1)

            if token in self.positive_words:
                if negated:
                    score -= weight
                    neg_hits.append(f"not_{token}")
                else:
                    score += weight
                    pos_hits.append(token)

            elif token in self.negative_words:
                if negated:
                    score += weight
                    pos_hits.append(f"not_{token}")
                else:
                    score -= weight
                    neg_hits.append(token)

        return score, pos_hits, neg_hits

    # ---------------------------------------------------------------------
    # Scoring logic
    # ---------------------------------------------------------------------

    def score_text(self, text: str) -> int:
        """
        Compute a numeric "mood score" for the given text.

        Delegates to _analyze and returns just the score.
        Positive = net positive signal; Negative = net negative; 0 = neutral.
        """
        score, _, _ = self._analyze(text)
        return score

    # ---------------------------------------------------------------------
    # Label prediction
    # ---------------------------------------------------------------------

    def predict_label(self, text: str) -> str:
        """
        Turn the numeric score into a mood label.

        Label logic (decision rationale in comments):
          - "mixed": both positive AND negative signals fired, but the net
            score is weak (abs <= 1). The model noticed real tension — calling
            it positive or negative would be overconfident.
          - "positive" / "negative": net score is strong enough (abs >= 2) OR
            only one kind of signal fired at all.
          - "neutral": score is 0 and no signals fired (truly empty/flat text).

        Why abs(score) <= 1 as the mixed threshold?
          With weight-1 words, score +1/-1 means a single word on one side.
          That's not a strong enough signal to commit to a label when the other
          side also showed up. Requiring >= 2 to confidently label positive/negative
          reduces false positives on ambiguous text.
        """
        score, pos_hits, neg_hits = self._analyze(text)

        # Both signals present and net score is weak -> mixed
        if pos_hits and neg_hits and abs(score) <= 1:
            return "mixed"

        if score > 0:
            return "positive"
        elif score < 0:
            return "negative"
        else:
            return "neutral"

    # ---------------------------------------------------------------------
    # Explanations
    # ---------------------------------------------------------------------

    def explain(self, text: str) -> str:
        """
        Return a short string explaining WHY the model chose its label.

        Uses _analyze so the explanation always reflects actual scoring logic.
        """
        score, pos_hits, neg_hits = self._analyze(text)
        label = self.predict_label(text)
        return (
            f"label={label}, score={score} "
            f"(positive signals: {pos_hits or []}, "
            f"negative signals: {neg_hits or []})"
        )