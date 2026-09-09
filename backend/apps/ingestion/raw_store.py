"""Optional raw-response retention.

Preserves a raw provider payload on disk BEFORE normalization, so a run can be
diagnosed or reprocessed. Retention is OPT-IN via settings.INGESTION_SAVE_RAW
(default False) — nothing is written unless explicitly enabled — so tests and
default runs touch no filesystem.

Files are written under settings.RAW_DATA_DIR/<source_key>/<UTC-timestamp>.json.
Licensed/private provider data written here must never be committed
(data/ is gitignored; see data/README.md).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as _tz
from pathlib import Path
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger("vessel.ingestion")


def raw_retention_enabled() -> bool:
    return bool(getattr(settings, "INGESTION_SAVE_RAW", False))


def save_raw(source_key: str, payload: Any, *, suffix: str = "") -> Optional[Path]:
    """Write `payload` as JSON under the source's raw directory. No-op (returns
    None) when retention is disabled or writing fails (never raises)."""
    if not raw_retention_enabled():
        return None
    try:
        base = Path(getattr(settings, "RAW_DATA_DIR"))
        target_dir = base / source_key
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(_tz.utc).strftime("%Y%m%dT%H%M%S%fZ")
        name = f"{stamp}{('_' + suffix) if suffix else ''}.json"
        path = target_dir / name
        path.write_text(json.dumps(payload, default=str, indent=2))
        logger.info("ingestion.raw_saved source=%s path=%s", source_key, path)
        return path
    except Exception:  # retention must never break ingestion
        logger.exception("ingestion.raw_save failed source=%s", source_key)
        return None
