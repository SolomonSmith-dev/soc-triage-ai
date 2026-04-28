# Model Card: Mood Machine

This model card covers both versions of the Mood Machine sentiment classifier:

1. A **rule-based model** in `mood_analyzer.py`
2. A **machine learning model** in `ml_experiments.py` using scikit-learn

Both were built and evaluated on the same dataset.

---

## 1. Model Overview

**Model type:** Both models were built and compared.

**Intended purpose:**
Classify short text posts (social media-style) into one of four mood labels:
`positive`, `negative`, `neutral`, or `mixed`.

**How the rule-based version works:**
Text is preprocessed (lowercased, punctuation stripped, ASCII emoticons converted,
elongated words normalized). Each token is scored against positive and negative word
lists. Words with stronger sentiment ("hate", "love", "hyphy", "janky") carry a weight
of 2 instead of the default 1. If a negation word ("not", "never", "can't") precedes a
sentiment word, its signal is flipped — "not happy" subtracts, "not bad" adds. The final
label is assigned by threshold:

- Both signals present and `abs(score) <= 1` → `mixed`
- `score > 0` → `positive`
- `score < 0` → `negative`
- `score == 0`, no signals → `neutral`

**How the ML version works:**
Text is converted to a bag-of-words vector using `CountVectorizer` (each word becomes
a feature, its value is how many times it appears). A `LogisticRegression` model is
trained to map those vectors to labels. It does not use the handcrafted word lists — it
learns associations between words and labels directly from the labeled examples.

---

## 2. Data

**Dataset description:**
24 total posts in `SAMPLE_POSTS`. Started with 6 provided examples. Added 18 more
including slang, emojis, sarcasm, mixed feelings, AAVE, and Bay Area-specific language.

**Labeling process:**
Labels were assigned manually. Most were straightforward. A few required judgment calls:

- `"today was just meh"` — initially labeled `neutral`, relabeled to `negative` after
  the rule-based model consistently predicted negative and that turned out to be more
  accurate to how "meh" actually reads.
- `"been slippin lately but im getting back on it"` — labeled `mixed` because "slippin"
  (negative) and the hopeful framing ("getting back on it") pull in opposite directions.
- `"I love being stuck in traffic 🙂"` — labeled `negative` (sarcasm). Debatable — a
  classmate might label this `positive` if they take the words at face value.

**Important characteristics:**
- Contains Bay Area and AAVE slang: "hyphy", "bussin", "janky", "bogus", "salty", "goated"
- Includes sarcasm (one example)
- Includes ASCII emoticons (`:)`, `:(`) and Unicode emoji (`💀`, `🙂`)
- Includes negation patterns: "not happy", "not bad"
- Mix of all four label types: 10 negative, 7 positive, 4 mixed, 1 neutral (slight imbalance)
- Only one truly neutral example — the model has limited signal for this class

**Possible issues:**
- 24 examples is extremely small for any real-world use
- Sarcasm appears only once — no generalizable pattern can be learned
- The dataset reflects the vocabulary of one person from one cultural context
- Neutral is severely underrepresented (1 example)

---

## 3. How the Rule-Based Model Works

**Scoring rules:**
- Positive word match → `+weight` (default 1, or 2 for strong words)
- Negative word match → `-weight`
- Negation prefix flips the sign
- Mixed threshold: both signals present and `|score| <= 1`

**Enhancements implemented:**
- Negation handling: "not happy" scores -1, "not bad" scores +1
- Word weighting: `"love"`, `"hate"`, `"terrible"`, `"hyphy"`, `"janky"`, `"bogus"`,
  `"bussin"`, `"proud"`, `"amazing"`, `"awesome"`, `"excited"`, `"fire"`, `"angry"`,
  `"disappointed"` all carry weight 2
- Emoticon conversion: `:)` → `happy`, `:(` → `sad`, etc. (handled in preprocessing)
- Elongation normalization: 3+ repeated characters reduced to 2
- Punctuation stripping: trailing `"happy!"` matches `"happy"`
- AAVE vocabulary: `"bussin"`, `"goated"`, `"slay"`, `"ate"`, `"pressed"`, `"salty"`, etc.
- Bay Area vocabulary: `"hyphy"`, `"janky"`, `"bogus"`, `"trippin"`, `"slippin"`, etc.

**Strengths:**
- Fully explainable: every prediction can be traced to specific tokens and scores
- Deterministic: same input always produces the same output
- Easy to patch: add a word to the list and behavior updates immediately
- Handles negation reliably for simple cases

**Weaknesses:**
- Cannot detect sarcasm: `"I love being stuck in traffic 🙂"` → predicted `positive`
  because `"love"` scores +2 and nothing else fires
- Cannot handle intensifiers: `"hella"` precedes both positive and negative words;
  adding it to either list produces wrong results, so it's omitted entirely
- Misses context: `"she slay every single time no cap"` → `neutral` (neither "slay"
  nor "every" nor "time" fires), when it should be `positive`
- Score is a flat sum — word order, tone, and sentence structure are invisible

---

## 4. How the ML Model Works

**Features used:** Bag-of-words via `CountVectorizer`. Each unique word in the
training set becomes a feature column. The value is the raw count of that word in
the post.

