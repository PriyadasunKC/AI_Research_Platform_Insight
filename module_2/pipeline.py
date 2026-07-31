"""
pipeline.py — Main entry point for the Sinhala Historical KG extraction pipeline

Pipeline stages:
    1. NER           → ner_pipeline.run_ner(sentence)
    2. Normalization → normalizer.normalize_entity() (applied inside extractor)
    3. Extraction    → deepseek_relation_extractor.extract_relations()
    4. Output        → list of validated triple dicts

Usage (interactive):
    python pipeline.py
    python pipeline.py --sentence "දුටුගැමුණු රජු රුවන්වැලිසෑය ඉදිකළේය."
    python pipeline.py --file sentences.txt --output triples.json

Usage (as library):
    from pipeline import run_pipeline, run_pipeline_batch
    triples = run_pipeline("දුටුගැමුණු රජු රුවන්වැලිසෑය ඉදිකළේය.")

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from relation_extractor import extract_relations
from ner_pipeline import NERTag, run_ner

load_dotenv()


# DATA TYPES

class PipelineResult:
    """Container for the output of one sentence through the full pipeline."""

    def __init__(
        self,
        sentence: str,
        ner_tags: list[NERTag],
        triples: list[dict],
    ) -> None:
        self.sentence = sentence
        self.ner_tags = ner_tags
        self.triples  = triples

    def to_dict(self) -> dict:
        return {
            "sentence": self.sentence,
            "ner_tags": [{"entity": t.entity, "label": t.label} for t in self.ner_tags],
            "triples":  self.triples,
        }

    def __repr__(self) -> str:
        return (
            f"PipelineResult(\n"
            f"  sentence = {self.sentence!r}\n"
            f"  ner_tags = {self.ner_tags}\n"
            f"  triples  = {self.triples}\n"
            f")"
        )


# CORE PIPELINE FUNCTIONS

def run_pipeline(
    sentence: str,
    verbose: bool = False,
) -> PipelineResult:
    """
    Run the full pipeline for a single Sinhala sentence.

    Stage 1 → NER
    Stage 2 → DeepSeek relation extraction (with entity/relation normalization)
    Stage 3 → Return validated triples

    Args:
        sentence: Raw Sinhala sentence string.
        verbose:  Print stage outputs if True.

    Returns:
        PipelineResult with .ner_tags and .triples populated.
    """
    sentence = sentence.strip()
    if not sentence:
        return PipelineResult(sentence="", ner_tags=[], triples=[])

    # Stage 1: NER 
    if verbose:
        print(f"\n{'═' * 60}")
        print(f"STAGE 1 — NER")
        print(f"Input: {sentence}")

    ner_tags = run_ner(sentence)

    if verbose:
        print(f"NER output:")
        for tag in ner_tags:
            print(f"  [{tag.label}] {tag.entity}")

    if not ner_tags:
        if verbose:
            print("No entities found — skipping relation extraction.")
        return PipelineResult(sentence=sentence, ner_tags=[], triples=[])

    # Stage 2: Relation Extraction
    if verbose:
        print(f"\nSTAGE 2 — DeepSeek Relation Extraction")

    triples = extract_relations(sentence, ner_tags, verbose=verbose)

    if verbose:
        print(f"\nSTAGE 3 — Final Output")
        if triples:
            for t in triples:
                period_str = f"  [period: {t['period']}]" if t.get("period") else ""
                print(f"  ({t['subject']}) --[{t['relation']}]--> ({t['object']}){period_str}")
        else:
            print("  No valid triples extracted.")

    return PipelineResult(sentence=sentence, ner_tags=ner_tags, triples=triples)


def run_pipeline_batch(
    sentences: list[str],
    verbose: bool = False,
) -> list[PipelineResult]:
    """
    Run the pipeline on a list of sentences.

    Args:
        sentences: List of Sinhala sentence strings.
        verbose:   Print per-sentence details if True.

    Returns:
        List of PipelineResult objects (same order as input).
    """
    results: list[PipelineResult] = []
    total = len(sentences)
    for i, sentence in enumerate(sentences, start=1):
        if not sentence.strip():
            continue
        print(f"[{i:>4}/{total}] Processing: {sentence[:60]}{'…' if len(sentence) > 60 else ''}")
        try:
            result = run_pipeline(sentence, verbose=verbose)
            results.append(result)
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append(PipelineResult(sentence=sentence, ner_tags=[], triples=[]))
    return results


def collect_triples(results: list[PipelineResult]) -> list[dict]:
    """
    Flatten all triples from a batch of PipelineResults into a single list.
    Attaches source_sentence provenance to each triple.
    """
    all_triples: list[dict] = []
    for r in results:
        for t in r.triples:
            all_triples.append({**t, "source_sentence": r.sentence})
    return all_triples


# CLI ENTRY POINT

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sinhala Historical KG — Relation Extraction Pipeline (Module 2)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--sentence", "-s",
        type=str,
        help="Single Sinhala sentence to process",
    )
    group.add_argument(
        "--file", "-f",
        type=Path,
        help="Path to a text file with one Sinhala sentence per line",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Optional path to save output JSON (e.g. triples.json)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print intermediate pipeline stages",
    )
    parser.add_argument(
        "--save-kg",
        action="store_true",
        help="Save extracted entities and triples to the Neo4j KG",
    )
    parser.add_argument(
        "--kg-stats",
        action="store_true",
        help="Print current KG node and edge counts, then exit",
    )
    return parser.parse_args()


def _interactive_mode() -> None:
    """REPL loop for manual sentence-by-sentence testing."""
    print("=" * 60)
    print("  Sinhala Historical KG — Interactive Pipeline")
    print("  Module 2 | 214161L | University of Moratuwa")
    print("  Type 'exit' or press Ctrl+C to quit.")
    print("=" * 60)

    while True:
        try:
            sentence = input("\nසිංහල වාක්‍යය ඇතුළු කරන්න: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if sentence.lower() in ("exit", "quit", "q"):
            print("Exiting.")
            break
        if not sentence:
            continue

        result = run_pipeline(sentence, verbose=True)

        print("\n── Extracted Triples ──────────────────────────────────────")
        if result.triples:
            for t in result.triples:
                period_info = f"  (කාලය: {t['period']})" if t.get("period") else ""
                print(f"  ▶  {t['subject']}  →[{t['relation']}]→  {t['object']}{period_info}")
        else:
            print("  (valid triples නොමැත)")


def main() -> None:
    args = _parse_args()

    # Mode 0: just print KG stats and exit
    if args.kg_stats:
        from kg_store import get_kg_stats
        stats = get_kg_stats()
        if "error" in stats:
            print(f"[KG] {stats['error']}")
        else:
            print("\n── KG Node counts ──────────────────────────────────")
            for label, count in stats.get("nodes", {}).items():
                print(f"  {label:<16} {count}")
            print("\n── KG Edge counts ──────────────────────────────────")
            for rel, count in stats.get("edges", {}).items():
                print(f"  {rel:<20} {count}")
        return

    # Mode 1: process single sentence
    if args.sentence:
        result = run_pipeline(args.sentence, verbose=args.verbose)
        output = [result.to_dict()]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if args.save_kg:
            from kg_store import save_pipeline_result
            counts = save_pipeline_result(result.sentence, result.ner_tags, result.triples)
            print(f"\n[KG] Saved: {counts['nodes_processed']} node(s), {counts['edges_created']} edge(s)")
        if args.output:
            args.output.write_text(
                json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"\nSaved to {args.output}")
        return

    # Mode 2: process file
    if args.file:
        if not args.file.exists():
            print(f"[ERROR] File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        sentences = [
            line.strip()
            for line in args.file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        print(f"Loaded {len(sentences)} sentences from {args.file}")
        results  = run_pipeline_batch(sentences, verbose=args.verbose)
        triples  = collect_triples(results)
        all_data = [r.to_dict() for r in results]

        print(f"\nTotal valid triples extracted: {len(triples)}")
        print(json.dumps(all_data, ensure_ascii=False, indent=2))

        if args.save_kg:
            from kg_store import save_pipeline_result
            total_nodes = total_edges = 0
            for r in results:
                counts = save_pipeline_result(r.sentence, r.ner_tags, r.triples)
                total_nodes += counts["nodes_processed"]
                total_edges += counts["edges_created"]
            print(f"\n[KG] Saved: {total_nodes} node(s), {total_edges} edge(s) across {len(results)} sentence(s)")

        if args.output:
            args.output.write_text(
                json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"\nSaved to {args.output}")
        return

    # Mode 3: interactive REPL
    _interactive_mode()


if __name__ == "__main__":
    main()
