"""Lightweight progress tracker – persists completed URLs to JSON for resume."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_FLUSH_EVERY = 10


class ProgressTracker:
    """Track completed URLs so a crawl can resume after interruption."""

    def __init__(
        self,
        output_dir: Path,
        *,
        enabled: bool = True,
        load_existing: bool = True,
    ) -> None:
        self._path = Path(output_dir) / "progress.json"
        self._enabled = enabled
        self._done: set[str] = set()
        self._dirty = False
        self._marks_since_flush = 0

        if enabled and load_existing and self._path.exists():
            self._load()

    # ------------------------------------------------------------------
    def is_done(self, url: str) -> bool:
        if not self._enabled:
            return False
        return url in self._done

    def mark_done(self, url: str) -> None:
        if not self._enabled:
            return
        if url in self._done:
            return
        self._done.add(url)
        self._dirty = True
        self._marks_since_flush += 1
        if self._marks_since_flush >= _FLUSH_EVERY:
            self.flush()

    def flush(self) -> None:
        if not self._enabled:
            return
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "completed_urls": sorted(self._done),
            "count": len(self._done),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        data = json.dumps(payload, indent=2)
        # Atomic write via temp file + rename
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp, str(self._path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._dirty = False
        self._marks_since_flush = 0

    def reset(self) -> None:
        if not self._enabled:
            return
        self._done.clear()
        self._dirty = False
        self._marks_since_flush = 0
        if self._path.exists():
            self._path.unlink()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._done = set(data.get("completed_urls", []))
        except (json.JSONDecodeError, OSError):
            self._done = set()
