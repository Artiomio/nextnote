"""Full experiment: JSB Chorales -> soprano -> tokens -> Markov -> MIDI.

Run with::

    python -m nextnote.experiment \
        --representation absolute \
        --orders 1 3 5 \
        --length 200 \
        --tempo 90 \
        --seed 42 \
        --output-dir output
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

from nexttoken import MarkovChain

from .dataset import (
    default_raw_dir,
    encode_corpus,
    list_midi_files,
    load_corpus_events,
)
from .midi_tokenizer import BOS, EOS, TokenizationStats
from .midi_writer import check_midi, tokens_to_midi_file


def _token_to_str(token):
    return token if isinstance(token, str) else repr(token)


def _musical_token_count(sequences):
    """Number of tokens excluding the special BOS/EOS markers."""
    return sum(
        1
        for sequence in sequences
        for token in sequence
        if token != BOS and token != EOS
    )


def _report_lines(report):
    lines = [f"{pathlib.Path(report['path']).name}:"]
    lines.append(f"  valid: {'yes' if report['valid'] else 'no'}")
    if not report["valid"]:
        lines.append(f"  reason: {report['reason']}")
    lines.append(f"  notes: {report['notes']}")
    lines.append(f"  duration: {report['duration']:.1f} seconds")
    if report["pitch_min"] is not None:
        lines.append(f"  pitch range: {report['pitch_min']}\u2013{report['pitch_max']}")
    return lines


def run_experiment(args):
    raw_dir = pathlib.Path(args.raw_dir) if args.raw_dir else default_raw_dir()
    output_dir = pathlib.Path(args.output_dir)

    files = list_midi_files(raw_dir)
    if not files:
        print(f"No JSB Chorales MIDI files found in: {raw_dir}")
        print("Export/download the corpus first (only JSB Chorales is used):")
        print("    python scripts/download_jsb.py")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Corpus directory : {raw_dir}")
    print(f"Found {len(files)} MIDI files")

    token_stats = TokenizationStats()
    started = time.time()
    corpus_events = load_corpus_events(raw_dir, token_stats)
    print(f"Parsed {len(corpus_events)} chorales in {time.time() - started:.2f} s")

    min_tokens = args.min_tokens if args.min_tokens is not None else args.length
    summaries = []
    reports = []

    for index, order in enumerate(args.orders):
        sequences = encode_corpus(
            corpus_events,
            representation=args.representation,
            order=order,
            reference_pitch=args.reference_pitch,
            stats=token_stats if index == 0 else None,
        )
        total_tokens = _musical_token_count(sequences)

        model = MarkovChain(order=order, random_seed=args.seed)
        model.fit(sequences)

        generated = model.generate(
            initial_context=[BOS] * order,
            max_tokens=args.length,
            dead_end_strategy="restart",
            stop_tokens=[EOS],
            min_tokens=min_tokens,
        )

        midi_path = output_dir / f"bach_markov_order_{order}.mid"
        tokens_path = output_dir / f"bach_markov_order_{order}.tokens.txt"
        clamped = tokens_to_midi_file(
            generated,
            midi_path,
            representation=args.representation,
            tempo=args.tempo,
            reference_pitch=args.reference_pitch,
        )
        tokens_path.write_text(
            "\n".join(_token_to_str(token) for token in generated) + "\n",
            encoding="utf-8",
        )
        report = check_midi(midi_path)
        reports.append(report)

        summaries.append(
            {
                "order": order,
                "musical_tokens": total_tokens,
                "vocab": len(model.vocabulary),
                "contexts": len(model.unique_contexts),
                "dead_ends": model.last_dead_end_count,
                "fit_time": model.fit_time,
                "generated": len(generated),
                "clamped": clamped,
                "report": report,
            }
        )

    # ---------------------------------------------------------- reporting
    print()
    print("Tokenization")
    print(f"  chorales processed : {token_stats.sequences}")
    print(
        "  chorales skipped   : "
        f"{token_stats.skipped_sequences + token_stats.empty_sequences}"
    )
    print(f"  notes              : {token_stats.notes}")
    print(f"  rests              : {token_stats.rests}")
    print(f"  chords in soprano  : {token_stats.chords} (highest note kept)")
    print(f"  short durations    : {token_stats.short_durations} (< 1/16 note)")
    print(f"  rounded durations  : {token_stats.rounded_durations} (not on 1/16 grid)")
    for warning in token_stats.warnings[:10]:
        print(f"  warning: {warning}")
    if len(token_stats.warnings) > 10:
        print(f"  ... and {len(token_stats.warnings) - 10} more warnings")

    print()
    print("Models")
    header = (
        f"  {'order':>5} {'tokens':>8} {'vocab':>6} {'contexts':>9} "
        f"{'dead-ends':>9} {'fit(s)':>8} {'generated':>9}"
    )
    print(header)
    for summary in summaries:
        print(
            f"  {summary['order']:>5} {summary['musical_tokens']:>8} "
            f"{summary['vocab']:>6} {summary['contexts']:>9} "
            f"{summary['dead_ends']:>9} {summary['fit_time']:>8.2f} "
            f"{summary['generated']:>9}"
        )

    print()
    print("Generated MIDI")
    for report in reports:
        print("\n".join(_report_lines(report)))

    ok = all(report["valid"] for report in reports)
    print()
    print("All MIDI files valid: " + ("yes" if ok else "NO"))
    for report in reports:
        if not report["valid"]:
            print(f"  {report['path']}: {report['reason']}")
    return 0 if ok else 1


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--representation",
        choices=["absolute", "interval"],
        default="absolute",
    )
    parser.add_argument("--orders", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--length", type=int, default=200, help="Musical tokens to generate")
    parser.add_argument("--tempo", type=int, default=90, help="Tempo in BPM")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--reference-pitch", type=int, default=60)
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=None,
        help="Minimum length before EOS may stop generation (default: --length)",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    return run_experiment(args)


if __name__ == "__main__":
    sys.exit(main())
