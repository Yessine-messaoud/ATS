"""Deterministic policy guard: requests to select or judge candidates on protected characteristics are refused
before any model call.

The system prompt already tells the model to refuse; this guard makes the refusal independent of the model, which
matters for small local models that do not reliably follow it (mistral 7B searched for "age:under_30" and then
stated which candidates were under 30, a fact no tool had returned). It errs on the side of refusing: a recruiter
who meant something legitimate can rephrase in job-related terms.
"""

from __future__ import annotations

import re

PROTECTED = {
    "age": [
        r"\b(over|under|older\s+than|younger\s+than|plus\s+de|moins\s+de)\s+\d{2}(?!\s*(years?\s+of|ans\s+d|%|k\b))\b",
        r"\b(age|ages|aged|âge|âgée?s?)\b",
        r"\byoung(er)?\s+(people|candidates|ones|profiles|person)\b",
        r"\b(old|older)\s+(people|candidates|ones|profiles|person)\b",
        r"\b(jeunes?|vieux|seniors?\s+citizens)\b",
    ],
    "gender": [
        r"\b(male|female|males|females|men|women|man|woman|hommes?|femmes?|masculins?|féminine?s?|gender|genre|sexe)\b",
    ],
    "origin or nationality": [
        r"\b(origin|origine|nationality|nationalité|nationalities|ethnic|ethnicity|ethnie|race|racial)\b",
        r"\b(foreigners?|étrangers?|immigrants?)\b",
    ],
    "religion": [r"\b(religion|religious|muslims?|christians?|jews?|jewish|musulmane?s?|chrétiens?|juifs?)\b"],
    "family situation": [
        r"\b(married|divorced|marié(e)?s?|célibataires?|children|kids|enfants|pregnan\w*|enceintes?)\b",
        r"\b(family\s+situation|situation\s+familiale|marital)\b",
    ],
    # "health" alone is a sector ("health-sector experience"); only conditions are protected.
    "health or disability": [
        r"\b(disabled|disability|handicap\w*|illness|maladie|sick)\b",
        r"\b(health\s+(condition|problems?|issues?|status)|état\s+de\s+santé)\b",
    ],
}
PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, group in PROTECTED.items() for pattern in group]
FRENCH = re.compile(r"\b(les|des|candidats?|poste|pour|ne|garde|que|qui|sont|avec|sans)\b", re.IGNORECASE)

REFUSAL_EN = (
    "I can't help with that: selecting or judging candidates on {topic} is discriminatory, and candidates are "
    "assessed only on job-related criteria (skills, experience, languages, location, availability). If you have a "
    "job-related requirement in mind, tell me and I will look for candidates who meet it."
)
REFUSAL_FR = (
    "Je ne peux pas faire cela : sélectionner ou évaluer des candidats selon {topic} est discriminatoire, et les "
    "candidats sont évalués uniquement sur des critères liés au poste (compétences, expérience, langues, lieu, "
    "disponibilité). Si vous avez une exigence liée au poste, dites-la-moi et je chercherai les profils qui y "
    "répondent."
)
TOPICS_FR = {
    "age": "l'âge",
    "gender": "le genre",
    "origin or nationality": "l'origine ou la nationalité",
    "religion": "la religion",
    "family situation": "la situation familiale",
    "health or disability": "la santé ou le handicap",
}


def protected_topic(text: str) -> str | None:
    for name, pattern in PATTERNS:
        if pattern.search(text):
            return name
    return None


def refusal(text: str) -> str | None:
    """The refusal to send instead of running the model, or None when the request is acceptable."""
    topic = protected_topic(text)
    if topic is None:
        return None
    if len(FRENCH.findall(text)) >= 2:
        return REFUSAL_FR.format(topic=TOPICS_FR[topic])
    return REFUSAL_EN.format(topic=topic)
