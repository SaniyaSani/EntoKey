from diptera_id.taxonomy import path_from_taxon


def test_taxon_path_from_ancestor_ids():
    taxon = {"id": 30, "name": "Example species", "rank": "species", "ancestor_ids": [10, 20]}
    lookup = {
        10: {"id": 10, "name": "Exampleidae", "rank": "family"},
        20: {"id": 20, "name": "Example", "rank": "genus"},
        30: taxon,
    }
    path = path_from_taxon(taxon, lookup)
    assert path.family == "Exampleidae"
    assert path.genus == "Example"
    assert path.species == "Example species"
