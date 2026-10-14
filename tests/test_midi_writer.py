"""Writing tokens to MIDI and re-reading them for validation."""

from nextnote.midi_tokenizer import BOS, EOS, REST, MidiTokenizer
from nextnote.midi_writer import check_midi, tokens_to_midi_file


def test_write_and_reopen_midi(tmp_path):
    events = [(60, 1.0), (62, 0.5), (None, 0.5), (64, 1.0)]
    tokens = MidiTokenizer(representation="absolute", order=1).encode(events)

    path = tmp_path / "short.mid"
    tokens_to_midi_file(tokens, path, tempo=90)

    assert path.exists()
    assert path.stat().st_size > 0

    report = check_midi(path)
    assert report["valid"], report["reason"]
    assert report["notes"] == 3
    assert report["duration"] > 0
    assert report["pitch_min"] == 60
    assert report["pitch_max"] == 64
    assert report["note_durations_positive"]


def test_trailing_rest_keeps_duration(tmp_path):
    tokens = [BOS, (60, 4), (REST, 4), EOS]
    path = tmp_path / "rest.mid"
    tokens_to_midi_file(tokens, path, tempo=90)

    report = check_midi(path)
    assert report["valid"], report["reason"]
    # 8 steps == 2 quarter notes at 90 BPM ~= 1.33 s
    assert report["duration"] > 1.0


def test_out_of_range_pitch_is_clamped(tmp_path):
    tokens = [BOS, (200, 4), (-10, 4), EOS]
    path = tmp_path / "clamp.mid"
    clamped = tokens_to_midi_file(tokens, path, tempo=90)

    assert clamped == 2
    report = check_midi(path)
    assert report["valid"], report["reason"]
    assert 0 <= report["pitch_min"] <= report["pitch_max"] <= 127


def test_tokens_to_midi_pipeline(tmp_path):
    """End-to-end: fit the nexttoken_core Markov core, generate, write, validate."""
    from nexttoken_core import MarkovChain

    events = [(60, 1.0), (62, 1.0), (64, 1.0), (65, 1.0)]
    tokens = MidiTokenizer(representation="absolute", order=1).encode(events)

    model = MarkovChain(order=1, random_seed=42).fit([tokens])
    generated = model.generate(
        initial_context=[BOS], max_tokens=20, stop_tokens=[EOS], min_tokens=5
    )

    path = tmp_path / "generated.mid"
    tokens_to_midi_file(generated, path, tempo=90)

    report = check_midi(path)
    assert report["valid"], report["reason"]
    assert report["notes"] > 0
    assert report["duration"] > 0
