"""Human annotation check for the YRSS evaluation v2: sampling and agreement."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from benchmark.yrss_v2 import agreement
from benchmark.yrss_v2.corpus import Corpus, Document, Span, Template, render

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fixture_corpus(families: int = 40, negatives: int = 10, variants: int = 4) -> Corpus:
    documents = []
    for index in range(families):
        negative = index < negatives
        text = (
            "ใบแจ้งยอด {{amount}} ครบกำหนด {{date}}"
            if negative
            else "ผู้ติดต่อ {{name}} โทร {{phone}} อีเมล {{email}}"
        )
        template = Template(f"fx-{index:03d}", "letter", negative, text)
        documents += [render(template, variant, seed=7) for variant in range(variants)]
    return Corpus("yrss-eval-v2", "test", 7, "0" * 64, tuple(documents))


def _doc(doc_id: str, text: str, *spans: tuple[int, int, str]) -> Document:
    return Document(doc_id, doc_id, "letter", text, tuple(Span(*span) for span in spans))


def _corpus(*documents: Document) -> Corpus:
    return Corpus("yrss-eval-v2", "test", 7, "0" * 64, tuple(documents))


def _rows(*rows: tuple[str, str, str]) -> list[agreement.Row]:
    return [agreement.Row(number + 2, *row) for number, row in enumerate(rows)]


def _score(corpus: Corpus, rows: list[agreement.Row]) -> dict:
    return agreement.score(corpus, [doc.doc_id for doc in corpus.documents], rows)


def _perfect_rows(corpus: Corpus) -> list[agreement.Row]:
    rows = []
    for doc in corpus.documents:
        for span in doc.spans:
            rows.append((doc.doc_id, span.entity_type, doc.text[span.start : span.end]))
        if not doc.spans:
            rows.append((doc.doc_id, "NONE", ""))
    return _rows(*rows)


# --- kappa ---------------------------------------------------------------


def test_kappa_matches_a_hand_computed_case():
    # Gold A A O O, annotator A O O O: observed 3/4, chance 1/2*1/4 + 1/2*3/4 = 1/2.
    pairs = Counter({("A", "A"): 1, ("A", "O"): 1, ("O", "O"): 2})
    assert agreement.cohen_kappa(pairs) == pytest.approx(0.5)


def test_kappa_edge_cases():
    assert agreement.cohen_kappa(Counter()) is None
    assert agreement.cohen_kappa(Counter({("O", "O"): 5})) == 1.0
    assert agreement.cohen_kappa(Counter({("A", "O"): 2, ("O", "A"): 2})) == pytest.approx(-1.0)


def test_report_kappa_uses_characters_and_skips_whitespace_in_second_figure():
    # 4 characters: gold labels "ab", annotator labels "a" only.
    report = _score(_corpus(_doc("d-v0", "ab c", (0, 2, "NAME"))), _rows(("d-v0", "NAME", "a")))
    assert report["kappa"]["characters"]["n"] == 4
    assert report["kappa"]["characters"]["value"] == pytest.approx(0.5)
    assert report["kappa"]["non_whitespace_characters"]["n"] == 3
    # Observed 2/3, chance 2/3*1/3 + 1/3*2/3 = 4/9.
    assert report["kappa"]["non_whitespace_characters"]["value"] == pytest.approx(0.4)


def test_perfect_annotation_scores_one():
    corpus = _fixture_corpus(families=8, negatives=2, variants=1)
    report = _score(corpus, _perfect_rows(corpus))
    assert report["kappa"]["characters"]["value"] == 1.0
    assert report["kappa"]["characters"]["ci95"] == [1.0, 1.0]
    assert report["kappa"]["non_whitespace_characters"]["value"] == 1.0
    agreed = report["span_agreement"]
    assert agreed["gold_exact"] == agreed["annotator_exact"] == 1.0
    assert agreed["gold_overlap_same_type"] == agreed["annotator_overlap_same_type"] == 1.0
    assert agreed["gold_spans"] == agreed["annotator_spans"] == 18
    assert report["disagreements"] == []
    assert report["rows"]["issues"] == []
    assert report["complete"] is True


def test_bootstrap_interval_is_seeded_and_brackets_the_estimate():
    corpus = _fixture_corpus(families=12, negatives=2, variants=1)
    rows = [row for row in _perfect_rows(corpus) if row.entity_type != "EMAIL" or row.number % 3]
    first = _score(corpus, rows)
    second = _score(corpus, rows)
    low, high = first["kappa"]["characters"]["ci95"]
    assert first == second
    assert low <= first["kappa"]["characters"]["value"] <= high
    assert low < 1.0
    assert first["bootstrap"] == {"resamples": 1000, "seed": 0, "unit": "document"}


# --- span agreement and disagreement kinds --------------------------------


def test_disagreement_kinds_are_told_apart():
    text = "AAAA BBBB CCCC DDDD EEEE"
    corpus = _corpus(
        _doc("exact-v0", text, (0, 4, "NAME")),
        _doc("boundary-v0", text, (0, 4, "NAME")),
        _doc("type-v0", text, (0, 4, "NAME")),
        _doc("missing-v0", text, (0, 4, "NAME")),
        _doc("extra-v0", text, (0, 4, "NAME")),
    )
    report = _score(
        corpus,
        _rows(
            ("exact-v0", "NAME", "AAAA"),
            ("boundary-v0", "NAME", "AAAA BB"),
            ("type-v0", "ADDRESS", "AAAA"),
            ("missing-v0", "NONE", ""),
            ("extra-v0", "NAME", "AAAA"),
            ("extra-v0", "PHONE", "DDDD"),
        ),
    )
    kinds = {row["doc_id"]: row["kinds"] for row in report["disagreements"]}
    assert kinds == {
        "boundary-v0": {"boundary": 1},
        "type-v0": {"type": 1},
        "missing-v0": {"missing": 1},
        "extra-v0": {"extra": 1},
    }
    agreed = report["span_agreement"]
    assert agreed["gold_spans"] == 5
    assert agreed["annotator_spans"] == 5
    assert agreed["gold_exact"] == pytest.approx(2 / 5)
    assert agreed["gold_overlap_same_type"] == pytest.approx(3 / 5)
    assert agreed["annotator_exact"] == pytest.approx(2 / 5)
    assert agreed["annotator_overlap_same_type"] == pytest.approx(3 / 5)
    assert report["confusion"] == {
        "NAME": {"ADDRESS": 1, "NAME": 3, "O": 1},
        "O": {"PHONE": 1},
    }


def test_wrong_type_with_wrong_boundary_counts_as_both():
    report = _score(
        _corpus(_doc("d-v0", "AAAA BBBB", (0, 4, "NAME"))), _rows(("d-v0", "ADDRESS", "AAAA BB"))
    )
    assert report["disagreements"] == [{"doc_id": "d-v0", "kinds": {"boundary": 1, "type": 1}}]


def test_one_gold_span_split_in_two_is_a_boundary_disagreement():
    report = _score(
        _corpus(_doc("d-v0", "AAAA BBBB", (0, 9, "ADDRESS"))),
        _rows(("d-v0", "ADDRESS", "AAAA"), ("d-v0", "ADDRESS", "BBBB")),
    )
    assert report["disagreements"] == [{"doc_id": "d-v0", "kinds": {"boundary": 2}}]
    assert report["span_agreement"]["annotator_overlap_same_type"] == 1.0


# --- resolving rows to offsets ---------------------------------------------


def test_repeated_strings_resolve_in_reading_order():
    doc = _doc("d-v0", "KIM met KIM and KIM", (0, 3, "NAME"), (8, 11, "NAME"), (16, 19, "NAME"))
    spans, issues = agreement.resolve_rows(doc, _rows(*[("d-v0", "NAME", "KIM")] * 3))
    assert [(span.start, span.end) for span in spans] == [(0, 3), (8, 11), (16, 19)]
    assert issues == []


def test_out_of_order_row_falls_back_to_first_free_occurrence():
    doc = _doc("d-v0", "AAA BBB AAA")
    rows = _rows(("d-v0", "NAME", "BBB"), ("d-v0", "NAME", "AAA"), ("d-v0", "NAME", "AAA"))
    spans, issues = agreement.resolve_rows(doc, rows)
    # The first AAA row takes the copy after BBB; the second goes back to the free one.
    assert [(span.start, span.end) for span in spans] == [(0, 3), (4, 7), (8, 11)]
    assert issues == []


def test_resolved_spans_never_overlap():
    doc = _doc("d-v0", "ABAB")
    rows = _rows(("d-v0", "NAME", "ABAB"), ("d-v0", "NAME", "AB"))
    spans, issues = agreement.resolve_rows(doc, rows)
    assert [(span.start, span.end) for span in spans] == [(0, 4)]
    assert issues == [{"row": 3, "kind": "not-found", "doc_id": "d-v0"}]


def test_outer_space_in_a_copied_string_is_ignored():
    doc = _doc("d-v0", "call KIM now", (5, 8, "NAME"))
    spans, issues = agreement.resolve_rows(doc, _rows(("d-v0", " name ", "  KIM ")))
    assert spans == [Span(5, 8, "NAME")]
    assert issues == []


def test_none_row_means_no_personal_data():
    corpus = _corpus(_doc("neg-v0", "nothing here"), _doc("pos-v0", "KIM", (0, 3, "NAME")))
    report = _score(corpus, _rows(("neg-v0", "none", ""), ("pos-v0", "NAME", "KIM")))
    assert report["disagreements"] == []
    assert report["documents"] == {"sampled": 2, "negative_gold": 1, "unanswered": []}
    assert report["complete"] is True


def test_none_row_next_to_mentions_is_flagged_and_mentions_kept():
    corpus = _corpus(_doc("d-v0", "KIM", (0, 3, "NAME")))
    report = _score(corpus, _rows(("d-v0", "NONE", ""), ("d-v0", "NAME", "KIM")))
    assert report["rows"]["issues"] == [{"row": 2, "kind": "none-with-mentions", "doc_id": "d-v0"}]
    assert report["span_agreement"]["gold_exact"] == 1.0


def test_unfound_and_bad_rows_are_counted_not_echoed():
    secret = "ZZZ-SECRET-STRING"
    corpus = _corpus(_doc("d-v0", "call KIM now", (5, 8, "NAME")), _doc("e-v0", "plain"))
    report = _score(
        corpus,
        _rows(
            ("d-v0", "NAME", "KIM"),
            ("d-v0", "PHONE", secret),
            ("d-v0", secret, "KIM"),
            (secret, "NAME", "KIM"),
            ("d-v0", "NAME", ""),
        ),
    )
    assert report["rows"]["total"] == 5
    assert report["rows"]["not_found"] == 1
    assert report["rows"]["issues"] == [
        {"row": 3, "kind": "not-found", "doc_id": "d-v0"},
        {"row": 4, "kind": "unknown-type", "doc_id": "d-v0"},
        {"row": 5, "kind": "unknown-doc"},
        {"row": 6, "kind": "empty-text", "doc_id": "d-v0"},
    ]
    assert report["documents"]["unanswered"] == ["e-v0"]
    assert report["complete"] is False
    assert secret not in json.dumps(report, ensure_ascii=False)


def test_report_contains_no_text_or_values():
    corpus = _fixture_corpus(families=6, negatives=1, variants=1)
    rows = [row for row in _perfect_rows(corpus) if row.entity_type != "PHONE"]
    dumped = json.dumps(_score(corpus, rows), ensure_ascii=False)
    for doc in corpus.documents:
        assert doc.text not in dumped
        for span in doc.spans:
            assert doc.text[span.start : span.end] not in dumped
    assert "ผู้ติดต่อ" not in dumped


# --- export ----------------------------------------------------------------


def test_sample_is_deterministic_and_changes_with_the_seed():
    corpus = _fixture_corpus()
    first = [doc.doc_id for doc in agreement.sample_documents(corpus, seed=3)]
    assert first == [doc.doc_id for doc in agreement.sample_documents(corpus, seed=3)]
    assert first != [doc.doc_id for doc in agreement.sample_documents(corpus, seed=4)]


def test_sample_takes_one_variant_per_family_and_about_ten_percent():
    corpus = _fixture_corpus()
    sample = agreement.sample_documents(corpus, seed=3)
    assert len(sample) == 16
    assert len({doc.family for doc in sample}) == len(sample)
    assert len({doc.doc_id.rsplit("-v", 1)[1] for doc in sample}) > 1


def test_sample_keeps_the_negative_share():
    for seed in range(5):
        for negatives in (0, 3, 10, 17):
            corpus = _fixture_corpus(negatives=negatives)
            sample = agreement.sample_documents(corpus, seed=seed)
            share = sum(1 for doc in sample if not doc.spans) / len(sample)
            assert abs(share - negatives / 40) <= 0.05


def test_export_writes_a_packet_without_gold(tmp_path):
    corpus = _fixture_corpus()
    out = tmp_path / "packet"
    manifest = agreement.export_packet(corpus, out, seed=3)
    again = agreement.export_packet(corpus, tmp_path / "again", seed=3)
    assert manifest == again

    lines = (out / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    packet = [json.loads(line) for line in lines]
    assert all(set(row) == {"doc_id", "text"} for row in packet)
    assert [row["doc_id"] for row in packet] == manifest["doc_ids"]
    by_id = {doc.doc_id: doc for doc in corpus.documents}
    assert all(by_id[row["doc_id"]].text == row["text"] for row in packet)

    with (out / "answers.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert list(csv.reader(handle)) == [["doc_id", "type", "text"]]

    stored = (out / "manifest.json").read_text(encoding="utf-8")
    assert json.loads(stored) == manifest
    assert manifest["sample_seed"] == 3
    assert manifest["plaintext_sha256"] == agreement.plaintext_sha256(corpus)
    assert manifest["documents_sampled"] == 16
    for doc in corpus.documents:
        assert doc.text not in stored
        for span in doc.spans:
            assert doc.text[span.start : span.end] not in stored
    for name in ("documents.jsonl", "answers.csv", "manifest.json"):
        body = (out / name).read_text(encoding="utf-8")
        assert "spans" not in body and "genre" not in body and "family" not in body
    assert sorted(path.name for path in out.iterdir()) == [
        "answers.csv",
        "documents.jsonl",
        "manifest.json",
    ]


def test_export_refuses_the_repository(tmp_path):
    corpus = _fixture_corpus()
    inside = REPO_ROOT / "benchmark" / "data" / "never-written-human-check"
    with pytest.raises(agreement.AgreementError, match="inside-repository"):
        agreement.export_packet(corpus, inside, seed=3)
    assert not inside.exists()

    # Any git work tree counts, not only this one.
    (tmp_path / ".git").mkdir()
    with pytest.raises(agreement.AgreementError, match="inside-repository"):
        agreement.export_packet(corpus, tmp_path / "sub" / "packet", seed=3)
    agreement.export_packet(corpus, tmp_path / "sub" / "packet", seed=3, allow_in_repo=True)
    assert (tmp_path / "sub" / "packet" / "documents.jsonl").exists()


# --- command line ------------------------------------------------------------


def test_cli_export_then_score_round_trip(tmp_path, monkeypatch, capsys):
    corpus = _fixture_corpus()
    monkeypatch.setattr(agreement, "build_corpus", lambda split: corpus)
    out = tmp_path / "packet"
    assert agreement.main(["export", "--out", str(out), "--seed", "3"]) == 0
    capsys.readouterr()

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    by_id = {doc.doc_id: doc for doc in corpus.documents}
    with (out / "answers.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for doc_id in manifest["doc_ids"]:
            doc = by_id[doc_id]
            for span in doc.spans:
                writer.writerow([doc_id, span.entity_type, doc.text[span.start : span.end]])
            if not doc.spans:
                writer.writerow([doc_id, "NONE", ""])

    report_path = tmp_path / "report.json"
    code = agreement.main(
        [
            "score",
            "--manifest",
            str(out / "manifest.json"),
            "--answers",
            str(out / "answers.csv"),
            "--report",
            str(report_path),
        ]
    )
    assert code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report == json.loads(capsys.readouterr().out)
    assert report["kappa"]["characters"]["value"] == 1.0
    assert report["span_agreement"]["gold_exact"] == 1.0
    assert report["sample_seed"] == 3
    assert report["documents"]["sampled"] == 16


def test_cli_export_refuses_the_repository(monkeypatch, capsys):
    monkeypatch.setattr(agreement, "build_corpus", lambda split: _fixture_corpus())
    inside = REPO_ROOT / "never-written-human-check"
    assert agreement.main(["export", "--out", str(inside)]) == 2
    assert "inside-repository" in capsys.readouterr().err
    assert not inside.exists()


def test_cli_score_rejects_a_changed_corpus_or_bad_header(tmp_path, monkeypatch, capsys):
    corpus = _fixture_corpus()
    monkeypatch.setattr(agreement, "build_corpus", lambda split: corpus)
    out = tmp_path / "packet"
    agreement.export_packet(corpus, out, seed=3)
    args = [
        "score",
        "--manifest",
        str(out / "manifest.json"),
        "--answers",
        str(out / "answers.csv"),
    ]

    (out / "answers.csv").write_text("document,label\n", encoding="utf-8")
    assert agreement.main(args) == 2
    assert "bad-answer-header" in capsys.readouterr().err

    agreement.export_packet(corpus, out, seed=3)
    monkeypatch.setattr(agreement, "build_corpus", lambda split: _fixture_corpus(negatives=9))
    assert agreement.main(args) == 2
    assert "corpus-hash-mismatch" in capsys.readouterr().err


def test_cli_reports_a_missing_input_file_without_a_traceback(tmp_path, capsys):
    args = ["score", "--manifest", str(tmp_path / "none.json"), "--answers", str(tmp_path / "a")]
    assert agreement.main(args) == 2
    assert capsys.readouterr().err.strip() == "input-file-not-found"
