#!/usr/bin/env python3
"""
DO-178C Traceability Report Generator.

Parses requirements_matrix.yaml and generates a compliance report.

Usage:
    python tests/traceability/coverage_report.py
    python tests/traceability/coverage_report.py --junit-xml results.xml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def load_matrix(path: Path) -> dict:
    """Load requirements matrix from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("requirements", {})


def generate_report(requirements: dict) -> str:
    """Generate a text traceability report."""
    lines = []
    lines.append("=" * 70)
    lines.append("DO-178C TRACEABILITY REPORT")
    lines.append("=" * 70)
    lines.append("")

    total = len(requirements)
    covered = sum(1 for r in requirements.values() if r.get("tests"))
    uncovered = total - covered

    lines.append(f"Total Requirements: {total}")
    lines.append(f"With Test Coverage: {covered}")
    lines.append(f"Missing Coverage:   {uncovered}")
    lines.append(f"Coverage Rate:      {covered/total*100:.1f}%")
    lines.append("")

    # Group by standard
    by_standard = {}
    for req_id, req in requirements.items():
        std = req.get("standard", "Unknown")
        by_standard.setdefault(std, []).append((req_id, req))

    for standard, reqs in sorted(by_standard.items()):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"Standard: {standard}")
        lines.append(f"{'─' * 50}")

        for req_id, req in reqs:
            tests = req.get("tests", [])
            status = "✅ COVERED" if tests else "❌ MISSING"
            lines.append(f"\n  {req_id}: {req['description']}")
            lines.append(f"    Source:  {req.get('source', 'N/A')}")
            lines.append(f"    Status:  {status}")
            if tests:
                for test in tests:
                    lines.append(f"    Test:    {test}")

    # Flag uncovered requirements
    uncovered_reqs = [
        (rid, r) for rid, r in requirements.items() if not r.get("tests")
    ]
    if uncovered_reqs:
        lines.append(f"\n\n{'!' * 70}")
        lines.append("WARNING: The following requirements have NO test coverage:")
        lines.append(f"{'!' * 70}")
        for req_id, req in uncovered_reqs:
            lines.append(f"  {req_id}: {req['description']}")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="DO-178C Traceability Report")
    parser.add_argument(
        "--matrix", default=None,
        help="Path to requirements_matrix.yaml",
    )
    args = parser.parse_args()

    matrix_path = Path(args.matrix) if args.matrix else (
        Path(__file__).parent / "requirements_matrix.yaml"
    )

    if not matrix_path.exists():
        print(f"ERROR: Requirements matrix not found at {matrix_path}")
        sys.exit(1)

    requirements = load_matrix(matrix_path)
    report = generate_report(requirements)
    print(report)


if __name__ == "__main__":
    main()
