#!/usr/bin/env python3
"""Command-line interface for the multi-agent contradiction finder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contradiction_finder import (
    ConfigurationError,
    ContradictionHandlerAgent,
    DocumentInputError,
    load_documents,
    render_markdown,
    write_json_report,
    write_markdown_report,
)

REPORT_PATH = Path(__file__).resolve().parent / "agent-outputs" / "contradiction-report.md"
JSON_REPORT_PATH = (
    Path(__file__).resolve().parent / "agent-outputs" / "contradiction-report.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find contradictions between two Markdown documents."
    )
    parser.add_argument(
        "architecture",
        type=Path,
        help="System architecture Markdown document",
    )
    parser.add_argument(
        "requirements",
        type=Path,
        help="System requirements Markdown document",
    )
    parser.add_argument(
        "--json",
        type=Path,
        metavar="PATH",
        help="Also write the structured report as JSON",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Exit after the initial report instead of accepting follow-up questions",
    )
    return parser.parse_args(argv)


def interactive_session(handler: ContradictionHandlerAgent) -> None:
    print("\nAsk follow-up questions about the report. Type 'exit' to finish.")
    while True:
        try:
            question = input("\ncontradiction-finder> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question.lower() in {"exit", "quit"}:
            return
        if not question:
            continue
        print(handler.ask(question))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        corpus = load_documents(args.architecture, args.requirements)
        handler = ContradictionHandlerAgent()
        report = handler.analyze(corpus)
    except (ConfigurationError, DocumentInputError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nAnalysis cancelled.", file=sys.stderr)
        return 130

    markdown_path = write_markdown_report(report, REPORT_PATH)
    json_path = write_json_report(report, JSON_REPORT_PATH)
    print(render_markdown(report), end="")
    print(f"Markdown report written to {markdown_path}", file=sys.stderr)
    print(f"JSON report written to {json_path}", file=sys.stderr)
    if args.json:
        additional_json_path = write_json_report(report, args.json)
        print(f"\nJSON report written to {additional_json_path}")

    if not args.no_interactive:
        interactive_session(handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
