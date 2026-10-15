"""Quantization and token round-trip tests."""

from nextnote.midi_tokenizer import (
    ABS,
    BOS,
    EOS,
    REST,
    MidiTokenizer,
    decode_tokens,
    quantize_duration,
)


def test_quantize_on_16th_grid():
    assert quantize_duration(1.0) == 4   # quarter note
    assert quantize_duration(0.25) == 1  # sixteenth
    assert quantize_duration(0.5) == 2   # eighth
    assert quantize_duration(2.0) == 8   # half note


def test_quantize_rounds_and_never_returns_zero():
    assert quantize_duration(0.3) == 1   # 1.2 steps -> 1
    assert quantize_duration(0.4) == 2   # 1.6 steps -> 2
    assert quantize_duration(0.05) == 1  # sub-step -> 1
    assert quantize_duration(0.0) == 1


def test_absolute_roundtrip():
    events = [(60, 1.0), (None, 0.5), (62, 0.25), (64, 2.0)]
    tokens = MidiTokenizer(representation="absolute", order=1).encode(events)

    assert tokens[0] == BOS
    assert tokens[-1] == EOS
    assert (60, 4) in tokens

    assert decode_tokens(tokens, "absolute") == [(60, 4), (None, 2), (62, 1), (64, 8)]


def test_interval_roundtrip():
    events = [(60, 1.0), (62, 0.5), (60, 0.5), (None, 0.25), (65, 1.0)]
    tokens = MidiTokenizer(representation="interval", order=1).encode(events)

    assert tokens[1] == (ABS, 60, 4)  # first note anchored absolutely

    decoded = decode_tokens(tokens, "interval", reference_pitch=60)
    assert decoded == [(60, 4), (62, 2), (60, 2), (None, 1), (65, 4)]


def test_interval_abs_token_resets_pitch_after_restart():
    tokens = [
        BOS,
        (ABS, 60, 4),
        (2, 4),
        (ABS, 72, 4),
        (-2, 4),
        EOS,
    ]

    assert decode_tokens(tokens, "interval") == [
        (60, 4),
        (62, 4),
        (72, 4),
        (70, 4),
    ]


def test_bos_padding_count_matches_order():
    events = [(60, 1.0), (62, 1.0)]
    tokens = MidiTokenizer(representation="absolute", order=3).encode(events)
    assert tokens[:3] == [BOS, BOS, BOS]


def test_rest_token_shape():
    tokens = MidiTokenizer(representation="absolute", order=1).encode([(None, 1.0)])
    assert (REST, 4) in tokens
