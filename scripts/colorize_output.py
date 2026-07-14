#!/usr/bin/env python3
"""
Colorize pytest output with rich ANSI colors.

Adds colors to:
  - PASSED  → bright green  ✓
  - FAILED  → bright red    ✗
  - ERROR   → bold red
  - SKIPPED → yellow
  - [XX%]   → gradient (red → yellow → green)
  - Summary line (e.g., "123 passed, 2 failed in 5.3s")
  - Section separators (═══ lines)

Usage:
    pytest ... --color=no 2>&1 | python3 scripts/colorize_output.py
"""
from __future__ import annotations

import re
import sys

# ── ANSI escape codes ──────────────────────────────────────────
RESET       = "\033[0m"
BOLD        = "\033[1m"
DIM         = "\033[2m"

# Foreground
FG_RED      = "\033[31m"
FG_GREEN    = "\033[32m"
FG_YELLOW   = "\033[33m"
FG_BLUE     = "\033[34m"
FG_MAGENTA  = "\033[35m"
FG_CYAN     = "\033[36m"
FG_WHITE    = "\033[37m"

# Bright foreground
FG_BRED     = "\033[91m"
FG_BGREEN   = "\033[92m"
FG_BYELLOW  = "\033[93m"
FG_BBLUE    = "\033[94m"
FG_BMAGENTA = "\033[95m"
FG_BCYAN    = "\033[96m"

# Background
BG_RED      = "\033[41m"
BG_GREEN    = "\033[42m"
BG_YELLOW   = "\033[43m"
BG_BLUE     = "\033[44m"

# ── Status symbols ─────────────────────────────────────────────
PASS_LABEL  = f"{BOLD}{FG_BGREEN}PASSED{RESET}"
FAIL_LABEL  = f"{BOLD}{FG_BRED}FAILED{RESET}"
ERROR_LABEL = f"{BOLD}{FG_BRED}ERROR{RESET}"
SKIP_LABEL  = f"{BOLD}{FG_BYELLOW}SKIPPED{RESET}"
XFAIL_LABEL = f"{BOLD}{FG_YELLOW}XFAIL{RESET}"
XPASS_LABEL = f"{BOLD}{FG_BGREEN}XPASS{RESET}"


def _pct_color(pct: int) -> str:
    """Return an ANSI color code based on progress percentage (gradient)."""
    if pct <= 25:
        return FG_RED
    elif pct <= 50:
        return FG_YELLOW
    elif pct <= 75:
        return FG_BCYAN
    else:
        return FG_BGREEN


def colorize_percentage(match: re.Match) -> str:
    """Colorize [  XX%] percentage brackets."""
    spaces = match.group(1)
    pct = int(match.group(2))
    color = _pct_color(pct)
    return f"[{BOLD}{color}{spaces}{pct}%{RESET}]"


def colorize_summary_counts(line: str) -> str:
    """Colorize summary counts like '123 passed', '2 failed', etc."""
    line = re.sub(
        r"(\d+)\s+(passed)",
        lambda m: f"{BOLD}{FG_BGREEN}{m.group(1)} {m.group(2)}{RESET}",
        line,
    )
    line = re.sub(
        r"(\d+)\s+(failed)",
        lambda m: f"{BOLD}{FG_BRED}{m.group(1)} {m.group(2)}{RESET}",
        line,
    )
    line = re.sub(
        r"(\d+)\s+(error)",
        lambda m: f"{BOLD}{FG_BRED}{m.group(1)} {m.group(2)}{RESET}",
        line,
    )
    line = re.sub(
        r"(\d+)\s+(skipped)",
        lambda m: f"{BOLD}{FG_BYELLOW}{m.group(1)} {m.group(2)}{RESET}",
        line,
    )
    line = re.sub(
        r"(\d+)\s+(warnings?)",
        lambda m: f"{BOLD}{FG_YELLOW}{m.group(1)} {m.group(2)}{RESET}",
        line,
    )
    line = re.sub(
        r"(\d+)\s+(deselected)",
        lambda m: f"{BOLD}{FG_CYAN}{m.group(1)} {m.group(2)}{RESET}",
        line,
    )
    # Colorize timing "in X.XXs"
    line = re.sub(
        r"(in\s+[\d.]+s)",
        lambda m: f"{DIM}{FG_WHITE}{m.group(1)}{RESET}",
        line,
    )
    return line


def colorize_separator(line: str) -> str:
    """Colorize pytest separator lines (=== ... ===)."""
    stripped = line.rstrip()
    if re.match(r"^=+ .+ =+$", stripped):
        # Summary separator line — color based on content
        if "passed" in stripped and "failed" not in stripped and "error" not in stripped:
            return f"{FG_BGREEN}{stripped}{RESET}\n"
        elif "failed" in stripped or "error" in stripped:
            return f"{FG_BRED}{stripped}{RESET}\n"
        else:
            return f"{FG_BCYAN}{stripped}{RESET}\n"
    elif re.match(r"^=+$", stripped):
        return f"{FG_CYAN}{stripped}{RESET}\n"
    elif re.match(r"^-+$", stripped):
        return f"{DIM}{stripped}{RESET}\n"
    return None


def colorize_line(line: str) -> str:
    """Apply all colorization rules to a single line."""
    # Check for separator lines first
    sep = colorize_separator(line)
    if sep is not None:
        return sep

    # Colorize test status keywords
    line = line.replace(" PASSED", f" {PASS_LABEL}")
    line = line.replace(" FAILED", f" {FAIL_LABEL}")
    line = line.replace(" ERROR",  f" {ERROR_LABEL}")
    line = line.replace(" SKIPPED", f" {SKIP_LABEL}")
    line = line.replace(" XFAIL",  f" {XFAIL_LABEL}")
    line = line.replace(" XPASS",  f" {XPASS_LABEL}")

    # Colorize percentage progress [  XX%]
    line = re.sub(r"\[(\s*)(\d+)%\]", colorize_percentage, line)

    # Colorize summary count lines (e.g., "123 passed, 2 failed in 5.3s")
    if re.search(r"\d+\s+(passed|failed|error|skipped)", line):
        line = colorize_summary_counts(line)

    # Colorize collection lines "collected X items"
    line = re.sub(
        r"(collected\s+)(\d+)(\s+items?)",
        lambda m: f"{m.group(1)}{BOLD}{FG_BCYAN}{m.group(2)}{RESET}{m.group(3)}",
        line,
    )

    # Colorize FAILURES / ERRORS section headers
    if re.match(r"^_{3,}\s+.+\s+_{3,}$", line.strip()):
        return f"{BOLD}{FG_BRED}{line.rstrip()}{RESET}\n"

    # (Removed test path colorization to match standard plain format)

    return line


def main() -> None:
    """Read from stdin, colorize, and write to stdout."""
    try:
        for line in sys.stdin:
            sys.stdout.write(colorize_line(line))
            sys.stdout.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        # Gracefully handle pipe closure (e.g., head, less) or Ctrl+C
        pass


if __name__ == "__main__":
    main()
