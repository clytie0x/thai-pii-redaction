"""Amphrang — Thai PII detection CLI."""

import argparse
import sys


def cmd_report(args):
    """Generate a PII risk report for a text file (no redaction)."""
    from pathlib import Path

    from amphrang.engine.detectors.aggregate import detect_all
    from amphrang.engine.ingest.text_cleaner import clean

    try:
        raw_text = Path(args.file).read_text(encoding="utf-8")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Failed to read file: {e}", file=sys.stderr)
        sys.exit(1)

    text = clean(raw_text).text

    merged = detect_all(text)
    fp_entities = [e for e in merged if e.redact_type == "FP"]
    tb_entities = [e for e in merged if e.redact_type != "FP"]

    print(f"=== PII Risk Report: {args.file} ===")
    print(f"Total entities detected: {len(merged)}")
    print(f"  Structured PII (FP): {len(fp_entities)}")
    print(f"  Name/Address/Date (TB): {len(tb_entities)}")

    if fp_entities:
        print("\nStructured PII types:")
        type_counts = {}
        for e in fp_entities:
            type_counts[e.data_type] = type_counts.get(e.data_type, 0) + 1
        for dtype, count in sorted(type_counts.items()):
            print(f"  {dtype}: {count}")

    if tb_entities:
        print("\nNamed entity types:")
        type_counts = {}
        for e in tb_entities:
            type_counts[e.data_type] = type_counts.get(e.data_type, 0) + 1
        for dtype, count in sorted(type_counts.items()):
            print(f"  {dtype}: {count}")

    total = len(fp_entities) + len(tb_entities)
    if total == 0:
        risk = "Low"
    elif total <= 5:
        risk = "Medium"
    else:
        risk = "High"

    print(f"\nRisk Level: {risk}")


def main():
    parser = argparse.ArgumentParser(
        prog="amphrang",
        description="Amphrang — Thai PII detection and anonymization",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # report subcommand
    report_parser = subparsers.add_parser("report", help="Generate PII risk report")
    report_parser.add_argument("file", help="Input text file path")
    report_parser.set_defaults(func=cmd_report)

    # serve subcommand — local backend (needs [server] extra)
    serve_parser = subparsers.add_parser("serve", help="Run the local backend")
    from amphrang.serve import add_serve_arguments, run_serve

    add_serve_arguments(serve_parser)
    serve_parser.set_defaults(func=run_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
