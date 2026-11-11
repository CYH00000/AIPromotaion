# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from datetime import datetime
from pathlib import Path


class JsonlLineCounter:
    """Count complete JSONL lines incrementally from staging files."""

    def __init__(self) -> None:
        self._offsets: dict[Path, int] = {}
        self._lines: dict[Path, int] = {}

    def scan(self, directory: Path) -> tuple[int, int]:
        contents = 0
        comments = 0
        if not directory.exists():
            return (contents, comments)

        for path in directory.rglob("*.jsonl"):
            count = self._scan_file(path)
            name = path.name.casefold()
            if "contents" in name:
                contents += count
            elif "comments" in name:
                comments += count
        return (contents, comments)

    def _scan_file(self, path: Path) -> int:
        try:
            size = path.stat().st_size
        except OSError:
            return self._lines.get(path, 0)

        offset = self._offsets.get(path, 0)
        count = self._lines.get(path, 0)
        if size < offset:
            offset = 0
            count = 0

        if size > offset:
            try:
                with path.open("rb") as stream:
                    stream.seek(offset)
                    chunk = stream.read()
            except OSError:
                return count
            count += chunk.count(b"\n")
            offset = size

        self._offsets[path] = offset
        self._lines[path] = count
        return count


def is_stalled(last_activity_at: datetime | None, now: datetime, timeout_seconds: int) -> bool:
    if last_activity_at is None:
        return False
    return (now - last_activity_at).total_seconds() >= timeout_seconds
