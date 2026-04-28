"""
Shared data for the Mood Machine lab.

This file defines:
  - POSITIVE_WORDS: starter list of positive words
  - NEGATIVE_WORDS: starter list of negative words
  - SAMPLE_POSTS: short example posts for evaluation and training
  - TRUE_LABELS: human labels for each post in SAMPLE_POSTS
"""

# ---------------------------------------------------------------------
# Starter word lists
# ---------------------------------------------------------------------

# Word weights: words not listed here default to weight 1.
# Higher weight = stronger sentiment signal in either direction.
# Decision: separate strong signals ("hate", "love") from mild ones ("bad", "good")
# so the scorer can reflect real intensity differences.
WORD_WEIGHTS = {
    # Strong positives
    "love": 2,
    "amazing": 2,
    "awesome": 2,
    "excited": 2,
    "fire": 2,
    "proud": 2,
    "bussin": 2,
    "hyphy": 2,   # strong Bay Area hype signal
    # Strong negatives
    "hate": 2,
    "terrible": 2,
    "awful": 2,
    "angry": 2,
    "disappointed": 2,
    "bogus": 2,   # Bay Area: strong sense of wrongness
    "janky": 2,   # Bay Area: broken/sketchy, always clearly negative
}

# ASCII emoticon map: convert text emoticons to sentiment tokens before
# punctuation stripping removes the characters that make them recognizable.
# Decision: do this in dataset.py so the vocabulary stays centralized.
EMOTICON_MAP = {
    ":)":  "happy",
    ":-)": "happy",
    ":D":  "excited",
    ":(":  "sad",
    ":-(": "sad",
    ":/":  "stressed",
    ":'(": "sad",
}



POSITIVE_WORDS = [
    "happy",
    "great",
    "good",
    "love",
    "excited",
    "awesome",
    "fun",
    "chill",
    "relaxed",
    "amazing",
    # General slang positives
    "fire",
    "lit",
    "proud",
    "hyped",
    "blessed",
    "winning",
    "funny",
    "hopeful",
    "grinding",   # working hard, hustling
    # AAVE positives
    "bussin",     # delicious / excellent
    "goated",     # greatest of all time
    "slay",       # doing something excellently
    "ate",        # nailed it ("she ate that")
    "dope",       # cool / impressive
    "fye",        # fire / great (regional AAVE)
    "slaps",      # sounds amazing
    "sheesh",     # expression of awe or hype
    "valid",      # correct / approved
    "secured",    # achieved something ("secured the bag")
    "real",       # genuine / facts (affirmative)
    "facts",      # agreement / emphasis on something true
    "gassed",     # excited / hyped up
    # Bay Area slang positives
    # NOTE: "hella" is an intensifier, not a sentiment word — intentionally omitted
    # ("hella good" = positive, "hella sad" = negative; adding it either way is wrong)
    "hyphy",      # energized / turned up (E-40/Mac Dre era Bay Area)
    "turnt",      # hype / excited
    "fresh",      # stylish / clean (positive state)
    "clean",      # looking good / no problems
    "sick",       # impressive / cool
    "stunting",   # showing off confidently (positive self-expression)
    "flexin",     # same as stunting, showing strength or success
    "mob",        # moving with your crew (positive social context)
    "drip",       # strong personal style
    # Emoji signals
    "😂",
    "🔥",
    "😍",
    "🥳",
]

NEGATIVE_WORDS = [
    "sad",
    "bad",
    "terrible",
    "awful",
    "angry",
    "upset",
    "tired",
    "stressed",
    "hate",
    "boring",
    # Slang / informal negatives
    "disappointed",
    "annoyed",
    "exhausted",
    "off",
    "meh",
    "wtf",
    # AAVE negatives
    "pressed",    # upset / bothered over something
    "salty",      # bitter / resentful
    "hating",     # being jealous or negative toward someone
    "played",     # disrespected / betrayed
    "sus",        # suspicious / untrustworthy
    "cappin",     # lying (negative because dishonest)
    "down",       # struggling / in a bad place ("feeling down bad")
    # Bay Area slang negatives
    "bogus",      # unfair / wrong / low quality (strong negative)
    "janky",      # broken / sketchy / unreliable (strong negative)
    "trippin",    # overreacting or acting wrongly
    "slippin",    # messing up / not being careful
    "shady",      # untrustworthy / sketchy
    # Emoji signals
    "😢",
    "😡",
    "💔",
    "😤",
]

