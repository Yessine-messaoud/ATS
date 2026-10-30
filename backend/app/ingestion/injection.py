"""Heuristic detection of prompt-injection attempts embedded in candidate documents.

Detection only flags the document for the recruiter. The real protection is architectural: document text is
always passed to the LLM as data, and scores are computed deterministically, never by the LLM.
"""

from __future__ import annotations

import re

PATTERNS = [
    # English
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+)?(the\s+|your\s+)?((previous|prior|above|earlier|job|"
    r"screening|other)\s+)?(instructions|prompts|rules|requirements|criteria)",
    r"(you\s+are|act\s+as)\s+(now\s+)?(an?\s+)?(ai|assistant|language\s+model|chatgpt|claude|gpt)",
    r"system\s+prompt",
    r"new\s+instructions\s*:",
    r"\b(system|assistant)\s*:\s*(ignore|disregard|forget|override|you\s+(are|must)|new\s+instructions)",
    r"(rate|score|rank)\s+(this|the)\s+(candidate|applicant|cv|resume)\s+(as\s+)?(\d{2,3}|highest|top|perfect)",
    r"(give|assign|award)\s+(me\s+|this\s+(candidate|applicant|profile|cv)\s+)?(a\s+)?(score|rating|grade)\s+of\s+\d{2,3}",
    r"(rank|place|put|list)\s+(me|this\s+(candidate|applicant|profile))\s+(first|at\s+the\s+top|on\s+top)",
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
