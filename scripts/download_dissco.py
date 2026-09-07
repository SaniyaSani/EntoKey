#!/usr/bin/env python3
"""Harvest a bounded or explicitly unbounded Diptera export from DiSSCo's open API.

Search results are expanded through the documented ``/full`` endpoint so linked
Digital Media Objects are retained for the existing openDS ingestor.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests


DEFAULT_API = "https://disscover.dissco.eu/api"
USER_AGENT = "TaxaLens-WholeFly/0.7 (DiSSCo open-data research harvester)"


def jsonapi_items(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", [])
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def specimen_pid(item: dict) -> str:
    value = str(item.get("id", "") or item.get("attributes", {}).get("id", "")).strip()
    if value.startswith(("http://", "https://")):
        value = urlsplit(value).path.strip("/")
    value = re.sub(r"^doi:", "", value, flags=re.I).strip("/")
    return value


def get_json(session: requests.Session, url: str, params: dict | None, retries: int) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, params=params, timeout=(30, 120))
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"DiSSCo request failed: {last_error}")


def full_url(api: str, pid: str) -> str:
    parts = pid.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"unexpected DiSSCo specimen id: {pid}")
    return f"{api.rstrip('/')}/digital-specimen/v1/{parts[0]}/{parts[1]}/full"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/raw/dissco/diptera_full.jsonl")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--max-records", type=int, default=20_000, help="0 requires --allow-unbounded")
    parser.add_argument("--allow-unbounded", action="store_true")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.max_records == 0 and not args.allow_unbounded:
        raise SystemExit("use --allow-unbounded with --max-records 0 after reviewing API capacity and storage")

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if args.resume and destination.exists():
        with destination.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                obj = json.loads(line)
                pid = specimen_pid(obj.get("data", obj) if isinstance(obj, dict) else {})
                if pid:
                    seen.add(pid)
    mode = "a" if args.resume else "w"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    search_url = f"{args.api.rstrip('/')}/digital-specimen/v1/search"
    written = len(seen)
    page = 1
    with destination.open(mode, encoding="utf-8") as output:
        while not args.max_records or written < args.max_records:
            params = {
                "q": "Diptera",
                "livingOrPreserved": "preserved",
                "hasOrder": "true",
                "pageNumber": page,
                "pageSize": args.page_size,
            }
            payload = get_json(session, search_url, params, args.retries)
            items = jsonapi_items(payload)
            if not items:
                break
            new_on_page = 0
            for item in items:
                pid = specimen_pid(item)
                if not pid or pid in seen:
                    continue
                try:
                    full = get_json(session, full_url(args.api, pid), None, args.retries)
                except Exception as exc:
                    print(f"skip {pid}: {exc}")
                    continue
                output.write(json.dumps(full, ensure_ascii=False) + "\n")
                output.flush()
                seen.add(pid)
                written += 1
                new_on_page += 1
                if args.sleep:
                    time.sleep(args.sleep)
                if args.max_records and written >= args.max_records:
                    break
            print(f"DiSSCo expanded specimens: {written} (page {page})")
            if new_on_page == 0:
                print("DiSSCo returned no new specimen IDs; stopping to avoid a pagination loop")
                break
            page += 1
    print(f"DiSSCo openDS export -> {destination} ({written} specimens)")


if __name__ == "__main__":
    main()
