#!/usr/bin/env python3
"""Build a small, license-aware Diptera pilot dataset from the iNaturalist API.

For large training corpora, use the official iNaturalist Licensed Observation Images
or GBIF/DwC-A datasets instead of scraping the API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from PIL import Image
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diptera_id.taxonomy import path_from_taxon

API = "https://api.inaturalist.org/v1"
DEFAULT_DIPTERA_ID = 47822
UA = "SwissDipteraIDWorkbench/0.1 (research pilot; contact project owner)"


def chunks(items, n):
    for i in range(0, len(items), n):
        yield items[i:i+n]


def medium_url(url: str) -> str:
    return re.sub(r"/(square|small|thumb|medium|large)\.", "/medium.", url)


def fetch_json(session: requests.Session, url: str, params=None, retries: int = 4):
    for attempt in range(retries):
        r = session.get(url, params=params, timeout=45)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after retries: {url}")


def fetch_taxa(session: requests.Session, ids: set[int]) -> dict[int, dict]:
    lookup: dict[int, dict] = {}
    for batch in chunks(sorted(ids), 30):
        payload = fetch_json(session, f"{API}/taxa/{','.join(map(str,batch))}")
        for item in payload.get("results", []):
            lookup[item["id"]] = item
        time.sleep(0.35)
    return lookup


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data")
    p.add_argument("--taxon-id", type=int, default=DEFAULT_DIPTERA_ID)
    p.add_argument("--place-id", type=int, default=None, help="Optional iNaturalist place ID (e.g. Switzerland)")
    p.add_argument("--pages", type=int, default=3)
    p.add_argument("--per-page", type=int, default=100)
    p.add_argument("--max-images-per-observation", type=int, default=1)
    p.add_argument("--licenses", default="cc0,cc-by,cc-by-sa", help="Photo licenses. NC is intentionally excluded by default.")
    p.add_argument("--download", action="store_true", help="Actually download images; otherwise only write manifest URLs")
    args = p.parse_args()

    out = Path(args.out)
    image_dir = out / "images"
    out.mkdir(parents=True, exist_ok=True)
    if args.download:
        image_dir.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({"User-Agent": UA})

    observations = []
    all_taxon_ids: set[int] = set()
    for page in range(1, args.pages + 1):
        params = {
            "taxon_id": args.taxon_id,
            "quality_grade": "research",
            "photos": "true",
            "photo_license": args.licenses,
            "per_page": min(args.per_page, 200),
            "page": page,
            "order_by": "created_at",
            "order": "desc",
        }
        if args.place_id:
            params["place_id"] = args.place_id
        payload = fetch_json(s, f"{API}/observations", params=params)
        batch = payload.get("results", [])
        if not batch:
            break
        observations.extend(batch)
        for obs in batch:
            taxon = obs.get("taxon") or {}
            if isinstance(taxon.get("id"), int):
                all_taxon_ids.add(taxon["id"])
            for ancestor_id in taxon.get("ancestor_ids", []) or []:
                if isinstance(ancestor_id, int):
                    all_taxon_ids.add(ancestor_id)
        time.sleep(0.5)

    taxon_lookup = fetch_taxa(s, all_taxon_ids)
    rows = []
    for obs in observations:
        taxon = obs.get("taxon") or {}
        path = path_from_taxon(taxon, taxon_lookup)
        # Species training requires a species-level label.
        if not path.species:
            continue

        user = (obs.get("user") or {}).get("login")
        for photo in (obs.get("photos") or [])[: args.max_images_per_observation]:
            url = medium_url(photo.get("url", ""))
            if not url:
                continue
            photo_id = photo.get("id")
            ext = ".jpg"
            local_name = f"inat_{obs['id']}_{photo_id}{ext}"
            local_path = image_dir / local_name

            if args.download and not local_path.exists():
                try:
                    r = s.get(url, timeout=45)
                    r.raise_for_status()
                    img = Image.open(BytesIO(r.content)).convert("RGB")
                    img.save(local_path, format="JPEG", quality=92)
                except Exception as exc:
                    print(f"skip image {url}: {exc}")
                    continue
                time.sleep(0.15)

            rows.append({
                "source": "iNaturalist",
                "observation_id": obs.get("id"),
                "photo_id": photo_id,
                "image_url": url,
                "local_path": str(local_path) if args.download else "",
                "family": path.family or "",
                "genus": path.genus or "",
                "species": path.species or "",
                "taxon_id": taxon.get("id"),
                "observed_on": obs.get("observed_on") or "",
                "latitude": (obs.get("geojson") or {}).get("coordinates", [None, None])[1] if obs.get("geojson") else None,
                "longitude": (obs.get("geojson") or {}).get("coordinates", [None, None])[0] if obs.get("geojson") else None,
                "observer": user or "",
                "photo_license": photo.get("license_code") or "",
                "attribution": photo.get("attribution") or "",
                "observation_url": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "split_group": hashlib.sha1(str(obs.get("id")).encode()).hexdigest()[:12],
            })

    df = pd.DataFrame(rows)
    manifest = out / "inat_pilot_manifest.csv"
    df.to_csv(manifest, index=False)
    print(f"Wrote {len(df)} images -> {manifest}")
    if len(df):
        print(f"Species: {df['species'].nunique()} | Families: {df['family'].nunique()}")


if __name__ == "__main__":
    main()
