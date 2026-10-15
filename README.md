# nextnote

Monophonic music generation built on top of the universal Markov core from
[`nexttoken-core`](https://github.com/Artiomio/nexttoken-core). This is an
*extension* of the original
[`nexttoken`](https://github.com/Artiomio/nexttoken) idea, not a rewrite: the
n-th order Markov chain (counting, normalization, `np.random.choice`, context
shifting) is **imported from `nexttoken_core`**, never duplicated here. The
original `nexttoken` repo is kept unchanged for teaching; the reusable core
lives in `nexttoken-core`.

`nextnote` adds only the music-specific parts:

* obtaining a small corpus of Bach chorales;
* turning the soprano line into a sequence of discrete tokens;
* writing the generated tokens back out as real, playable MIDI files.

## First version at a glance

> Download a small JSB Chorales corpus, extract the soprano (top) voice from
> every chorale, represent the music as a sequence of discrete tokens, train the
> existing Markov chain and produce real, playable MIDI files.

Only the **JSB Chorales** corpus is used. No GiantMIDI, Lakh MIDI, PiJAMA,
Weimar Jazz Database, no other corpora and no audio. No neural networks, no GUI,
no polyphonic generation.

## Where the corpus comes from

The corpus is the built-in **JSB Chorales** collection shipped with
[`music21`](https://music21.org/music21docs/moduleReference/moduleCorpusChorales.html)
(`music21.corpus.chorales`, the 371-chorale Riemenschneider set). `music21`
ships these files with the package, so nothing extra is downloaded from the
internet; `scripts/download_jsb.py` simply exports each chorale to its own
Standard MIDI File:

```text
data/raw/jsb_chorales/jsb_chorale_001.mid
data/raw/jsb_chorales/jsb_chorale_002.mid
...
```

The script is idempotent: if the corpus is already present it does nothing, and
it fails with a clear error if fewer than 300 files are found.

## Why only the soprano?

The first model is deliberately **monophonic**: it isolates the Markov-chain
experiment from the separate, harder problem of representing polyphony. We take
the top voice only, so a piece is a single stream of notes and rests. Chords in
the soprano part (rare; 8 occurrences in the whole corpus) are reduced to their
**highest** note.

## What is a musical token?

A token is any hashable Python object. On a 1/16-note grid
(`duration_steps`, 4 steps = 1 quarter note):

| token                        | meaning                                  |
| ---------------------------- | ---------------------------------------- |
| `(midi_pitch, duration_steps)` | a note (absolute mode), e.g. `(60, 4)` |
| `(pitch_interval, duration_steps)` | a note (interval mode)             |
| `("ABS", midi_pitch, duration_steps)` | first note in interval mode      |
| `("REST", duration_steps)`   | a rest                                   |
| `"BOS"` / `"EOS"`            | begin / end of a piece                   |

Each chorale is tokenized independently; a transition between the last token of
one chorale and the first token of the next one is **never** created.

Two representations are available:

* `absolute` — notes by absolute MIDI pitch (used for the first baseline);
* `interval` — notes by interval from the previous sounding note. The first
  note of every fragment is an explicit `("ABS", pitch, duration)` anchor, so
  the same melodic contour in different keys shares transition statistics.

Rests do not reset the previous sounding pitch. A dead-end restart is pinned to
the `BOS` context; in interval mode this makes the next fragment begin with a
fresh `ABS` anchor instead of silently continuing interval arithmetic from an
unrelated training context.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .              # installs nexttoken-core from GitHub automatically
```

`nextnote` depends on the shared Markov core
[`nexttoken-core`](https://github.com/Artiomio/nexttoken-core) (import name
`nexttoken_core`), declared in `pyproject.toml` as a git dependency pinned to the tested core
commit, so reinstalling the same `nextnote` revision does not silently change
the Markov implementation:

```text
nexttoken-core @ git+https://github.com/Artiomio/nexttoken-core.git@f618273b3a44663750e7ef9748bcc99f5296c4a2
```

For local development, install the sibling checkout as an editable dependency
instead:

```bash
pip install -e ../nexttoken-core
pip install -e . --no-deps
```

`nextnote` imports `MarkovChain` from `nexttoken_core` — see
`src/nextnote/experiment.py`.

## Download the corpus

```bash
python scripts/download_jsb.py
```

Re-running the command is safe (it skips an already-exported corpus). Output:

```text
Found 370 MIDI files in .../data/raw/jsb_chorales
```

## Run the experiment

```bash
python -m nextnote.experiment \
    --representation absolute \
    --orders 1 3 5 \
    --length 200 \
    --tempo 90 \
    --seed 42 \
    --output-dir output
```

By default `EOS` is masked until 75% of `--length` has been generated
(150 tokens for a length of 200). After that the piece may end naturally; the
hard limit is still `--length`. Override this with `--min-tokens`.

The command:

1. checks that the corpus exists (and otherwise tells you to run the downloader);
2. parses every chorale and extracts the soprano;
3. tokenizes each chorale into an independent sequence;
4. trains Markov models of orders `1`, `3` and `5` on the same sequences;
5. generates ~200 musical tokens per model;
6. writes real MIDI files;
7. re-opens every MIDI file and validates it;
8. prints tokenization, model and validation statistics.

## Output

```text
output/bach_markov_order_1.mid
output/bach_markov_order_3.mid
output/bach_markov_order_5.mid
```

Each file is a Standard MIDI File with a single track, Acoustic Grand Piano
(program 0), 90 BPM, real `note_on`/`note_off` events accounting for token
durations and rests.

For an absolute-vs-interval comparison, keep the outputs separate so the
second run does not overwrite the first:

```bash
python -m nextnote.experiment \
    --representation absolute \
    --orders 1 3 5 \
    --length 200 \
    --seed 42 \
    --output-dir output/absolute

python -m nextnote.experiment \
    --representation interval \
    --orders 1 3 5 \
    --length 200 \
    --seed 42 \
    --output-dir output/interval
```

The model table reports vocabulary size, unique contexts, dead-end restarts and
`clamped` pitches. In interval mode, a non-zero clamped count is useful
diagnostic information: it means cumulative intervals drifted outside MIDI
pitch range `0..127`.

Alongside every `.mid` a debug dump of the generated tokens is written:

```text
output/bach_markov_order_1.tokens.txt
output/bach_markov_order_3.tokens.txt
output/bach_markov_order_5.tokens.txt
```

### Listening to the result

Any MIDI player works, for example:

```bash
timidity output/bach_markov_order_3.mid
# or
vlc output/bach_markov_order_3.mid
```

`data/`, `models/`, `output/` and `*.mid` are git-ignored; the empty directories
are kept with `.gitkeep` files.

## Tests

```bash
pytest                    # run from nextnote/
```

## Limitations of a monophonic Markov model

* Only the soprano voice is modelled; there is no harmony or counterpoint.
* Very short contexts (order 1) produce aimless wandering; higher orders are
  closer to the corpus but eventually hit unseen contexts.
* A Markov chain has **no** notion of global musical form, phrase structure or a
  tonal centre; the interval representation in particular can drift in pitch
  (out-of-range pitches are clamped to `0..127`).
* Dead-end contexts are handled by a `restart` strategy. `nextnote` restarts
  specifically from `BOS`; in interval mode that also re-establishes an
  absolute pitch anchor. This is not a real backoff: the model does not build
  statistics for shorter contexts.
* There is no train/validation split yet.
