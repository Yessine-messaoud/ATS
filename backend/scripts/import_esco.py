"""Import the ESCO skills taxonomy from the official CSV export, then rebuild the retrieval index.

1. Download the ESCO dataset (CSV, languages: en + fr) from https://esco.ec.europa.eu/en/use-esco/download
2. Unzip it, then run (from backend/):

   uv run python -m scripts.import_esco path/to/esco-csv --version esco-1.2.0

Uses skills_en.csv, skills_fr.csv (optional) and broaderRelationsSkillPillar.csv (optional).
Restart the API afterwards: the taxonomy is loaded at startup.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import get_engine
from app.matching.taxonomy import read_esco_csv, set_taxonomy
from app.search.index import reindex_all
from app.services.taxonomy import save_taxonomy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True, help="recorded with every score, e.g. esco-1.2.0")
    args = parser.parse_args()

    files = {lang: args.directory / f"skills_{lang}.csv" for lang in ("en", "fr")}
    files = {lang: path for lang, path in files.items() if path.exists()}
    if "en" not in files:
        raise SystemExit(f"skills_en.csv not found in {args.directory}")
    broader = args.directory / "broaderRelationsSkillPillar.csv"
    taxonomy = read_esco_csv(files, broader if broader.exists() else None, args.version)
    print(f"read {len(taxonomy.skills)} skills, {sum(len(b) for b in taxonomy.broader.values())} broader relations")

    with Session(get_engine()) as db:
        save_taxonomy(db, taxonomy)
        set_taxonomy(taxonomy)
        print("reindexed", reindex_all(db))


if __name__ == "__main__":
    main()
