from __future__ import annotations

import json
from pathlib import Path


def load_json(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def diagnostic_help(family: str | None, rules_path: str | Path, refs_path: str | Path) -> dict:
    rules = load_json(rules_path)
    refs = load_json(refs_path)
    if not family:
        return {"characters": [], "keys": []}
    return {
        "characters": rules.get(family, {}).get("characters", []),
        "notes": rules.get(family, {}).get("notes", ""),
        "keys": refs.get(family, refs.get("_general", [])),
    }
