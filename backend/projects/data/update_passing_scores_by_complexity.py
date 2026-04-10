"""
Set rubric.passing_score from project complexity in project_templates JSON.

Mapping (edit PASSING_BY_COMPLEXITY if needed):
  BEGINNER      -> 80
  INTERMEDIATE  -> 75
  ADVANCED      -> 70

Usage (from repo root or any cwd):
  python backend/projects/data/update_passing_scores_by_complexity.py
  python backend/projects/data/update_passing_scores_by_complexity.py path/to/file.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent / "project_templates_five_domains.json"

PASSING_BY_COMPLEXITY = {
    "BEGINNER": 80,
    "INTERMEDIATE": 75,
    "ADVANCED": 70,
}


def _strip_trailing_comma_before_close_array(raw: str) -> str:
    """Remove illegal JSON trailing comma after last array element (... },\\n])."""
    s = raw.strip()
    s = re.sub(r"(\})\s*,(\s*)\]\s*$", r"\1\2]", s, count=1)
    return s


def main() -> None:
    path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_FILE
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fixed = _strip_trailing_comma_before_close_array(raw)
        data = json.loads(fixed)

    if not isinstance(data, list):
        print("JSON root must be an array.", file=sys.stderr)
        sys.exit(1)

    updated = 0
    missing_rubric = 0
    unknown_cx = 0

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        cx = item.get("complexity")
        if cx not in PASSING_BY_COMPLEXITY:
            print(f"Entry {i}: unknown complexity {cx!r}, skipped.", file=sys.stderr)
            unknown_cx += 1
            continue
        rubric = item.get("rubric")
        if not isinstance(rubric, dict):
            missing_rubric += 1
            rubric = {}
            item["rubric"] = rubric
        new_score = PASSING_BY_COMPLEXITY[cx]
        if rubric.get("passing_score") != new_score:
            rubric["passing_score"] = new_score
            updated += 1

    out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(out, encoding="utf-8")

    print(f"Wrote {path}")
    print(f"Templates: {len(data)} | passing_score updated on {updated} rubric(s).")
    if missing_rubric:
        print(f"Note: created empty rubric dict for {missing_rubric} item(s) that lacked rubric.")
    if unknown_cx:
        print(f"Warning: {unknown_cx} item(s) skipped due to unknown complexity.", file=sys.stderr)


if __name__ == "__main__":
    main()
