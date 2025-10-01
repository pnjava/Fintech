"""Utility script to export the FastAPI OpenAPI specification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import create_application


def main() -> None:
    app = create_application()
    spec = app.openapi()
    destination = Path("docs/openapi.json")
    destination.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"OpenAPI specification written to {destination}")


if __name__ == "__main__":
    main()
