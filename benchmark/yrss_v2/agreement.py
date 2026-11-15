"""Human annotation check for the YRSS evaluation v2.

``export`` draws a seeded sample of the corpus and writes a labeling packet
for a person who did not write the documents. ``score`` compares the filled
answer sheet with the constructed gold labels.

Agreement is Cohen's kappa over character labels (eleven types plus ``O``).
The protocol says "token labels"; the character is the token here because
Thai has no spaces between words, so any word tokenizer would add its own
errors to the figure. Kappa over non-whitespace characters is reported too.

The packet holds document text, so it is written outside the repository by
default. The manifest and the report hold ids, counts and hashes only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .corpus import SEEDS, Corpus, Document, Span, build_corpus, canonical_bytes
from .types import SCHEME_TYPES

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = "docs/decisions/2026-11-13-yrss-eval-v2.md"
SAMPLE_SEED = 20261113
SAMPLE_FRACTION = 0.10
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 0
OUTSIDE = "O"
NONE_TYPE = "NONE"
ANSWER_COLUMNS = ("doc_id", "type", "text")
DOCUMENTS_FILE = "documents.jsonl"
ANSWERS_FILE = "answers.csv"
MANIFEST_FILE = "manifest.json"


class AgreementError(Exception):
    """A short error code. It never carries document text."""


@dataclass(frozen=True)
class Row:
    """One answer row. ``number`` is the row a spreadsheet shows (header is 1)."""

    number: int
    doc_id: str
    entity_type: str
    text: str


def plaintext_sha256(corpus: Corpus) -> str:
    return hashlib.sha256(canonical_bytes(corpus)).hexdigest()


# --- export ----------------------------------------------------------------


def _half_up(value: float) -> int:
    return int(value + 0.5)


def sample_documents(
    corpus: Corpus, *, seed: int, fraction: float = SAMPLE_FRACTION
) -> list[Document]:
    """Pick whole families, one variant each, until about ``fraction`` of documents.

    Variants of one family share their fixed text, so two of them would not
    be two independent checks. Negative families are drawn on their own so
    the sample keeps the corpus share of documents without personal data.
    """
    families: dict[str, list[Document]] = {}
    for doc in corpus.documents:
        families.setdefault(doc.family, []).append(doc)
    negative = sorted(name for name, docs in families.items() if not any(d.spans for d in docs))
    positive = sorted(name for name in families if name not in set(negative))
    total = len(corpus.documents)
    if not total:
        raise AgreementError("empty-corpus")
    target = min(max(1, _half_up(fraction * total)), len(families))
    negative_share = sum(1 for doc in corpus.documents if not doc.spans) / total
    take_negative = min(_half_up(target * negative_share), len(negative))
    take_positive = min(target - take_negative, len(positive))

    rng = random.Random(seed)
    chosen = rng.sample(negative, take_negative) + rng.sample(positive, take_positive)
    sample = [rng.choice(families[name]) for name in chosen]
    # Mix the order so the position in the packet says nothing about the label.
    rng.shuffle(sample)
    return sample


def inside_work_tree(path: Path) -> bool:
    """True when ``path`` is in this repository or in any git work tree."""
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        return True
    return any((parent / ".git").exists() for parent in (resolved, *resolved.parents))


def export_packet(
    corpus: Corpus,
    out_dir: Path,
    *,
    seed: int = SAMPLE_SEED,
    fraction: float = SAMPLE_FRACTION,
    allow_in_repo: bool = False,
) -> dict:
    """Write the documents, an empty answer sheet and a manifest. Return the manifest."""
    if not allow_in_repo and inside_work_tree(out_dir):
        raise AgreementError("inside-repository")
    sample = sample_documents(corpus, seed=seed, fraction=fraction)
    manifest = {
        "doc_ids": [doc.doc_id for doc in sample],
        "documents_in_corpus": len(corpus.documents),
        "documents_sampled": len(sample),
        "negative_documents_in_corpus": sum(1 for doc in corpus.documents if not doc.spans),
        "negative_documents_sampled": sum(1 for doc in sample if not doc.spans),
        "plaintext_sha256": plaintext_sha256(corpus),
        "protocol": PROTOCOL,
        "sample_fraction": fraction,
        "sample_seed": seed,
        "split": corpus.split,
        "version": corpus.version,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"doc_id": doc.doc_id, "text": doc.text}, ensure_ascii=False) for doc in sample
    ]
    (out_dir / DOCUMENTS_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The byte-order mark makes spreadsheet programs read Thai text as UTF-8.
    with (out_dir / ANSWERS_FILE).open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerow(ANSWER_COLUMNS)
    (out_dir / MANIFEST_FILE).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


# --- reading and resolving answers -------------------------------------------


def read_answers(path: Path) -> list[Row]:
    """Read the filled answer sheet. Blank lines keep their row number."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        table = list(csv.reader(handle))
    header = [cell.strip().lower() for cell in table[0]] if table else []
    if any(column not in header for column in ANSWER_COLUMNS):
        raise AgreementError("bad-answer-header")
    index = {column: header.index(column) for column in ANSWER_COLUMNS}
    rows = []
    for number, cells in enumerate(table[1:], start=2):
        picked = [
            cells[index[column]] if index[column] < len(cells) else "" for column in ANSWER_COLUMNS
        ]
        if any(cell.strip() for cell in picked):
            rows.append(Row(number, *picked))
    return rows


