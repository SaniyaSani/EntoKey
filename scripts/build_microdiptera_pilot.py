#!/usr/bin/env python3
"""Build a license-aware, family-balanced MicroDiptera pilot from iNaturalist.

This API workflow is intentionally bounded and intended for a pilot only.  Use
the official Open Data tables for a large corpus.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_inat_pilot import API, UA, fetch_json, fetch_taxa, medium_url
from diptera_id.corpus.io import ManifestWriter
from diptera_id.corpus.schema import finalize_record, normalize_license
from diptera_id.taxonomy import path_from_taxon


def resolve_family(session: requests.Session, name: str) -> dict:
    payload = fetch_json(session, f"{API}/taxa", params={
        "q": name,
        "rank": "family",
        "is_active": "true",
        "per_page": 30,
    })
    for taxon in payload.get("results", []):
        if str(taxon.get("name", "")).casefold() == name.casefold() and taxon.get("rank") == "family":
            return taxon
    raise RuntimeError(f"Could not resolve active iNaturalist family: {name}")


def family_observations(
    session: requests.Session,
    taxon_id: int,
    target: int,
    per_page: int,
    licenses: str,
    place_id: int | None,
) -> list[dict]:
    observations: list[dict] = []
    page = 1
    while len(observations) < target:
        params = {
            "taxon_id": taxon_id,
            "quality_grade": "research",
            "photos": "true",
            "photo_license": licenses,
            "per_page": min(per_page, 200),
            "page": page,
            "order_by": "created_at",
            "order": "desc",
        }
        if place_id:
            params["place_id"] = place_id
        batch = fetch_json(session, f"{API}/observations", params=params).get("results", [])
        if not batch:
            break
        observations.extend(batch)
        if len(batch) < params["per_page"]:
            break
        page += 1
        time.sleep(0.5)
    return observations[:target]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/microdiptera_families.json")
    parser.add_argument("--out", default="data/microdiptera")
    parser.add_argument("--per-family", type=int, default=150)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--place-id", type=int, default=None)
    parser.add_argument("--licenses", default="cc0,cc-by,cc-by-sa")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.12)
    args = parser.parse_args()
    if args.per_family > 1000:
        raise SystemExit("API pilot is capped at 1000 observations per family; use iNaturalist Open Data beyond that")

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    families = [str(value).strip() for value in config.get("families", []) if str(value).strip()]
    if not families:
        raise SystemExit("No families listed in config")
    out = Path(args.out)
    image_dir = out / "images"
    out.mkdir(parents=True, exist_ok=True)
    if args.download:
        image_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA.replace("/0.1", "/0.4")})
    allowed = {normalize_license(value) for value in args.licenses.split(",")}
    rows: list[dict] = []
    family_report: dict[str, dict] = {}

    for family_name in families:
        family_taxon = resolve_family(session, family_name)
        observations = family_observations(
            session,
            int(family_taxon["id"]),
            args.per_family,
            args.per_page,
            args.licenses,
            args.place_id,
        )
        taxon_ids: set[int] = {int(family_taxon["id"])}
        for observation in observations:
            taxon = observation.get("taxon") or {}
            if isinstance(taxon.get("id"), int):
                taxon_ids.add(taxon["id"])
            taxon_ids.update(value for value in (taxon.get("ancestor_ids") or []) if isinstance(value, int))
        lookup = fetch_taxa(session, taxon_ids)
        accepted = 0

        for observation in observations:
            taxon = observation.get("taxon") or {}
            path = path_from_taxon(taxon, lookup)
            if (path.family or "").casefold() != family_name.casefold():
                continue
            photos = observation.get("photos") or []
            if not photos:
                continue
            photo = photos[0]
            license_name = normalize_license(photo.get("license_code") or "")
            if license_name not in allowed:
                continue
            url = medium_url(photo.get("url", ""))
            if not url:
                continue
            photo_id = str(photo.get("id") or "")
            local_path = image_dir / f"inat_{observation['id']}_{photo_id}.jpg"
            if args.download and not local_path.exists():
                try:
                    response = session.get(url, timeout=45)
                    response.raise_for_status()
                    Image.open(BytesIO(response.content)).convert("RGB").save(local_path, "JPEG", quality=94)
                except Exception as exc:
                    print(f"skip {url}: {exc}")
                    continue
                time.sleep(args.sleep)

            user = (observation.get("user") or {}).get("login") or ""
            record = finalize_record({
                "source": "iNaturalist",
                "source_record_id": observation.get("id"),
                "source_image_id": photo_id,
                "image_url": url,
                "local_path": str(local_path.resolve()) if args.download else "",
                "image_license": license_name,
                "attribution": photo.get("attribution") or user,
                "source_url": f"https://www.inaturalist.org/observations/{observation.get('id')}",
                "basis_of_record": "HUMAN_OBSERVATION",
                "order": "Diptera",
                "family": path.family,
                "genus": path.genus,
                "species": path.species,
                "taxon_id": taxon.get("id"),
                "observer": user,
                "event_date": observation.get("observed_on") or "",
                "latitude": ((observation.get("geojson") or {}).get("coordinates") or [None, None])[1],
                "longitude": ((observation.get("geojson") or {}).get("coordinates") or [None, None])[0],
                "view_type": "habitus",
                "parent_specimen_id": str(observation.get("id")),
                "specimen_group_id": f"iNaturalist:{observation.get('id')}",
                "label_quality": "C" if path.species else "D",
            })
            rows.append(record)
            accepted += 1
        family_report[family_name] = {"taxon_id": family_taxon["id"], "images": accepted}
        print(f"{family_name}: {accepted} images")

    manifest = out / "microdiptera_manifest.csv"
    with ManifestWriter(manifest) as writer:
        writer.write(rows)
    (out / "collection_report.json").write_text(json.dumps(family_report, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} balanced MicroDiptera images -> {manifest}")


if __name__ == "__main__":
    main()
