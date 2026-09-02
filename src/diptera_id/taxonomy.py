from __future__ import annotations

from dataclasses import dataclass
from typing import Any

RANKS = ("family", "genus", "species")


@dataclass(frozen=True)
class TaxonPath:
    family: str | None = None
    genus: str | None = None
    species: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {rank: getattr(self, rank) for rank in RANKS}


def path_from_taxon(taxon: dict[str, Any], taxon_lookup: dict[int, dict[str, Any]]) -> TaxonPath:
    found: dict[str, str | None] = {rank: None for rank in RANKS}

    ids: list[int] = []
    for key in ("ancestor_ids", "ancestors"):
        raw = taxon.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, int):
                    ids.append(item)
                elif isinstance(item, dict) and isinstance(item.get("id"), int):
                    ids.append(item["id"])

    if isinstance(taxon.get("id"), int):
        ids.append(taxon["id"])

    for taxon_id in ids:
        info = taxon_lookup.get(taxon_id)
        if not info:
            if taxon_id == taxon.get("id"):
                info = taxon
            else:
                continue
        rank = info.get("rank")
        if rank in found and info.get("name"):
            found[rank] = info["name"]

    own_rank = taxon.get("rank")
    if own_rank in found and taxon.get("name"):
        found[own_rank] = taxon["name"]

    return TaxonPath(**found)