def _issue(row: Row, kind: str, doc_id: str | None = None) -> dict:
    issue = {"row": row.number, "kind": kind}
    if doc_id is not None:
        issue["doc_id"] = doc_id
    return issue


def _find_free(text: str, needle: str, start: int, taken: list[Span]) -> int:
    """First place at or after ``start`` where ``needle`` fits without overlap."""
    position = text.find(needle, start)
    while position != -1:
        end = position + len(needle)
        if all(end <= span.start or position >= span.end for span in taken):
            return position
        position = text.find(needle, position + 1)
    return -1


def resolve_rows(doc: Document, rows: list[Row]) -> tuple[list[Span], list[dict]]:
    """Turn the rows of one document into spans.

    Each row takes the next exact copy of its string after the row before it,
    so a string that appears three times needs three rows. A row written out
    of reading order falls back to the first copy that is still free. Issues
    name the row and the document, never the string.
    """
    spans: list[Span] = []
    issues: list[dict] = []
    none_rows: list[Row] = []
    cursor = 0
    for row in rows:
        entity_type = row.entity_type.strip().upper()
        needle = row.text.strip()
        if entity_type == NONE_TYPE:
            none_rows.append(row)
        elif entity_type not in SCHEME_TYPES:
            issues.append(_issue(row, "unknown-type", doc.doc_id))
        elif not needle:
            issues.append(_issue(row, "empty-text", doc.doc_id))
        else:
            position = _find_free(doc.text, needle, cursor, spans)
            if position == -1:
                position = _find_free(doc.text, needle, 0, spans)
            if position == -1:
                issues.append(_issue(row, "not-found", doc.doc_id))
                continue
            spans.append(Span(position, position + len(needle), entity_type))
            cursor = position + len(needle)
    if spans:
        issues += [_issue(row, "none-with-mentions", doc.doc_id) for row in none_rows]
    return sorted(spans, key=lambda span: span.start), sorted(issues, key=lambda i: i["row"])


# --- agreement ---------------------------------------------------------------


def cohen_kappa(pairs: Counter) -> float | None:
    """Cohen's kappa from counts of (first label, second label) pairs.

    None when there is nothing to compare. 1.0 when both raters used a single
    label everywhere, where the usual formula would divide by zero.
    """
    total = sum(pairs.values())
    if not total:
        return None
    first: Counter = Counter()
    second: Counter = Counter()
    for (left, right), count in pairs.items():
        first[left] += count
        second[right] += count
    observed = sum(count for (left, right), count in pairs.items() if left == right) / total
    expected = sum(first[label] * second[label] for label in first) / (total * total)
    if expected >= 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def _labels(length: int, spans: list[Span] | tuple[Span, ...]) -> list[str]:
    labels = [OUTSIDE] * length
    for span in spans:
        labels[span.start : span.end] = [span.entity_type] * (span.end - span.start)
    return labels


def _char_pairs(doc: Document, annotated: list[Span]) -> tuple[Counter, Counter]:
    """Label pairs for every character, and for non-whitespace characters only."""
    everything: Counter = Counter()
    solid: Counter = Counter()
    gold = _labels(len(doc.text), doc.spans)
    mine = _labels(len(doc.text), annotated)
    for char, pair in zip(doc.text, zip(gold, mine, strict=True), strict=True):
        everything[pair] += 1
        if not char.isspace():
            solid[pair] += 1
    return everything, solid


