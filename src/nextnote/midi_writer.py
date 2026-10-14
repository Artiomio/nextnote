"""Write generated tokens to a real Standard MIDI File and validate it."""

from __future__ import annotations

import mido

from .midi_tokenizer import STEPS_PER_QUARTER, decode_tokens

# General MIDI program 0 == Acoustic Grand Piano
ACOUSTIC_GRAND_PIANO = 0
DEFAULT_TICKS_PER_BEAT = 480
DEFAULT_VELOCITY = 64


def tokens_to_midi_file(
    tokens,
    path,
    representation="absolute",
    tempo=90,
    reference_pitch=60,
    ticks_per_beat=DEFAULT_TICKS_PER_BEAT,
    program=ACOUSTIC_GRAND_PIANO,
    velocity=DEFAULT_VELOCITY,
):
    """Write ``tokens`` to ``path`` as a single-track MIDI file.

    Returns the number of note pitches that had to be clamped into ``0..127``
    (normally 0 for the absolute representation).
    """
    notes = decode_tokens(tokens, representation, reference_pitch)

    midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)

    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))
    track.append(mido.Message("program_change", channel=0, program=program, time=0))

    ticks_per_step = ticks_per_beat // STEPS_PER_QUARTER
    pending = 0
    clamped = 0

    for pitch, steps in notes:
        delta = max(1, int(steps)) * ticks_per_step
        if pitch is None:  # rest: delay the next event
            pending += delta
            continue

        note = int(round(pitch))
        if note < 0 or note > 127:
            note = max(0, min(127, note))
            clamped += 1

        track.append(
            mido.Message("note_on", channel=0, note=note, velocity=velocity, time=pending)
        )
        pending = 0
        track.append(
            mido.Message("note_off", channel=0, note=note, velocity=0, time=delta)
        )

    # Flush a possible trailing rest so the file keeps its full duration.
    track.append(mido.MetaMessage("end_of_track", time=pending))

    midi.save(str(path))
    return clamped


def check_midi(path):
    """Re-open a MIDI file and report whether it is a usable monophonic result.

    Returns a dict with ``valid``, ``reason`` (when invalid), ``tracks``,
    ``notes``, ``duration`` (seconds), ``pitch_min``, ``pitch_max`` and
    ``note_durations_positive``.
    """
    result = {
        "path": str(path),
        "valid": False,
        "reason": "",
        "tracks": 0,
        "notes": 0,
        "duration": 0.0,
        "pitch_min": None,
        "pitch_max": None,
        "note_durations_positive": False,
    }

    try:
        midi = mido.MidiFile(str(path))
    except Exception as exc:  # noqa: BLE001
        result["reason"] = f"could not parse MIDI: {exc}"
        return result

    result["tracks"] = len(midi.tracks)
    result["duration"] = float(midi.length)

    active = {}
    note_count = 0
    pitches = []
    durations_positive = True
    absolute_time = 0.0
    ticks_per_beat = midi.ticks_per_beat
    tempo = 500000  # microseconds per beat; mido default
    seconds_per_tick = tempo / 1e6 / ticks_per_beat

    for track in midi.tracks:
        for message in track:
            absolute_time += message.time * seconds_per_tick
            if message.type == "set_tempo":
                seconds_per_tick = message.tempo / 1e6 / ticks_per_beat
            elif message.type == "note_on" and message.velocity > 0:
                active[message.note] = absolute_time
            elif message.type == "note_off" or (
                message.type == "note_on" and message.velocity == 0
            ):
                start = active.pop(message.note, None)
                if start is not None:
                    note_count += 1
                    pitches.append(message.note)
                    if absolute_time - start <= 0:
                        durations_positive = False

    result["notes"] = note_count
    result["note_durations_positive"] = durations_positive
    if pitches:
        result["pitch_min"] = min(pitches)
        result["pitch_max"] = max(pitches)

    problems = []
    if result["tracks"] < 1:
        problems.append("no tracks")
    if result["notes"] <= 0:
        problems.append("no notes")
    if result["duration"] <= 0:
        problems.append("non-positive duration")
    if pitches and not all(0 <= p <= 127 for p in pitches):
        problems.append("pitch out of 0..127")
    if not durations_positive:
        problems.append("non-positive note duration")

    result["valid"] = not problems
    result["reason"] = "; ".join(problems)
    return result
