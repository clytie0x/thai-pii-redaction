"""Wire the corpus through the product's real detect_all() and score it."""

from __future__ import annotations

from dataclasses import replace

from amphrang._core_config import sdk_core_config

from .corpus import build_corpus
from .gold import GOLD_VERSION, load_gold
from .scorer import score


class BenchmarkIntegrityError(RuntimeError):
    """Raised when a benchmark run cannot support a complete score."""

    def __init__(self, diagnostics: dict[str, int]):
        super().__init__("benchmark integrity failure: one or more NER chunks were skipped")
        self.diagnostics = diagnostics


def predict_samples(
    samples,
    engine: str = "crf",
    *,
    diagnostics=None,
) -> list[list[tuple[int, int, str]]]:
    """Run detect_all over samples under the requested NER engine.

    One immutable SDK profile governs the run. The explicit benchmark engine
    overrides only the engine name; environment and canonical caches stay intact.
    """
    from pii_redactor.detectors.aggregate import detect_all

    env_by_engine = {
        "crf": "thainer",
        "wangchanberta": "wangchanberta",
        "union": "union",
        "finetuned": "finetuned",
    }
    if engine not in env_by_engine:
        raise ValueError(f"unknown engine {engine!r}; supported: {sorted(env_by_engine)}")
    config = replace(sdk_core_config(), engine=env_by_engine[engine])
    return [
        [
            (e.span[0], e.span[1], e.data_type)
            for e in detect_all(s.text, ner_diagnostics=diagnostics, config=config)
        ]
        for s in samples
    ]


def run_benchmark(
    engine: str = "crf", seed: int = 42, size: int = 200, source: str = "synthetic"
) -> dict:
    from pii_redactor.detectors.tb_detector import NERChunkDiagnostics

    samples = load_gold() if source == "gold" else build_corpus(seed=seed, size=size)
    diagnostics = NERChunkDiagnostics()
    predictions = predict_samples(samples, engine, diagnostics=diagnostics)
    chunk_report = diagnostics.as_dict()
    if diagnostics.skipped:
        raise BenchmarkIntegrityError(chunk_report)

    report = score(samples, predictions)
    report["engine"] = engine
    report["seed"] = seed
    report["size"] = size
    report["source"] = source
    report["gold_version"] = GOLD_VERSION if source == "gold" else None
    report["ner_chunks"] = chunk_report
    report["integrity"] = {"ok": True, "reason": None}
    return report


def render_table(report: dict) -> str:
    lines = [
        f"engine={report['engine']} source={report.get('source', 'synthetic')} "
        f"seed={report['seed']} size={report['size']}",
        f"{'type':<16}{'n':>5}{'recall':>9}{'prec':>9}{'f2':>9}",
    ]
    for t in sorted(report["by_type"]):
        c = report["by_type"][t]
        n = report["corpus"]["by_type"].get(t, 0)
        lines.append(f"{t:<16}{n:>5}{c['recall']:>9.3f}{c['precision']:>9.3f}{c['f2']:>9.3f}")
    o = report["overall"]
    ci = report.get("confidence_intervals", {}).get("overall_f2")
    lines.append(
        f"{'OVERALL':<16}{report['corpus']['entities']:>5}"
        f"{o['recall']:>9.3f}{o['precision']:>9.3f}{o['f2']:>9.3f}"
    )
    if ci:
        lines.append(
            f"overall_f2_ci{int(ci['confidence'] * 100)}={ci['lower']:.3f}-{ci['upper']:.3f}"
        )
    shared = report.get("shared_11", {}).get("overall")
    if shared:
        lines.append(
            f"shared_11 R={shared['recall']:.3f} P={shared['precision']:.3f} "
            f"F2={shared['f2']:.3f} "
            f"excluded={report['shared_11']['excluded_predictions']}"
        )
    lines.append(f"coverage_recall={o['coverage_recall']:.3f} exact_recall={o['exact_recall']:.3f}")
    chunks = report.get("ner_chunks")
    if chunks:
        lines.append(
            f"ner_chunks attempted={chunks['attempted']} "
            f"succeeded={chunks['succeeded']} skipped={chunks['skipped']}"
        )
    for sl in sorted(report["by_slice"]):
        s = report["by_slice"][sl]
        if s.get("gold_entities") == 0:
            lines.append(
                f"slice {sl:<10} no gold entities: false_positives={s['false_positives']} "
                f"clean_docs={s['clean_docs']}/{s['documents']} "
                f"({s['clean_doc_rate']:.3f})"
            )
        else:
            lines.append(
                f"slice {sl:<10} recall={s['recall']:.3f} coverage={s['coverage_recall']:.3f}"
            )
    return "\n".join(lines)


