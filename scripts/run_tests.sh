#!/bin/bash
# ============================================================
# Drone Inspector — Test Runner (pytest-based)
# ============================================================
# Usage:
#   ./scripts/run_tests.sh                  # All non-SITL tests
#   ./scripts/run_tests.sh --sitl           # Include SITL tests
#   ./scripts/run_tests.sh --layer unit     # Only unit tests
#   ./scripts/run_tests.sh --coverage       # With coverage report
#   ./scripts/run_tests.sh --traceability   # Generate DO-178C report
#   ./scripts/run_tests.sh --no-log         # Disable log saving
#
# Logs are saved to: data/logs/tests/test_<layer>.log (latest only)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COLORIZER="$SCRIPT_DIR/colorize_output.py"

cd "$PROJECT_DIR"

# ──────────────────────────────────────────────────────────────
# ANSI color codes
# ──────────────────────────────────────────────────────────────
C_RESET="\033[0m"
C_BOLD="\033[1m"
C_DIM="\033[2m"
C_RED="\033[91m"
C_GREEN="\033[92m"
C_YELLOW="\033[93m"
C_CYAN="\033[96m"
C_WHITE="\033[97m"
C_BG_GREEN="\033[42m"
C_BG_RED="\033[41m"
C_BG_CYAN="\033[46m"

# Defaults
LAYER=""
INCLUDE_SITL=false
COVERAGE=false
TRACEABILITY=false
VERBOSE="-v"
EXTRA_ARGS=""
SAVE_LOG=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --sitl)
            INCLUDE_SITL=true
            shift
            ;;
        --layer)
            LAYER="$2"
            shift 2
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        --traceability)
            TRACEABILITY=true
            shift
            ;;
        --quiet|-q)
            VERBOSE=""
            shift
            ;;
        --no-log)
            SAVE_LOG=false
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --sitl            Include SITL end-to-end tests (requires PX4)"
            echo "  --layer LAYER     Run only: unit|integration|failsafe|protocol|sitl"
            echo "  --coverage        Generate HTML coverage report"
            echo "  --traceability    Generate DO-178C traceability report"
            echo "  --quiet, -q       Less verbose output"
            echo "  --no-log          Disable saving test output to log file"
            echo "  --help            Show this help"
            exit 0
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

# ──────────────────────────────────────────────────────────────
# Log file setup
# ──────────────────────────────────────────────────────────────
LOG_DIR="$PROJECT_DIR/data/logs/tests"
mkdir -p "$LOG_DIR"

LAYER_TAG="${LAYER:-all}"
LOG_FILE="$LOG_DIR/test_${LAYER_TAG}.log"

echo ""
printf "${C_BOLD}${C_CYAN}══════════════════════════════════════════════════${C_RESET}\n"
printf "${C_BOLD}${C_WHITE}  🚁  Drone Inspector — Automation Test Suite     ${C_RESET}\n"
printf "${C_BOLD}${C_CYAN}══════════════════════════════════════════════════${C_RESET}\n"
echo ""

# Deactivate conflicting ROS plugins
export PYTHONDONTWRITEBYTECODE=1

# Build pytest command
PYTEST_CMD="python -m pytest"

# Layer selection
if [ -n "$LAYER" ]; then
    case "$LAYER" in
        unit)
            PYTEST_CMD="$PYTEST_CMD tests/unit/"
            printf " Layer: ${C_BOLD}${C_CYAN}Unit Tests${C_RESET}\n"
            ;;
        integration)
            PYTEST_CMD="$PYTEST_CMD tests/integration/"
            printf " Layer: ${C_BOLD}${C_CYAN}Integration Tests${C_RESET}\n"
            ;;
        failsafe)
            PYTEST_CMD="$PYTEST_CMD tests/failsafe/"
            printf " Layer: ${C_BOLD}${C_YELLOW}Failsafe Tests (FAA/EASA)${C_RESET}\n"
            ;;
        protocol)
            PYTEST_CMD="$PYTEST_CMD tests/protocol/"
            printf " Layer: ${C_BOLD}${C_CYAN}Protocol Tests${C_RESET}\n"
            ;;
        sitl)
            PYTEST_CMD="$PYTEST_CMD tests/sitl/"
            INCLUDE_SITL=true
            printf " Layer: ${C_BOLD}${C_GREEN}SITL End-to-End Tests${C_RESET}\n"
            ;;
        *)
            echo "Unknown layer: $LAYER"
            echo "Available: unit, integration, failsafe, protocol, sitl"
            exit 1
            ;;
    esac
else
    PYTEST_CMD="$PYTEST_CMD tests/"
    printf " Layer: ${C_BOLD}${C_WHITE}ALL${C_RESET}\n"
fi

