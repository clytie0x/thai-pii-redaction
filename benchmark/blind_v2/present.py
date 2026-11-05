"""Markdown tables for a blind-v2 JSON report.

The renderer reads scores only. It does not accept document text and it does
not format anything except the fields ``run_benchmark`` stores.
"""

from __future__ import annotations

from .types import REDACTION_TYPES


def _num(value: float) -> str:
    return f"{value:.3f}"


def _signed(value: float) -> str:
    return f"{value:+.3f}"


def _system(report: dict, name: str) -> dict:
    for system in report["systems"]:
        if system["name"] == name and system["status"] == "ok":
            return system
    raise KeyError(name)


def render_split_markdown(report: dict) -> str:
    """One split: summary, per-entity scores, misses, and layer deltas."""
    dataset = report["dataset"]
    lines = [
        (
            f"dataset `{dataset['version']}` seed `{dataset['seed']}` "
            f"documents {dataset['documents']} "
            f"sha256 `{dataset['plaintext_sha256']}` "
            f"official `{str(dataset['official']).lower()}`"
        ),
        "",
        "| System | P | R | F1 | F2 | macro P | macro R | macro F1 | macro F2 | p50 ms | cost USD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for system in report["systems"]:
        if system["status"] != "ok":
            lines.append(f"| {system['name']} | skipped | | | | | | | | | |")
            continue
        micro = system["micro"]
        macro = system["macro"]
        lines.append(
            f"| {system['name']} | {_num(micro['precision'])} | {_num(micro['recall'])} | "
            f"{_num(micro['f1'])} | {_num(micro['f2'])} | {_num(macro['precision'])} | "
            f"{_num(macro['recall'])} | {_num(macro['f1'])} | {_num(macro['f2'])} | "
            f"{system['latency_ms']['p50']:.1f} | {system['cost_usd']:.2f} |"
        )
    lines.extend(
        [
            "",
            "| System | Type | n | P | R | F1 | F2 | fp | fn |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for system in report["systems"]:
        if system["status"] != "ok":
            continue
        for entity_type in REDACTION_TYPES:
            row = system["by_type"][entity_type]
            if row["n"] == 0:
                lines.append(
                    f"| {system['name']} | {entity_type} | 0 | n/a | n/a | n/a | n/a | | |"
                )
                continue
            lines.append(
                f"| {system['name']} | {entity_type} | {row['n']} | "
                f"{_num(row['precision'])} | {_num(row['recall'])} | {_num(row['f1'])} | "
                f"{_num(row['f2'])} | {row['fp']} | {row['fn']} |"
            )
        negative = system["negative"]
        misses = system["name_misses"]
        lines.append(
            f"| {system['name']} | negative | {negative['documents']} |  |  |  |  | "
            f"clean {negative['clean_docs']}/{negative['documents']}; "
            f"false_positives {negative['false_positives']}; "
            f"other_fp {system['other_false_positives']}; "
            f"name_fn cued {misses['false_negatives_with_prefix_cue']} "
            f"uncued {misses['false_negatives_without_prefix_cue']} | |"
        )
    ablation = report["ablations"]
    lines.extend(
        ["", "Layer ablation (removed minus full). A negative delta means the layer helped."]
    )
    if ablation.get("status") != "ok":
        lines.append(f"ablation {ablation.get('status')}: {ablation.get('reason', '')}")
        return "\n".join(lines)
    lines.extend(
        [
            "",
            "| Layer removed | micro P | micro R | micro F1 | micro F2 | delta R | delta F2 |",
            "|---|---:|---:|---:|---:|---:|---:|",
            (
                f"| full | {_num(ablation['full_micro']['precision'])} | "
                f"{_num(ablation['full_micro']['recall'])} | {_num(ablation['full_micro']['f1'])} | "
                f"{_num(ablation['full_micro']['f2'])} |  |  |"
            ),
        ]
    )
    by_layer = {}
    for row in ablation["layers"]:
        by_layer[row["disabled"]] = row
        lines.append(
            f"| {row['disabled']} | {_num(row['micro']['precision'])} | "
            f"{_num(row['micro']['recall'])} | {_num(row['micro']['f1'])} | "
            f"{_num(row['micro']['f2'])} | {_signed(row['delta_micro_recall'])} | "
            f"{_signed(row['delta_micro_f2'])} |"
        )
    for disabled in ("tb", "fp"):
        row = by_layer[disabled]
        lines.extend(
            [
                "",
                f"Per-type recall with `{disabled}` removed.",
                "",
                "| Type | n | full R | removed R | delta R |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for entity_type in REDACTION_TYPES:
            full = ablation["full_by_type"][entity_type]
            removed = row["by_type"][entity_type]
            lines.append(
                f"| {entity_type} | {full['n']} | {_num(full['recall'])} | "
                f"{_num(removed['recall'])} | {_signed(row['delta_by_type_recall'][entity_type])} |"
            )
    address_full = ablation["full_by_type"]["ADDRESS"]
    address_removed = by_layer["address_merge"]["by_type"]["ADDRESS"]
    lines.extend(
        [
            "",
            (
                "ADDRESS with `address_merge` removed: "
                f"precision {_num(address_full['precision'])} to "
                f"{_num(address_removed['precision'])}, "
                f"recall {_num(address_full['recall'])} to {_num(address_removed['recall'])}, "
                f"fp {address_full['fp']} to {address_removed['fp']}."
            ),
        ]
    )
    section = report.get("section26") or {}
    if section.get("status") == "ok":
        recall = section.get("micro_recall")
        recall_text = "n/a" if recall is None else _num(recall)
        lines.append(
            f"Section 26 keyword micro recall {recall_text} on n={section['n']} (warn/report, not a redaction score)."
        )
    utility = report.get("utility") or {}
    if utility.get("status") != "ok":
        lines.append(f"Utility {utility.get('status', 'skipped')}: {utility.get('reason', '')}.")
    return "\n".join(lines)


def _contrast(split: str, report: dict, *, brief: bool) -> str:
    guard = _system(report, "aiguard")
    regex = _system(report, "regex")
    thai = _system(report, "pythainlp-ner")
    wang = _system(report, "wangchanberta-ner")
    layers = {row["disabled"]: row for row in report["ablations"]["layers"]}
    tb = layers["tb"]
    fp = layers["fp"]
    name = guard["by_type"]["NAME"]
    misses = guard["name_misses"]
    address = guard["by_type"]["ADDRESS"]
    dropped = [
        entity_type
        for entity_type in REDACTION_TYPES
        if fp["delta_by_type_recall"][entity_type] < -1e-9
    ]
    head = (
        f"{split}: AI Guard micro F1 {_num(guard['micro']['f1'])} "
        f"F2 {_num(guard['micro']['f2'])} "
        f"(P {_num(guard['micro']['precision'])} R {_num(guard['micro']['recall'])}), "
        f"macro F1 {_num(guard['macro']['f1'])} F2 {_num(guard['macro']['f2'])} "
        f"over {guard['macro']['types']} types. "
        f"Removing tb takes NAME recall from {_num(name['recall'])} to "
        f"{_num(tb['by_type']['NAME']['recall'])} "
        f"(micro recall {_signed(tb['delta_micro_recall'])}). "
        f"Removing fp changes micro recall by {_signed(fp['delta_micro_recall'])} "
        f"and drops {', '.join(dropped)}."
    )
    if brief:
        return head
    return (
        head + " "
        f"NAME fn {name['fn']}, cued {misses['false_negatives_with_prefix_cue']}, "
        f"uncued {misses['false_negatives_without_prefix_cue']}. "
        f"Regex NAME recall {_num(regex['by_type']['NAME']['recall'])}. "
        f"PyThaiNLP NAME recall {_num(thai['by_type']['NAME']['recall'])}, "
        f"other_fp {thai['other_false_positives']}. "
        f"WangchanBERTa NAME recall {_num(wang['by_type']['NAME']['recall'])}, "
        f"other_fp {wang['other_false_positives']}. "
        f"ADDRESS precision {_num(address['precision'])}, recall {_num(address['recall'])}, "
        f"fp {address['fp']}. "
        f"Negative clean {guard['negative']['clean_docs']}/{guard['negative']['documents']}, "
        f"other_fp {guard['other_false_positives']}."
    )


def contrast_lines(reports: dict[str, dict], labels: dict[str, dict] | None = None) -> list[str]:
    """Measured contrasts for the Why NER note. Figures come from the JSON."""
    lines = [
        _contrast("hard-test", reports["hard-test"], brief=False),
        _contrast("hard-dev", reports["hard-dev"], brief=True),
        _contrast("freeze", reports["freeze"], brief=False),
    ]
    if not labels:
        return lines
    for split in ("hard-test", "hard-dev", "freeze"):
        other = labels[split]["other"]
        negative = labels[split]["negative"]
        other_text = ", ".join(f"{key} {value}" for key, value in sorted(other.items())) or "none"
        negative_text = (
            ", ".join(f"{key} {value}" for key, value in sorted(negative.items())) or "none"
        )
        lines.append(
            f"{split} label counts: out-of-scheme {other_text}; negative documents {negative_text}."
        )
    return lines
