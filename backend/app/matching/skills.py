"""Skill normalization v0: synonym table + implication/relatedness graph + strict fuzzy matching.

A deliberately small, hand-curated graph. Phase 4 replaces it with the ESCO taxonomy; the interface
(`canonical`, `skill_credit`) stays the same.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache

from rapidfuzz import fuzz

FUZZY_SAME_SKILL = 92
IMPLIED_CREDIT = 0.9

SYNONYMS: dict[str, str] = {
    "spark": "apache spark",
    "pyspark": "apache spark",
    "postgres": "postgresql",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "k8s": "kubernetes",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "js": "javascript",
    "ts": "typescript",
    "nodejs": "node.js",
    "node": "node.js",
    "express.js": "express",
    "expressjs": "express",
    "reactjs": "react",
    "react.js": "react",
    "springboot": "spring boot",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "microsoft power bi": "power bi",
    "amazon web services": "aws",
    "microsoft azure": "azure",
    "argo cd": "argocd",
    "gitlab ci/cd": "gitlab ci",
    "ci/cd": "continuous integration",
    "ci cd": "continuous integration",
    "cv": "computer vision",
    "vision par ordinateur": "computer vision",
    "apprentissage automatique": "machine learning",
    "ml": "machine learning",
    "dl": "deep learning",
    "onnx runtime": "onnx",
    "golang": "go",
    "c sharp": "c#",
}

# skill -> skills it demonstrates (transitively).
IMPLIES: dict[str, set[str]] = {
    "postgresql": {"sql", "relational databases"},
    "mysql": {"sql", "relational databases"},
    "sql server": {"sql", "relational databases"},
    "oracle": {"sql", "relational databases"},
    "dbt": {"sql"},
    "apache spark": {"big data"},
    "databricks": {"apache spark"},
    "azure data factory": {"azure", "etl"},
    "azure databricks": {"databricks", "azure"},
    "airflow": {"etl"},
    "pandas": {"python"},
    "django": {"python"},
    "flask": {"python"},
    "fastapi": {"python"},
    "pytorch": {"deep learning"},
    "tensorflow": {"deep learning"},
    "tensorflow lite": {"tensorflow"},
    "deep learning": {"machine learning"},
    "scikit-learn": {"machine learning", "python"},
    "object detection": {"computer vision"},
    "image segmentation": {"computer vision"},
    "opencv": {"computer vision"},
    "spring boot": {"java"},
    "node.js": {"javascript"},
    "express": {"node.js"},
    "react": {"javascript"},
    "angular": {"typescript"},
    "typescript": {"javascript"},
    "helm": {"kubernetes"},
    "argocd": {"kubernetes", "continuous integration"},
    "gitlab ci": {"continuous integration", "git"},
    "github actions": {"continuous integration", "git"},
    "jenkins": {"continuous integration"},
    "eks": {"kubernetes", "aws"},
    "gke": {"kubernetes", "google cloud platform"},
    "aks": {"kubernetes", "azure"},
    "terraform": {"infrastructure as code"},
    "ansible": {"infrastructure as code"},
    "dax": {"power bi"},
    "power query": {"power bi"},
}

# Unordered pairs of distinct but transferable skills, with the share of credit they give each other.
RELATED: dict[frozenset[str], float] = {
    frozenset(p): w
    for p, w in [
        (("postgresql", "mysql"), 0.7),
        (("postgresql", "sql server"), 0.7),
        (("mysql", "sql server"), 0.7),
        (("pytorch", "tensorflow"), 0.7),
        (("aws", "azure"), 0.5),
        (("aws", "google cloud platform"), 0.5),
        (("azure", "google cloud platform"), 0.5),
        (("react", "angular"), 0.5),
        (("react", "vue"), 0.6),
        (("power bi", "tableau"), 0.7),
        (("kafka", "rabbitmq"), 0.5),
        (("jenkins", "gitlab ci"), 0.7),
        (("gitlab ci", "github actions"), 0.8),
        (("docker", "kubernetes"), 0.4),
        (("onnx", "tensorrt"), 0.5),
        (("apache spark", "databricks"), 0.8),
        (("airflow", "azure data factory"), 0.5),
        (("java", "kotlin"), 0.6),
    ]
}


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", stripped).strip(" .,;:")


def canonical(name: str) -> str:
    key = normalize_text(name)
    return SYNONYMS.get(key, key)


@cache
def implied_by(skill: str) -> frozenset[str]:
    """Every skill demonstrated by `skill` (transitive closure of IMPLIES), excluding itself."""
    seen: set[str] = set()
    stack = list(IMPLIES.get(skill, ()))
    while stack:
        current = stack.pop()
        if current not in seen:
            seen.add(current)
            stack.extend(IMPLIES.get(current, ()))
    return frozenset(seen)


def same_skill(a: str, b: str) -> bool:
    return a == b or fuzz.ratio(a, b) >= FUZZY_SAME_SKILL


def skill_credit(have: str, want: str) -> tuple[float, str]:
    """Credit in [0, 1] that having skill `have` gives towards required skill `want`, and how it was earned."""
    if same_skill(have, want):
        return 1.0, "exact"
    if want in implied_by(have):
        return IMPLIED_CREDIT, "implied"
    related = RELATED.get(frozenset((have, want)))
    if related is not None:
        return related, "related"
    return 0.0, "none"


@cache
def mention_pattern(skill: str) -> re.Pattern[str]:
    """Whole-word pattern for a canonical skill and all its synonyms ("apache spark", "spark", "pyspark").

    Also works for names such as C++, C#, Node.js.
    """
    terms = sorted({skill, *(alias for alias, target in SYNONYMS.items() if target == skill)}, key=len, reverse=True)
    alternatives = "|".join(re.escape(term) for term in terms)
    return re.compile(rf"(?<![\w+#.])(?:{alternatives})(?![\w+#])")


# Every skill name the graph knows, used to spot skill mentions in free-text experience descriptions.
KNOWN_SKILLS: frozenset[str] = frozenset(
    set(IMPLIES) | {s for targets in IMPLIES.values() for s in targets} | set(SYNONYMS.values())
)