def _overlap(left: Span, right: Span) -> int:
    return min(left.end, right.end) - max(left.start, right.start)


def _best(span: Span, others: list[Span] | tuple[Span, ...]) -> int | None:
    """Index of the span that shares the most characters, or None."""
    best, best_size = None, 0
    for index, other in enumerate(others):
        size = _overlap(span, other)
        if size > best_size:
            best, best_size = index, size
    return best


def _compare_spans(gold: tuple[Span, ...], annotated: list[Span]) -> tuple[Counter, Counter]:
    """Disagreement kinds and (gold type, annotator type) counts for one document."""
    kinds: Counter = Counter()
    confusion: Counter = Counter()
    used: set[int] = set()
    for span in gold:
        index = _best(span, annotated)
        if index is None:
            kinds["missing"] += 1
            confusion[(span.entity_type, OUTSIDE)] += 1
            continue
        used.add(index)
        other = annotated[index]
        confusion[(span.entity_type, other.entity_type)] += 1
        if (other.start, other.end) != (span.start, span.end):
            kinds["boundary"] += 1
        if other.entity_type != span.entity_type:
            kinds["type"] += 1
    for index, span in enumerate(annotated):
        if index in used:
            continue
        match = _best(span, gold)
        if match is None:
            kinds["extra"] += 1
            confusion[(OUTSIDE, span.entity_type)] += 1
            continue
        # A second piece of a gold span that another row already matched.
        kinds["boundary"] += 1
        if gold[match].entity_type != span.entity_type:
            kinds["type"] += 1
    return kinds, confusion


def _matched(spans: list[Span] | tuple[Span, ...], others: list[Span] | tuple[Span, ...]):
    """How many of ``spans`` have an identical, or an overlapping same-type, partner."""
    exact = sum(1 for span in spans if span in others)
    overlapping = sum(
        1
        for span in spans
        if any(o.entity_type == span.entity_type and _overlap(span, o) > 0 for o in others)
    )
    return exact, overlapping


def _rate(count: int, total: int) -> float | None:
    return count / total if total else None


def _percentile(ordered: list[float], share: float) -> float:
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def _kappa_block(per_doc: list[Counter], draws: list[list[int]]) -> dict:
    """Point estimate plus a percentile interval from resampled documents."""
    pooled: Counter = Counter()
    for pairs in per_doc:
        pooled.update(pairs)
    samples = []
    for draw in draws:
        resampled: Counter = Counter()
        for index in draw:
            resampled.update(per_doc[index])
        value = cohen_kappa(resampled)
        if value is not None:
            samples.append(value)
    samples.sort()
    interval = [_percentile(samples, 0.025), _percentile(samples, 0.975)] if samples else None
    return {"value": cohen_kappa(pooled), "ci95": interval, "n": sum(pooled.values())}


