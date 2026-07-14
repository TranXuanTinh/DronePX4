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
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Defaults
LAYER=""
INCLUDE_SITL=false
COVERAGE=false
TRACEABILITY=false
VERBOSE="-v"
EXTRA_ARGS=""

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
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --sitl            Include SITL end-to-end tests (requires PX4)"
            echo "  --layer LAYER     Run only: unit|integration|failsafe|protocol|sitl"
            echo "  --coverage        Generate HTML coverage report"
            echo "  --traceability    Generate DO-178C traceability report"
            echo "  --quiet, -q       Less verbose output"
            echo "  --help            Show this help"
            exit 0
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

echo "=============================================="
echo " Drone Inspector — Automation Test Suite"
echo "=============================================="
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
            echo " Layer: Unit Tests"
            ;;
        integration)
            PYTEST_CMD="$PYTEST_CMD tests/integration/"
            echo " Layer: Integration Tests"
            ;;
        failsafe)
            PYTEST_CMD="$PYTEST_CMD tests/failsafe/"
            echo " Layer: Failsafe Tests (FAA/EASA)"
            ;;
        protocol)
            PYTEST_CMD="$PYTEST_CMD tests/protocol/"
            echo " Layer: Protocol Tests"
            ;;
        sitl)
            PYTEST_CMD="$PYTEST_CMD tests/sitl/"
            INCLUDE_SITL=true
            echo " Layer: SITL End-to-End Tests"
            ;;
        *)
            echo "Unknown layer: $LAYER"
            echo "Available: unit, integration, failsafe, protocol, sitl"
            exit 1
            ;;
    esac
else
    PYTEST_CMD="$PYTEST_CMD tests/"
    echo " Layer: ALL"
fi

# SITL marker filtering
if [ "$INCLUDE_SITL" = false ]; then
    PYTEST_CMD="$PYTEST_CMD -m 'not sitl and not hitl'"
    echo " SITL:  Skipped (use --sitl to include)"
else
    PYTEST_CMD="$PYTEST_CMD -m 'not hitl'"
    echo " SITL:  Included"
fi

# Coverage
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing --cov-report=html:data/reports/coverage"
    echo " Coverage: Enabled (HTML → data/reports/coverage/)"
fi

# Verbose
PYTEST_CMD="$PYTEST_CMD $VERBOSE --tb=short $EXTRA_ARGS"

echo ""
echo "=============================================="
echo ""

# Run tests
eval $PYTEST_CMD
TEST_EXIT=$?

# Traceability report
if [ "$TRACEABILITY" = true ]; then
    echo ""
    echo "=============================================="
    echo " DO-178C Traceability Report"
    echo "=============================================="
    python tests/traceability/coverage_report.py
fi

echo ""
echo "=============================================="
echo " Test run complete (exit code: $TEST_EXIT)"
echo "=============================================="

exit $TEST_EXIT