**TF-IDF comparison:** `TfidfVectorizer` was tested alongside `CountVectorizer`.
Both achieved identical 96% training accuracy and agreed on all 24 training examples.
On unseen sentences, they disagreed on one case (`"Oh great, another Monday"`).
With only 24 training examples, nearly every word appears in 1-2 documents — TF-IDF's
IDF weighting has almost nothing to differentiate. TF-IDF becomes more useful at
thousands of documents.

**Training behavior:**
Training accuracy was 96% (23/24 correct). The one miss was `"This is fine"` →
predicted `positive`, true `neutral` — the model had almost no neutral training
examples and no consistent signal for that class.

Adding more examples consistently improved accuracy. Adding Bay Area slang posts
gave the ML model patterns to learn (e.g., `"janky"` in a negative context, `"hyphy"`
in a positive one).

**Strengths:**
- Learns patterns from data without manual rule-writing
- Handled the sarcasm case correctly — `"I love being stuck in traffic 🙂"` →
  `negative` — because it memorized the training label
- Can implicitly capture co-occurrence patterns the rule-based system ignores

**Weaknesses:**
- The sarcasm "success" is memorization, not understanding. A new sarcastic sentence
  the model hasn't seen fails just like the rule-based system
- Evaluated only on training data — accuracy is inflated. A real evaluation needs
  a held-out test set
- `"that party was hella janky bro"` → predicted `positive` because `"party"` and
  `"bro"` co-occurred with positive labels in training, outweighing `"janky"`
- `"I went to the store"` → predicted `positive` — no neutral training signal
- Completely opaque: no way to inspect why a prediction was made without extra tooling

---

## 5. Evaluation

**How evaluated:** Both models ran against the full labeled `SAMPLE_POSTS` list.
This is training-set evaluation — not a held-out test — so numbers are optimistic.

**Results:**

| Model | Training Accuracy |
|---|---|
| Rule-based | 92% (22/24) |
| ML (CountVectorizer) | 96% (23/24) |

**Rule-based correct predictions:**
- `"I love this class so much"` → `positive` — `"love"` carries weight 2, nothing opposes it
- `"lowkey stressed but proud of myself ngl"` → `mixed` — `"stressed"` fires negative,
  `"proud"` fires positive with weight 2, score = +1 with both signals present → mixed
- `"I am not happy about this"` → `negative` — negation flips `"happy"` to -1

**Rule-based incorrect predictions:**
- `"I love being stuck in traffic 🙂"` → `positive` (true: `negative`)
  The model sees `"love"` (+2) and stops. Sarcasm is invisible to keyword scoring.
- `"been slippin lately but im getting back on it"` → `negative` (true: `mixed`)
  `"slippin"` fires -1. Nothing in `"getting back on it"` is in the word lists.
  The hopeful framing is undetectable.

**ML incorrect predictions:**
- `"This is fine"` → `positive` (true: `neutral`)
  Only one neutral training example. The model has no reliable pattern for this class.

---

## 6. Limitations

- **Dataset is tiny.** 24 examples cannot represent the real distribution of human
  language. Both models are over-tuned to this specific data.
- **No test set.** All evaluation is on training data. Neither accuracy number should
  be trusted for real-world use.
- **Sarcasm is undetectable by both systems** without contextual or pragmatic reasoning.
- **Intensifiers are invisible.** "hella happy" and "hella sad" look the same to both
  models because "hella" cannot be put in either word list without causing errors.
- **Neutral is severely underrepresented** — one example. Both models default away from
  this label when uncertain.
- **Cultural scope is narrow.** The dataset reflects Bay Area / AAVE English as used by
  one person. Slang from other regions, dialects, or languages is not covered.
- **Short text only.** Both models were designed for one-sentence social media posts.
  Longer text would likely break the scoring logic and overwhelm the ML model's features.

---

## 7. Ethical Considerations

- **Misclassifying distress.** A post like `"I'm fine :)"` might be a cry for help
  masked by forced positivity. This model would predict `positive` and miss it entirely.
  Using mood detection in mental health or crisis contexts with this system would be
  dangerous.
- **Dialect bias.** The model is optimized for one variety of English. AAVE and Bay
  Area slang were added intentionally, but other dialects (Southern US, Caribbean
  English, Indian English, etc.) are absent. The model may systematically misread
  posts written in those styles — not because the language is wrong, but because the
  training data doesn't include it.
- **Label subjectivity.** Multiple posts in this dataset could be reasonably labeled
  differently by different people. Labels reflect one perspective. Any application
  built on this system inherits that perspective.
- **Privacy.** If this system were applied to real social media posts, it would involve
  analyzing personal messages. The posts here are synthetic, but a production deployment
  would require user consent and data handling policies.

---

## 8. Ideas for Improvement

- **Add a real test set** — even 10-20 held-out labeled examples would give honest
  accuracy numbers instead of training-set inflation
- **Add more neutral examples** — the class has one training example, which is why
  both models avoid predicting it
- **Handle intensifiers** — detect "hella", "very", "so" as multipliers on the next
  sentiment word rather than ignoring them
- **Sarcasm detection** — requires either a larger dataset with many labeled sarcasm
  examples, or a pretrained language model (e.g., a small transformer) that encodes
  sentence context
- **Use TF-IDF with more data** — TF-IDF showed no improvement at 24 examples, but
  would likely help at 500+ examples where stopwords genuinely dilute the signal
- **Add a real test set and cross-validation** instead of evaluating on training data
- **Expand dialect coverage** — add labeled examples from more varieties of English
  so the model generalizes across communities rather than within one
