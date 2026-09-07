from __future__ import annotations

import json
from pathlib import Path

from diptera_id.key_finder import KeyFinder, candidate_genera, discovery_queries


ROOT = Path(__file__).resolve().parents[1]


def test_candidate_genera_preserves_rank_order_and_removes_duplicates():
    rows = [{"taxon": "Eristalis"}, {"taxon": "Helophilus"}, {"taxon": "Eristalis"}]
    assert candidate_genera(rows) == ["Eristalis", "Helophilus"]


def test_queries_cover_each_candidate_and_family():
    queries = discovery_queries("Syrphidae", ["Eristalis", "Helophilus"], "Europe")
    assert len(queries) == 3
    assert any("Eristalis" in query for query in queries)
    assert any("Syrphidae" in query and "genera" in query for query in queries)


def test_offline_finder_returns_curated_family_key(tmp_path):
    catalog = tmp_path / "keys.json"
    catalog.write_text(json.dumps({"references": [{
        "title": "A key to Syrphidae", "families": ["Syrphidae"], "genera": []
    }]}), encoding="utf-8")
    payload = KeyFinder(catalog).find("Syrphidae", ["Eristalis"], live=False)
    assert payload["results"][0]["title"] == "A key to Syrphidae"
    assert payload["results"][0]["provider"] == "curated"
    assert payload["live_search"] is False


def test_catalog_is_valid_json_and_has_general_reference():
    payload = json.loads((ROOT / "data/key_catalog_v09.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert any(not row.get("families") for row in payload["references"])