# ---------------------------------------------------------------------
# Starter labeled dataset
# ---------------------------------------------------------------------

# Short example posts written as if they were social media updates or messages.
SAMPLE_POSTS = [
    "I love this class so much",
    "Today was a terrible day",
    "Feeling tired but kind of hopeful",
    "This is fine",
    "So excited for the weekend",
    "I am not happy about this",
    # Added posts: slang, emojis, sarcasm, mixed feelings
    "lowkey stressed but proud of myself ngl",
    "this is absolutely fire no cap",
    "I love being stuck in traffic 🙂",
    "not bad tbh",
    "im dead 💀 this is too funny",
    "woke up feeling off today idk",
    "exhausted but we out here grinding",
    "today was just meh",
    "cant believe this happened wtf",
    "im not even mad just really disappointed",
    # Bay Area slang posts
    "bro that set was hella hyphy we had a blast",
    "this wifi is so janky i cant get anything done",
    "felt bogus getting left out like that",
    "she was salty all night for no reason",
    "pulled up fresh and the whole fit was clean",
    "homie was trippin but we still had fun",
    "ngl that was bussin i need another plate",
    "been slippin lately but im getting back on it",
]

# Human labels for each post above.
# Allowed labels in the starter:
#   - "positive"
#   - "negative"
#   - "neutral"
#   - "mixed"
TRUE_LABELS = [
    "positive",  # "I love this class so much"
    "negative",  # "Today was a terrible day"
    "mixed",     # "Feeling tired but kind of hopeful"
    "neutral",   # "This is fine"
    "positive",  # "So excited for the weekend"
    "negative",  # "I am not happy about this"
    # Labels for added posts
    "mixed",     # "lowkey stressed but proud of myself ngl"
    "positive",  # "this is absolutely fire no cap"
    "negative",  # "I love being stuck in traffic 🙂" (sarcasm)
    "positive",  # "not bad tbh"
    "positive",  # "im dead 💀 this is too funny"
    "negative",  # "woke up feeling off today idk"
    "mixed",     # "exhausted but we out here grinding"
    "negative",  # "today was just meh" — meh signals dissatisfaction, not neutrality
    "negative",  # "cant believe this happened wtf"
    "negative",  # "im not even mad just really disappointed"
    # Bay Area post labels
    "positive",  # "bro that set was hella hyphy we had a blast" — hyphy + blast = strong positive
    "negative",  # "this wifi is so janky i cant get anything done" — janky = strong negative
    "negative",  # "felt bogus getting left out like that" — bogus = strong negative
    "negative",  # "she was salty all night for no reason" — salty = negative
    "positive",  # "pulled up fresh and the whole fit was clean" — fresh + clean = positive
    "mixed",     # "homie was trippin but we still had fun" — trippin (neg) + fun (pos)
    "positive",  # "ngl that was bussin i need another plate" — bussin = strong positive
    "mixed",     # "been slippin lately but im getting back on it" — slippin (neg) + getting back (neutral but hopeful)
]

# TODO: Add 5-10 more posts and labels.
#
# Requirements:
#   - For every new post you add to SAMPLE_POSTS, you must add one
#     matching label to TRUE_LABELS.
#   - SAMPLE_POSTS and TRUE_LABELS must always have the same length.
#   - Include a variety of language styles, such as:
#       * Slang ("lowkey", "highkey", "no cap")
#       * Emojis (":)", ":(", "🥲", "😂", "💀")
#       * Sarcasm ("I absolutely love getting stuck in traffic")
#       * Ambiguous or mixed feelings
#
# Tips:
#   - Try to create some examples that are hard to label even for you.
#   - Make a note of any examples that you and a friend might disagree on.
#     Those "edge cases" are interesting to inspect for both the rule based
#     and ML models.
#
# Example of how you might extend the lists:
#
# SAMPLE_POSTS.append("Lowkey stressed but kind of proud of myself")
# TRUE_LABELS.append("mixed")
#
# Remember to keep them aligned:
#   len(SAMPLE_POSTS) == len(TRUE_LABELS)
