"""LIAR dataset loading and label mapping.

The LIAR dataset (Wang, 2017) contains ~12.8k short political statements each
labelled on a 6-point truthfulness scale. We map that categorical scale onto a
continuous [0, 1] "veracity" so it can be compared against the continuous
Epistemic Integrity Score.

`datasets>=4` removed script-based loaders, and the canonical `liar` repo is
script-only, so we fetch the original TSV bundle directly (with mirrors) and
cache it. No manual download is required.
"""

from __future__ import annotations

import csv
import io
import urllib.request
import zipfile
from pathlib import Path

from observability import get_logger

_log = get_logger("evaluation.liar")

# 6-point LIAR scale -> continuous veracity in [0, 1].
LABEL_TO_SCORE: dict[str, float] = {
    "pants-fire": 0.0,
    "false": 0.2,
    "barely-true": 0.4,
    "half-true": 0.6,
    "mostly-true": 0.8,
    "true": 1.0,
}

# HuggingFace's `liar` config exposes the label as an int ClassLabel in this order.
_INT_ORDER = ["false", "half-true", "mostly-true", "true", "barely-true", "pants-fire"]

# LIAR credit-history columns (0-indexed) hold the speaker's PAST counts,
# excluding the current statement. There is no "true" column in LIAR.
#   [8]=barely-true [9]=false [10]=half-true [11]=mostly-true [12]=pants-fire
_CREDIT_COLS: list[tuple[int, float]] = [
    (8, 0.4),
    (9, 0.2),
    (10, 0.6),
    (11, 0.8),
    (12, 0.0),
]


def _speaker_prior(cols: list[str]) -> float:
    """Speaker's a-priori credibility in [0,1] from their credit history.

    A veracity-weighted average of the speaker's historical rating counts.
    Returns 0.5 (neutral) when the speaker has no history. This is standard,
    non-leaking LIAR metadata (counts exclude the current statement).
    """
    total = 0.0
    weighted = 0.0
    for idx, score in _CREDIT_COLS:
        if idx < len(cols):
            try:
                c = float(cols[idx])
            except (ValueError, TypeError):
                c = 0.0
            total += c
            weighted += c * score
    return weighted / total if total > 0 else 0.5

_ZIP_URLS = [
    "https://www.cs.ucsb.edu/~william/data/liar_dataset.zip",
    "https://huggingface.co/datasets/ucsbnlp/liar/resolve/main/liar_dataset.zip",
]
_SPLIT_FILE = {"train": "train.tsv", "validation": "valid.tsv", "test": "test.tsv"}
_CACHE = Path.home() / ".cache" / "epis-kg" / "liar_dataset.zip"


def _label_to_name(label) -> str | None:  # noqa: ANN001
    if isinstance(label, str):
        return label if label in LABEL_TO_SCORE else None
    if isinstance(label, int) and 0 <= label < len(_INT_ORDER):
        return _INT_ORDER[label]
    return None


def _download_zip() -> bytes:
    if _CACHE.exists():
        return _CACHE.read_bytes()
    last_err: Exception | None = None
    for url in _ZIP_URLS:
        try:
            _log.info("liar_download", url=url)
            req = urllib.request.Request(url, headers={"User-Agent": "epis-kg/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                data = resp.read()
            _CACHE.parent.mkdir(parents=True, exist_ok=True)
            _CACHE.write_bytes(data)
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            _log.warning("liar_download_failed", url=url, error=str(exc))
    raise RuntimeError(f"could not download LIAR dataset from any mirror: {last_err}")


def load_liar(split: str = "validation", limit: int | None = None) -> list[dict]:
    """Return a list of ``{"statement", "label", "score"}`` dicts.

    Downloads and caches the original LIAR TSV bundle automatically.
    """
    if split not in _SPLIT_FILE:
        raise ValueError(f"unknown split '{split}' (use train|validation|test)")

    _log.info("liar_load", split=split, limit=limit)
    zip_bytes = _download_zip()
    rows: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open(_SPLIT_FILE[split]) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8")
            for cols in csv.reader(text, delimiter="\t"):
                # LIAR columns: [0]=id [1]=label [2]=statement [3..]=metadata
                if len(cols) < 3:
                    continue
                name = _label_to_name(cols[1].strip())
                statement = cols[2].strip()
                if name is None or not statement:
                    continue
                rows.append(
                    {
                        "statement": statement,
                        "label": name,
                        "score": LABEL_TO_SCORE[name],
                        "speaker": cols[4].strip() if len(cols) > 4 else "",
                        "prior_credibility": _speaker_prior(cols),
                    }
                )
                if limit is not None and len(rows) >= limit:
                    break
    _log.info("liar_loaded", rows=len(rows))
    return rows