def run_strategy_comparison(source: str = "synthetic", seed: int = 42, size: int = 200) -> dict:
    """Score four NER strategies (crf, wcb, union, route) on one corpus.

    Runs each engine once with the same SDK profile, composes union/route per
    sample, and scores all four with the shared scorer.
    """
    from pii_redactor.detectors.aggregate import detect_all

    from .strategies import route_entities, union_entities

    samples = load_gold() if source == "gold" else build_corpus(seed=seed, size=size)
    profile = sdk_core_config()

    def _run(engine_env: str):
        from pii_redactor.detectors.tb_detector import NERChunkDiagnostics

        config = replace(profile, engine=engine_env)
        diagnostics = NERChunkDiagnostics()
        entities = [detect_all(s.text, ner_diagnostics=diagnostics, config=config) for s in samples]
        if diagnostics.skipped:
            raise BenchmarkIntegrityError(diagnostics.as_dict())
        return entities, diagnostics.as_dict()

    crf_ents, crf_chunks = _run("thainer")
    wcb_ents, wcb_chunks = _run("wangchanberta")

    combined_chunks = {
        key: crf_chunks[key] + wcb_chunks[key] for key in ("attempted", "succeeded", "skipped")
    }

    strat_ents = {
        "crf": crf_ents,
        "wcb": wcb_ents,
        "union": [union_entities(c, w) for c, w in zip(crf_ents, wcb_ents)],
        "route": [route_entities(c, w) for c, w in zip(crf_ents, wcb_ents)],
    }

    reports: dict[str, dict] = {}
    for name, ents_list in strat_ents.items():
        preds = [[(e.span[0], e.span[1], e.data_type) for e in ents] for ents in ents_list]
        rep = score(samples, preds)
        rep["strategy"] = name
        rep["source"] = source
        rep["seed"] = seed
        rep["size"] = size
        rep["gold_version"] = GOLD_VERSION if source == "gold" else None
        rep["ner_chunks"] = (
            crf_chunks if name == "crf" else wcb_chunks if name == "wcb" else combined_chunks
        )
        rep["integrity"] = {"ok": True, "reason": None}
        reports[name] = rep
    return reports


def render_strategy_table(reports: dict) -> str:
    order = ["crf", "wcb", "union", "route"]
    base = reports[order[0]]
    types = sorted(base["by_type"])
    lines = [
        f"strategy comparison source={base.get('source', 'synthetic')} "
        f"seed={base['seed']} size={base['size']}  (values = recall)",
        f"{'type':<16}" + "".join(f"{s + '_R':>10}" for s in order),
    ]
    for t in types:
        row = f"{t:<16}"
        for s in order:
            c = reports[s]["by_type"].get(t)
            row += f"{c['recall']:>10.3f}" if c else f"{'-':>10}"
        lines.append(row)
    lines.append(
        f"{'OVERALL_R':<16}" + "".join(f"{reports[s]['overall']['recall']:>10.3f}" for s in order)
    )
    lines.append(
        f"{'OVERALL_P':<16}"
        + "".join(f"{reports[s]['overall']['precision']:>10.3f}" for s in order)
    )
    lines.append(
        f"{'coverage':<16}"
        + "".join(f"{reports[s]['overall']['coverage_recall']:>10.3f}" for s in order)
    )
    return "\n".join(lines)