def score(corpus: Corpus, doc_ids: list[str], rows: list[Row]) -> dict:
    """Compare answer rows with gold for the sampled documents.

    The result holds ids, counts and rates. It never holds document text or
    a copied value. A sampled document with no rows at all is scored as "no
    personal data found" and listed under ``unanswered``.
    """
    by_id = {doc.doc_id: doc for doc in corpus.documents}
    if any(doc_id not in by_id for doc_id in doc_ids) or len(set(doc_ids)) != len(doc_ids):
        raise AgreementError("manifest-doc-ids-do-not-match-corpus")
    sample = [by_id[doc_id] for doc_id in doc_ids]
    if not sample:
        raise AgreementError("empty-sample")

    grouped: dict[str, list[Row]] = {doc_id: [] for doc_id in doc_ids}
    issues: list[dict] = []
    for row in rows:
        doc_id = row.doc_id.strip()
        if doc_id in grouped:
            grouped[doc_id].append(row)
        else:
            # The cell could hold anything, so it is not repeated in the report.
            issues.append(_issue(row, "unknown-doc"))

    all_pairs: list[Counter] = []
    solid_pairs: list[Counter] = []
    confusion: Counter = Counter()
    disagreements: list[dict] = []
    gold_total = annotated_total = 0
    gold_exact = gold_overlap = annotated_exact = annotated_overlap = 0
    for doc in sample:
        annotated, doc_issues = resolve_rows(doc, grouped[doc.doc_id])
        issues += doc_issues
        everything, solid = _char_pairs(doc, annotated)
        all_pairs.append(everything)
        solid_pairs.append(solid)
        kinds, doc_confusion = _compare_spans(doc.spans, annotated)
        confusion.update(doc_confusion)
        if kinds:
            disagreements.append({"doc_id": doc.doc_id, "kinds": dict(sorted(kinds.items()))})
        exact, overlapping = _matched(doc.spans, annotated)
        gold_exact += exact
        gold_overlap += overlapping
        exact, overlapping = _matched(annotated, doc.spans)
        annotated_exact += exact
        annotated_overlap += overlapping
        gold_total += len(doc.spans)
        annotated_total += len(annotated)

    rng = random.Random(BOOTSTRAP_SEED)
    draws = [[rng.randrange(len(sample)) for _ in sample] for _ in range(BOOTSTRAP_RESAMPLES)]
    table: dict[str, dict[str, int]] = {}
    for (gold_type, other_type), count in sorted(confusion.items()):
        table.setdefault(gold_type, {})[other_type] = count
    issues.sort(key=lambda issue: issue["row"])
    unanswered = [doc_id for doc_id in doc_ids if not grouped[doc_id]]
    return {
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "unit": "document"},
        "complete": not issues and not unanswered,
        "confusion": table,
        "disagreements": disagreements,
        "documents": {
            "sampled": len(sample),
            "negative_gold": sum(1 for doc in sample if not doc.spans),
            "unanswered": unanswered,
        },
        "kappa": {
            "characters": _kappa_block(all_pairs, draws),
            "non_whitespace_characters": _kappa_block(solid_pairs, draws),
        },
        "labels": [*SCHEME_TYPES, OUTSIDE],
        "plaintext_sha256": plaintext_sha256(corpus),
        "protocol": PROTOCOL,
        "rows": {
            "total": len(rows),
            "not_found": sum(1 for issue in issues if issue["kind"] == "not-found"),
            "issues": issues,
        },
        "span_agreement": {
            "gold_spans": gold_total,
            "annotator_spans": annotated_total,
            "gold_exact": _rate(gold_exact, gold_total),
            "gold_overlap_same_type": _rate(gold_overlap, gold_total),
            "annotator_exact": _rate(annotated_exact, annotated_total),
            "annotator_overlap_same_type": _rate(annotated_overlap, annotated_total),
        },
        "split": corpus.split,
        "version": corpus.version,
    }


# --- command line ------------------------------------------------------------


def _run_export(args: argparse.Namespace) -> dict:
    corpus = build_corpus(args.split)
    manifest = export_packet(
        corpus,
        Path(args.out),
        seed=args.seed,
        fraction=args.fraction,
        allow_in_repo=args.allow_in_repo,
    )
    # Counts and the folder only. The doc ids stay in the manifest file.
    return {
        "documents_sampled": manifest["documents_sampled"],
        "negative_documents_sampled": manifest["negative_documents_sampled"],
        "out": str(Path(args.out).resolve()),
        "sample_seed": manifest["sample_seed"],
    }


def _run_score(args: argparse.Namespace) -> dict:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    corpus = build_corpus(manifest["split"])
    if plaintext_sha256(corpus) != manifest["plaintext_sha256"]:
        raise AgreementError("corpus-hash-mismatch")
    report = score(corpus, list(manifest["doc_ids"]), read_answers(Path(args.answers)))
    report["sample_seed"] = manifest["sample_seed"]
    report["sample_fraction"] = manifest["sample_fraction"]
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Human annotation check, YRSS evaluation v2.")
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export", help="write a labeling packet for the annotator")
    export.add_argument("--split", choices=sorted(SEEDS), default="test")
    export.add_argument("--seed", type=int, default=SAMPLE_SEED)
    export.add_argument("--fraction", type=float, default=SAMPLE_FRACTION)
    export.add_argument(
        "--out",
        default=str(Path.home() / "yrss-v2-human-check"),
        help="packet folder; must be outside the repository",
    )
    export.add_argument("--allow-in-repo", action="store_true")

    scorer = commands.add_parser("score", help="compare a filled answer sheet with gold")
    scorer.add_argument("--manifest", required=True)
    scorer.add_argument("--answers", required=True)
    scorer.add_argument("--report", help="also write the JSON report to this file")

    args = parser.parse_args(argv)
    try:
        result = _run_export(args) if args.command == "export" else _run_score(args)
    except AgreementError as error:
        print(str(error), file=sys.stderr)
        return 2
    except FileNotFoundError:
        # The split's templates, the manifest or the answer sheet is not there.
        print("input-file-not-found", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
