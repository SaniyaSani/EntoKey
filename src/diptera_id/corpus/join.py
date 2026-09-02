from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Callable, Iterable, Iterator

import pandas as pd


class RecordIndex:
    """Disk-backed key/value index for streaming occurrence-media joins."""

    def __init__(self, directory: str | Path | None = None):
        handle = tempfile.NamedTemporaryFile(prefix="diptera-corpus-", suffix=".sqlite", dir=directory, delete=False)
        handle.close()
        self.path = Path(handle.name)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("CREATE TABLE records (join_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def add(self, pairs: Iterable[tuple[str, dict]]) -> int:
        encoded = ((str(key), json.dumps(payload, ensure_ascii=False)) for key, payload in pairs if key)
        before = self.connection.total_changes
        self.connection.executemany("INSERT OR REPLACE INTO records(join_id, payload) VALUES (?, ?)", encoded)
        self.connection.commit()
        return self.connection.total_changes - before

    def get_many(self, keys: Iterable[str]) -> dict[str, dict]:
        unique = list(dict.fromkeys(str(key) for key in keys if key))
        found: dict[str, dict] = {}
        for start in range(0, len(unique), 800):
            batch = unique[start:start + 800]
            placeholders = ",".join("?" for _ in batch)
            query = f"SELECT join_id, payload FROM records WHERE join_id IN ({placeholders})"
            for key, payload in self.connection.execute(query, batch):
                found[key] = json.loads(payload)
        return found

    def iter_values(self, batch_size: int = 10_000) -> Iterator[dict]:
        cursor = self.connection.execute("SELECT payload FROM records")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for (payload,) in rows:
                yield json.loads(payload)

    def close(self) -> None:
        self.connection.close()
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> "RecordIndex":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def rows_from_chunk(frame: pd.DataFrame, mapper: Callable[[dict], tuple[str, dict] | None]):
    for raw in frame.to_dict(orient="records"):
        result = mapper(raw)
        if result is not None:
            yield result
