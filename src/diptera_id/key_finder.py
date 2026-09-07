from __future__ import annotations

"""Find taxonomic keys for the family/genus candidates returned by TaxaLens.

The finder deliberately separates curated references from discovery results.  A
search hit is a lead to inspect, never evidence that the suggested taxon is
correct.  Crossref and OpenAlex are queried through their public APIs and the
results can be cached for reproducible later review.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import quote

KEY_TERMS = {
    "key": 4.0,
    "keys": 4.0,
    "identification": 3.0,
    "revision": 2.5,
    "taxonomy": 2.0,
    "diagnosis": 1.5,
    "monograph": 1.5,
    "diptera": 1.0,
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def candidate_genera(predictions: Iterable[dict], limit: int = 4) -> list[str]:
    """Extract ordered unique genus names from classifier candidate rows."""
    return _unique(row.get("taxon", "") for row in predictions)[:limit]


def discovery_queries(family: str | None, genera: Iterable[str], region: str = "Europe") -> list[str]:
    family = _clean(family)
    genera = _unique(genera)
    queries = [f'"{genus}" identification key Diptera {region}' for genus in genera]
    if family:
        queries.append(f'"{family}" genera identification key Diptera {region}')
    return _unique(queries)


def _score(title: str, family: str, genera: list[str]) -> float:
    lower = title.casefold()
    score = sum(weight for term, weight in KEY_TERMS.items() if term in lower)
    if family and family.casefold() in lower:
        score += 3.0
    score += 5.0 * sum(genus.casefold() in lower for genus in genera)
    return score


def _doi_url(doi: str | None) -> str | None:
    doi = _clean(doi)
    return f"https://doi.org/{quote(doi, safe='/()') }" if doi else None


@dataclass
class KeyFinder:
    catalog_path: Path
    cache_dir: Path | None = None
    timeout: float = 8.0
    user_agent: str = "TaxaLens/0.9 (taxonomic-key discovery; research prototype)"

    def _catalog(self) -> list[dict]:
        if not self.catalog_path.exists():
            return []
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        return payload.get("references", payload if isinstance(payload, list) else [])

    def curated(self, family: str | None, genera: Iterable[str]) -> list[dict]:
        family = _clean(family)
        genera = _unique(genera)
        genus_keys = {value.casefold() for value in genera}
        rows: list[dict] = []
        for raw in self._catalog():
            families = _unique(raw.get("families", []))
            catalog_genera = _unique(raw.get("genera", []))
            family_match = not families or family.casefold() in {value.casefold() for value in families}
            genus_match = bool(genus_keys & {value.casefold() for value in catalog_genera})
            if not family_match and not genus_match:
                continue
            row = dict(raw)
            row.update({
                "provider": "curated",
                "match_type": "genus" if genus_match else "family",
                "score": 100.0 + (10.0 if genus_match else 0.0),
                "verification": "curated lead; inspect geographic and taxonomic scope",
            })
            rows.append(row)
        return rows

    def _crossref(self, query: str, family: str, genera: list[str], rows: int) -> list[dict]:
        import requests

        response = requests.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query, "rows": rows, "select": "DOI,title,author,published,URL,type"},
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        response.raise_for_status()
        output: list[dict] = []
        for item in response.json().get("message", {}).get("items", []):
            title = _clean((item.get("title") or [""])[0])
            score = _score(title, family, genera)
            if score < 3.0:
                continue
            date_parts = item.get("published", {}).get("date-parts", [[]])
            year = date_parts[0][0] if date_parts and date_parts[0] else None
            authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("author", [])[:4]]
            doi = _clean(item.get("DOI")) or None
            output.append({
                "title": title,
                "authors": ", ".join(filter(None, authors)),
                "year": year,
                "doi": doi,
                "url": _doi_url(doi) or item.get("URL"),
                "provider": "Crossref",
                "query": query,
                "match_type": "discovery",
                "score": score,
                "verification": "discovery result; confirm that it contains an applicable key",
            })
        return output

    def _openalex(self, query: str, family: str, genera: list[str], rows: int) -> list[dict]:
        import requests

        response = requests.get(
            "https://api.openalex.org/works",
            params={"search": query, "per-page": rows},
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        response.raise_for_status()
        output: list[dict] = []
        for item in response.json().get("results", []):
            title = _clean(item.get("display_name"))
            score = _score(title, family, genera)
            if score < 3.0:
                continue
            doi = _clean(item.get("doi")).removeprefix("https://doi.org/") or None
            location = item.get("primary_location") or {}
            output.append({
                "title": title,
                "authors": ", ".join(
                    _clean(authorship.get("author", {}).get("display_name"))
                    for authorship in item.get("authorships", [])[:4]
                ),
                "year": item.get("publication_year"),
                "doi": doi,
                "url": _doi_url(doi) or location.get("landing_page_url") or item.get("id"),
                "provider": "OpenAlex",
                "query": query,
                "match_type": "discovery",
                "score": score,
                "open_access": (item.get("open_access") or {}).get("is_oa"),
                "verification": "discovery result; confirm that it contains an applicable key",
            })
        return output

    def _cache_path(self, family: str, genera: list[str], region: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = sha256(json.dumps([family, genera, region], ensure_ascii=False).encode()).hexdigest()[:16]
        return self.cache_dir / f"keys_{digest}.json"

    def find(
        self,
        family: str | None,
        genera: Iterable[str],
        *,
        region: str = "Europe",
        live: bool = True,
        per_query: int = 5,
        max_results: int = 12,
    ) -> dict:
        family = _clean(family)
        genera = _unique(genera)[:4]
        queries = discovery_queries(family, genera, region)
        results = self.curated(family, genera)
        errors: list[dict] = []
        cache_path = self._cache_path(family, genera, region)
        if live and cache_path and cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached["cache_hit"] = True
            return cached
        if live:
            for query in queries:
                for provider, search in (("Crossref", self._crossref), ("OpenAlex", self._openalex)):
                    try:
                        results.extend(search(query, family, genera, per_query))
                    except Exception as exc:  # one provider must not hide curated/other results
                        errors.append({"provider": provider, "query": query, "error": type(exc).__name__})
        deduplicated: dict[str, dict] = {}
        for row in results:
            identity = (_clean(row.get("doi")) or _clean(row.get("url")) or _clean(row.get("title"))).casefold()
            if not identity:
                continue
            previous = deduplicated.get(identity)
            if previous is None or float(row.get("score", 0)) > float(previous.get("score", 0)):
                deduplicated[identity] = row
        ordered = sorted(deduplicated.values(), key=lambda row: (-float(row.get("score", 0)), _clean(row.get("title"))))[:max_results]
        payload = {
            "family": family or None,
            "genera": genera,
            "region": region,
            "queries": queries,
            "results": ordered,
            "errors": errors,
            "live_search": live,
            "cache_hit": False,
            "disclaimer": "These are candidate identification resources, not confirmation of the AI identification. Check scope, edition and diagnostic characters.",
        }
        if live and cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload
