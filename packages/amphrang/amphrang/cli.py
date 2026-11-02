"""Amphrang — Thai PII detection CLI."""

import argparse
import sys


def cmd_report(args):
    """Generate a PII risk report for a text file (no redaction)."""
    from pathlib import Path

    from amphrang import analyze

    try:
        raw_text = Path(args.file).read_text(encoding="utf-8")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Failed to read file: {e}", file=sys.stderr)
        sys.exit(1)

    report = analyze(raw_text)
    fp_count = report["fp_count"]
    tb_count = report["tb_count"]

    print(f"=== PII Risk Report: {args.file} ===")
    print(f"Total entities detected: {report['direct_pii_count']}")
    print(f"  Structured PII (FP): {fp_count}")
    print(f"  Name/Address/Date (TB): {tb_count}")

    if fp_count:
        print("\nStructured PII types:")
        type_counts = {}
        for row in report["breakdown"]:
            if row["redact_type"] == "FP":
                type_counts[row["data_type"]] = row["count"]
        for dtype, count in sorted(type_counts.items()):
            print(f"  {dtype}: {count}")

    if tb_count:
        print("\nNamed entity types:")
        type_counts = {}
        for row in report["breakdown"]:
            if row["redact_type"] != "FP":
                type_counts[row["data_type"]] = row["count"]
        for dtype, count in sorted(type_counts.items()):
            print(f"  {dtype}: {count}")

    if report["section26"]:
        print("\nSection 26 warnings (not automatically masked):")
        for hit in report["section26"]:
            print(f"  {hit['category']}")

    total = fp_count + tb_count
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
