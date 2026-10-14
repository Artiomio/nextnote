#!/usr/bin/env python3
"""Export the built-in ``music21`` JSB Chorales corpus to MIDI files.

Only the **JSB Chorales** corpus is used. Nothing else is downloaded: no
GiantMIDI, no Lakh MIDI, no PiJAMA, no audio. ``music21`` ships these 371
chorales with the package, so this script simply writes each one to its own
Standard MIDI File under ``data/raw/jsb_chorales/``.

Usage::

    python scripts/download_jsb.py
    python scripts/download_jsb.py --force      # re-export even if present
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# A "reasonable amount" -- the Riemenschneider set has 371 chorales.
MIN_EXPECTED_FILES = 300


def default_raw_dir():
    return (
        pathlib.Path(__file__).resolve().parents[1]
        / "data"
        / "raw"
        / "jsb_chorales"
    )


def export_corpus(raw_dir):
    """Write every built-in chorale to ``raw_dir``. Returns the count written."""
    from music21 import corpus

    raw_dir.mkdir(parents=True, exist_ok=True)
    scores = list(corpus.chorales.Iterator())
    written = 0
    for index, score in enumerate(scores, start=1):
        path = raw_dir / f"jsb_chorale_{index:03d}.mid"
        try:
            score.write("midi", fp=str(path))
            written += 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"warning: failed to export chorale {index}: {exc}", file=sys.stderr)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=None, help="Target directory for *.mid")
    parser.add_argument(
        "--force", action="store_true", help="Re-export even if the corpus exists"
    )
    args = parser.parse_args(argv)

    raw_dir = pathlib.Path(args.raw_dir) if args.raw_dir else default_raw_dir()

    existing = sorted(raw_dir.glob("*.mid")) if raw_dir.is_dir() else []
    if existing and not args.force and len(existing) >= MIN_EXPECTED_FILES:
        print(f"Corpus already present: {len(existing)} MIDI files in {raw_dir}")
        print("Nothing to do (use --force to re-export).")
        return 0

    print("Exporting the built-in music21 JSB Chorales corpus ...")
    export_corpus(raw_dir)

    found = sorted(raw_dir.glob("*.mid"))
    print(f"Found {len(found)} MIDI files in {raw_dir}")
    if len(found) < MIN_EXPECTED_FILES:
        print(
            f"ERROR: expected at least {MIN_EXPECTED_FILES} MIDI files, "
            f"found {len(found)}. The corpus was not obtained.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
