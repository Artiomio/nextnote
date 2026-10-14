"""Monophonic (soprano) note stream <-> discrete hashable tokens.

A musical token is deliberately just a plain hashable Python object so that
the universal Markov core in :mod:`nexttoken` can consume it without knowing
anything about music:

* note (absolute):    ``(midi_pitch, duration_steps)``   e.g. ``(60, 4)``
* note (interval):    ``(pitch_interval, duration_steps)``
* first interval note:``("ABS", midi_pitch, duration_steps)``
* rest:               ``("REST", duration_steps)``
* special:            the strings ``"BOS"`` and ``"EOS"``

``duration_steps`` is measured on a 1/16-note grid, i.e. 4 steps == 1 quarter
note (see :data:`STEPS_PER_QUARTER`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 1/16-note grid: four steps per quarter note.
STEPS_PER_QUARTER = 4

BOS = "BOS"
EOS = "EOS"
REST = "REST"
ABS = "ABS"

REPRESENTATIONS = ("absolute", "interval")


@dataclass
class TokenizationStats:
    """Counters + warnings collected while quantizing/tokenizing a corpus."""

    sequences: int = 0
    skipped_sequences: int = 0
    empty_sequences: int = 0
    notes: int = 0
    rests: int = 0
    chords: int = 0
    short_durations: int = 0
    rounded_durations: int = 0
    warnings: list = field(default_factory=list)

    def warn(self, message):
        self.warnings.append(message)


def quantize_duration(quarter_length, steps_per_quarter=STEPS_PER_QUARTER, stats=None):
    """Quantize a duration in quarter notes to an integer number of steps.

    * non-multiples of the grid are rounded to the nearest step (counted in
      ``stats.rounded_durations``);
    * durations shorter than one step become exactly one step (counted in
      ``stats.short_durations``) so that every sounded note survives.
    """
    steps_float = float(quarter_length) * steps_per_quarter
    steps = int(round(steps_float))
    if stats is not None and abs(steps_float - steps) > 1e-6:
        stats.rounded_durations += 1
    if steps < 1:
        steps = 1
        if stats is not None and quarter_length > 0:
            stats.short_durations += 1
    return steps


class MidiTokenizer:
    """Encode a monophonic note stream as a list of musical tokens.

    ``note_events`` is an iterable of ``(midi_pitch_or_None, quarter_length)``
    pairs, where ``None`` pitch means a rest.
    """

    def __init__(
        self,
        representation="absolute",
        order=1,
        steps_per_quarter=STEPS_PER_QUARTER,
        reference_pitch=60,
    ):
        if representation not in REPRESENTATIONS:
            raise ValueError(
                "representation must be one of %r, got %r"
                % (REPRESENTATIONS, representation)
            )
        self.representation = representation
        self.order = int(order)
        self.steps_per_quarter = steps_per_quarter
        self.reference_pitch = reference_pitch

    def encode(self, note_events, stats=None):
        tokens = [BOS] * self.order
        previous_pitch = None
        for pitch, quarter_length in note_events:
            duration = quantize_duration(
                quarter_length, self.steps_per_quarter, stats
            )
            if pitch is None:
                tokens.append((REST, duration))
                if stats is not None:
                    stats.rests += 1
                continue

            if stats is not None:
                stats.notes += 1

            if self.representation == "absolute":
                tokens.append((int(pitch), duration))
            else:
                if previous_pitch is None:
                    tokens.append((ABS, int(pitch), duration))
                else:
                    tokens.append((int(pitch) - previous_pitch, duration))
                previous_pitch = int(pitch)

        tokens.append(EOS)
        return tokens


def decode_tokens(tokens, representation="absolute", reference_pitch=60):
    """Inverse of :meth:`MidiTokenizer.encode`.

    Returns a list of ``(midi_pitch_or_None, duration_steps)`` pairs. ``BOS``
    and ``EOS`` are skipped. For the interval representation the first note is
    anchored at ``reference_pitch`` unless an explicit ``("ABS", ...)`` token
    is present.
    """
    if representation not in REPRESENTATIONS:
        raise ValueError(
            "representation must be one of %r, got %r"
            % (REPRESENTATIONS, representation)
        )

    notes = []
    previous_pitch = reference_pitch
    for token in tokens:
        if token == BOS or token == EOS:
            continue
        if not isinstance(token, tuple):
            continue

        head = token[0]
        if head == REST:
            notes.append((None, int(token[1])))
        elif head == ABS:
            pitch = int(token[1])
            notes.append((pitch, int(token[2])))
            previous_pitch = pitch
        elif representation == "interval":
            pitch = previous_pitch + int(token[0])
            notes.append((pitch, int(token[1])))
            previous_pitch = pitch
        else:  # absolute note token (pitch, duration)
            notes.append((int(head), int(token[1])))
    return notes
