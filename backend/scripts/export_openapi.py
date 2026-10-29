"""Write the API's OpenAPI schema to a file (used to generate the frontend's TypeScript types).

Usage (from backend/):  uv run python -m scripts.export_openapi ../frontend/src/lib/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {target}")
