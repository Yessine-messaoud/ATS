"""Heuristic detection of prompt-injection attempts embedded in candidate documents.

Detection only flags the document for the recruiter. The real protection is architectural: document text is
always passed to the LLM as data, and scores are computed deterministically, never by the LLM.
"""

from __future__ import annotations

import re

PATTERNS = [
    # English
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above)\s+(instructions|prompts)",
    r"(you\s+are|act\s+as)\s+(now\s+)?(an?\s+)?(ai|assistant|language\s+model|chatgpt|claude|gpt)",
    r"system\s+prompt",
    r"(rate|score|rank)\s+(this|the)\s+(candidate|applicant|cv|resume)\s+(as\s+)?(\d{2,3}|highest|top|perfect)",
    r"(this|the)\s+(candidate|applicant)\s+is\s+(the\s+)?(perfect|ideal|best)\s+(match|fit|candidate)",
    r"note\s+to\s+(the\s+)?(ai|llm|model|recruiter\s+bot|screening\s+system)",
    # French
    r"ignore[rz]?\s+(toutes\s+)?(les\s+)?instructions\s+(précédentes|precedentes|ci-dessus)",
    r"oublie[rz]?\s+(toutes\s+)?(les\s+)?instructions",
    r"(attribue[rz]?|donne[rz]?)\s+(un\s+)?(score|note)\s+(de\s+)?\d{2,3}",
    r"(ce|cette)\s+(candidat|candidate)\s+est\s+(le|la)\s+(meilleur|meilleure|parfait|parfaite)",
]
INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.IGNORECASE)


def detect_prompt_injection(text: str) -> list[str]:
    """Return the matched snippets (with a little context), empty when nothing suspicious is found."""
    snippets = []
    for match in INJECTION_RE.finditer(text):
        start, end = max(match.start() - 30, 0), min(match.end() + 30, len(text))
        snippets.append(" ".join(text[start:end].split()))
    return snippets
