"""Corpus-level tests. Skipped automatically when the corpus is not exported."""

import pytest

from nextnote.dataset import (
    default_raw_dir,
    encode_corpus,
    list_midi_files,
    load_corpus_events,
)
from nextnote.midi_tokenizer import BOS, EOS, TokenizationStats

_corpus_files = list_midi_files(default_raw_dir())
pytestmark = pytest.mark.skipif(
    not _corpus_files, reason="JSB Chorales corpus not downloaded"
)


def test_corpus_has_a_reasonable_number_of_files():
    assert len(_corpus_files) >= 300


def test_soprano_extraction_and_tokenization():
    stats = TokenizationStats()
    corpus = load_corpus_events(default_raw_dir(), stats, limit=20)

    assert corpus
    assert stats.sequences == len(corpus)

    # notes/rests are counted while encoding
    encode_stats = TokenizationStats()
    sequences = encode_corpus(
        corpus, representation="absolute", order=1, stats=encode_stats
    )
    assert encode_stats.notes > 0

    for sequence in sequences:
        assert sequence[0] == BOS
        assert sequence[-1] == EOS
        # every non-special token is a (pitch, duration) pair with a real pitch
        for token in sequence[1:-1]:
            assert isinstance(token, tuple)
            assert token[0] == "REST" or 0 <= token[0] <= 127
            assert token[1] >= 1
