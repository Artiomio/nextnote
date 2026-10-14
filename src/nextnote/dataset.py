"""Loading the JSB Chorales corpus and extracting the soprano line.

The corpus on disk is a folder of Standard MIDI Files produced by
``scripts/download_jsb.py`` (the built-in ``music21`` Bach chorale corpus).
Each file is one chorale, i.e. one independent training sequence.
"""

from __future__ import annotations

import pathlib

from music21 import converter

from .midi_tokenizer import MidiTokenizer

MIN_EXPECTED_FILES = 300  # the Riemenschneider set has 371 chorales


def project_root():
    """``.../nextnote`` regardless of the current working directory."""
    return pathlib.Path(__file__).resolve().parents[2]


def default_raw_dir():
    return project_root() / "data" / "raw" / "jsb_chorales"


def default_output_dir():
    return project_root() / "output"


def list_midi_files(raw_dir=None):
    """Return the sorted list of ``*.mid`` files in ``raw_dir``."""
    raw_dir = pathlib.Path(raw_dir) if raw_dir is not None else default_raw_dir()
    if not raw_dir.is_dir():
        return []
    return sorted(raw_dir.glob("*.mid"))


def _average_pitch(part):
    pitches = [n.pitch.midi for n in part.flatten().notes if hasattr(n, "pitch")]
    return sum(pitches) / len(pitches) if pitches else -1.0


def pick_soprano_part(score, stats=None):
    """Pick the top voice of ``score``.

    Preference order:

    1. a part whose name contains ``soprano`` (the exported JSB chorales do);
    2. otherwise the part with the highest average pitch.

    Returns ``None`` for an empty score.
    """
    parts = list(score.parts)
    if not parts:
        return None

    for part in parts:
        name = (part.partName or "").lower()
        if "soprano" in name:
            return part

    if stats is not None:
        stats.warn(
            "no part named 'soprano'; falling back to the highest-average-pitch part"
        )
    return max(parts, key=_average_pitch)


def extract_soprano(score, stats=None):
    """Return ``[(midi_pitch_or_None, quarter_length), ...]`` for the top voice.

    * ties are merged (``stripTies``);
    * a chord found in the soprano part is reduced to its **highest** note
      (documented compromise for the monophonic first version, counted in
      ``stats.chords``);
    * rests are kept as ``(None, quarter_length)``.
    """
    part = pick_soprano_part(score, stats)
    if part is None:
        return []

    events = []
    for element in part.flatten().stripTies().notesAndRests:
        duration = float(element.quarterLength)
        if element.isRest:
            events.append((None, duration))
        elif element.isChord:
            if stats is not None:
                stats.chords += 1
            events.append((max(p.midi for p in element.pitches), duration))
        elif element.isNote:
            events.append((element.pitch.midi, duration))
    return events


def load_chorale_events(path, stats=None):
    """Parse one MIDI file and return its soprano note events."""
    score = converter.parse(str(path))
    return extract_soprano(score, stats)


def load_corpus_events(raw_dir=None, stats=None, limit=None):
    """Parse every chorale once and return a list of soprano note-event lists.

    Parsing MIDI is the expensive step, so it is done once and the result can be
    re-encoded for several Markov orders / representations. ``limit`` caps the
    number of parsed files (handy for fast tests).
    """
    corpus = []
    for path in list_midi_files(raw_dir):
        if limit is not None and len(corpus) >= limit:
            break
        try:
            events = load_chorale_events(path, stats)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            if stats is not None:
                stats.skipped_sequences += 1
                stats.warn(f"could not parse {path.name}: {exc}")
            continue

        if not events:
            if stats is not None:
                stats.empty_sequences += 1
                stats.warn(f"empty soprano line in {path.name}")
            continue

        corpus.append(events)
        if stats is not None:
            stats.sequences += 1
    return corpus


def encode_corpus(corpus_events, representation="absolute", order=1,
                  reference_pitch=60, stats=None):
    """Tokenize a corpus of note-event lists into independent token sequences."""
    tokenizer = MidiTokenizer(
        representation=representation, order=order, reference_pitch=reference_pitch
    )
    return [tokenizer.encode(events, stats) for events in corpus_events]


def build_sequences(
    raw_dir=None,
    representation="absolute",
    order=1,
    reference_pitch=60,
    stats=None,
):
    """Parse + tokenize every chorale into independent token sequences.

    Returns ``(sequences, tokenizer)``. Sequences that cannot be parsed or are
    empty are skipped and counted in ``stats``.
    """
    corpus = load_corpus_events(raw_dir, stats)
    sequences = encode_corpus(
        corpus, representation=representation, order=order,
        reference_pitch=reference_pitch, stats=stats,
    )
    tokenizer = MidiTokenizer(
        representation=representation, order=order, reference_pitch=reference_pitch
    )
    return sequences, tokenizer
