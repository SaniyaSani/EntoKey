#!/usr/bin/env python3
"""Create or submit a reproducible GBIF DWCA download request for preserved Diptera."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests


API = "https://api.gbif.org/v1/occurrence/download/request"


def query(email: str, taxon_key: str) -> dict:
    return {
        "notificationAddresses": [email],
        "sendNotification": True,
        "format": "DWCA",
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "TAXON_KEY", "value": taxon_key},
                {"type": "equals", "key": "BASIS_OF_RECORD", "value": "PRESERVED_SPECIMEN"},
                {"type": "equals", "key": "MEDIA_TYPE", "value": "StillImage"},
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxon-key", default="811", help="GBIF taxon key for Diptera; verify if using a non-default checklist")
    parser.add_argument("--out", default="data/requests/gbif_preserved_diptera.json")
    parser.add_argument("--submit", action="store_true", help="Submit using GBIF_USER, GBIF_PASSWORD and GBIF_EMAIL")
    args = parser.parse_args()

    email = os.getenv("GBIF_EMAIL", "YOUR_EMAIL@example.org")
    payload = query(email, args.taxon_key)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote reproducible request -> {out}")
    if not args.submit:
        print("not submitted; inspect the JSON and rerun with --submit")
        return

    username = os.getenv("GBIF_USER")
    password = os.getenv("GBIF_PASSWORD")
    if not username or not password or email == "YOUR_EMAIL@example.org":
        raise SystemExit("Set GBIF_USER, GBIF_PASSWORD and GBIF_EMAIL before --submit")
    response = requests.post(API, auth=(username, password), json=payload, timeout=60)
    response.raise_for_status()
    print(f"GBIF download key: {response.text.strip()}")


if __name__ == "__main__":
    main()