# SITL marker filtering
if [ "$INCLUDE_SITL" = false ]; then
    PYTEST_CMD="$PYTEST_CMD -m 'not sitl and not hitl'"
    printf " SITL:  ${C_DIM}Skipped${C_RESET} (use --sitl to include)\n"
else
    PYTEST_CMD="$PYTEST_CMD -m 'not hitl'"
    printf " SITL:  ${C_BOLD}${C_GREEN}Included${C_RESET}\n"
fi

# Coverage
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing --cov-report=html:data/reports/coverage"
    printf " Coverage: ${C_BOLD}${C_GREEN}Enabled${C_RESET} (HTML → data/reports/coverage/)\n"
fi

# Verbose + disable pytest colors (our colorizer handles it)
PYTEST_CMD="$PYTEST_CMD $VERBOSE --tb=short --color=no $EXTRA_ARGS"

# Log info
if [ "$SAVE_LOG" = true ]; then
    printf " Log:   ${C_DIM}${LOG_FILE}${C_RESET}\n"
fi

echo ""
printf "${C_BOLD}${C_CYAN}══════════════════════════════════════════════════${C_RESET}\n"
echo ""

# ──────────────────────────────────────────────────────────────
# Run tests (with colorized output + optional log capture)
# ──────────────────────────────────────────────────────────────
if [ "$SAVE_LOG" = true ]; then
    # Write a colorized header to the log file
    {
        printf "\033[1;96m══════════════════════════════════════════════════\033[0m\n"
        printf "\033[1;97m  🚁  Drone Inspector — Test Log\033[0m\n"
        printf "\033[2m  Date:    $(date '+%Y-%m-%d %H:%M:%S %Z')\033[0m\n"
        printf "\033[2m  Layer:   ${LAYER_TAG}\033[0m\n"
        printf "\033[2m  Command: $PYTEST_CMD\033[0m\n"
        printf "\033[1;96m══════════════════════════════════════════════════\033[0m\n"
        echo ""
    } > "$LOG_FILE"

    # Run tests; colorize output via Python filter, tee to log file.
    # Use pipefail so we capture pytest's exit code through the pipe.
    set +e
    set -o pipefail
    eval $PYTEST_CMD 2>&1 | python3 "$COLORIZER" | tee -a "$LOG_FILE"
    TEST_EXIT=${PIPESTATUS[0]}
    set -e
else
    set +e
    set -o pipefail
    eval $PYTEST_CMD 2>&1 | python3 "$COLORIZER"
    TEST_EXIT=${PIPESTATUS[0]}
    set -e
fi

# Traceability report
if [ "$TRACEABILITY" = true ]; then
    echo ""
    printf "${C_BOLD}${C_CYAN}══════════════════════════════════════════════════${C_RESET}\n"
    printf "${C_BOLD}${C_WHITE}  DO-178C Traceability Report${C_RESET}\n"
    printf "${C_BOLD}${C_CYAN}══════════════════════════════════════════════════${C_RESET}\n"
    if [ "$SAVE_LOG" = true ]; then
        python tests/traceability/coverage_report.py 2>&1 | tee -a "$LOG_FILE"
    else
        python tests/traceability/coverage_report.py
    fi
fi

# ──────────────────────────────────────────────────────────────
# Colorized result banner
# ──────────────────────────────────────────────────────────────
echo ""
if [ "$TEST_EXIT" -eq 0 ]; then
    printf "${C_BOLD}${C_BG_GREEN}${C_WHITE}                                                  ${C_RESET}\n"
    printf "${C_BOLD}${C_BG_GREEN}${C_WHITE}   ✅  ALL TESTS PASSED  (exit code: 0)            ${C_RESET}\n"
    printf "${C_BOLD}${C_BG_GREEN}${C_WHITE}                                                  ${C_RESET}\n"
else
    printf "${C_BOLD}${C_BG_RED}${C_WHITE}                                                  ${C_RESET}\n"
    printf "${C_BOLD}${C_BG_RED}${C_WHITE}   ❌  TESTS FAILED  (exit code: $TEST_EXIT)              ${C_RESET}\n"
    printf "${C_BOLD}${C_BG_RED}${C_WHITE}                                                  ${C_RESET}\n"
fi
echo ""

# Append colorized summary to log
if [ "$SAVE_LOG" = true ]; then
    {
        echo ""
        if [ "$TEST_EXIT" -eq 0 ]; then
            printf "\033[1;42;97m   ✅  ALL TESTS PASSED  (exit code: 0)            \033[0m\n"
        else
            printf "\033[1;41;97m   ❌  TESTS FAILED  (exit code: $TEST_EXIT)              \033[0m\n"
        fi
        printf "\033[2m  Log saved: $LOG_FILE\033[0m\n"
    } >> "$LOG_FILE"
    printf " ${C_DIM}Log saved: ${LOG_FILE}${C_RESET}\n"
    echo ""
fi

exit $TEST_EXIT
