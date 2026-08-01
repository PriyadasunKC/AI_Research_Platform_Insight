"""
build_postman_body.py - Turn a plain .txt essay file into a properly
JSON-escaped request body, ready to paste into Postman's raw/JSON body
editor (or use with curl --data-binary @file).

Why this exists: pasting a multi-line essay directly into Postman's (or
curl's) raw body editor keeps the literal line breaks, which is not valid
JSON - every JSON parser used by this API (Python's json module, via
FastAPI/Pydantic) rejects unescaped control characters inside a string.
This script does the escaping for you.

Usage:
    python docs/build_postman_body.py path/to/essay.txt [submitted_by]

Prints the JSON body to stdout - copy it straight into Postman's body
editor (Body -> raw -> JSON), or redirect it to a file for curl:
    python docs/build_postman_body.py essay.txt student-042 > body.json
    curl -X POST http://localhost:8010/api/v1/essay/check \\
        -H "Content-Type: application/json" -H "X-API-Key: ..." \\
        --data-binary @body.json
"""

from __future__ import annotations

import json
import sys

# Windows consoles default stdout to the system codepage (e.g. cp1252),
# which cannot encode Sinhala characters - force UTF-8 regardless of
# platform/terminal so this always works, redirected to a file or not.
sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    essay_path = sys.argv[1]
    submitted_by = sys.argv[2] if len(sys.argv) > 2 else None

    essay_text = open(essay_path, encoding="utf-8").read().strip()
    payload = {"essay_text": essay_text}
    if submitted_by:
        payload["submitted_by"] = submitted_by

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
