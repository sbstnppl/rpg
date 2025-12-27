#!/bin/bash
# Autonomous E2E test-fix loop for Claude Code
# Runs /e2e-fix repeatedly with timeout-based continuation
# Stops after 3 consecutive 100% pass iterations
#
# Usage:
#   ./scripts/e2e-fix-loop.sh
#
# Controls:
#   - Press 'n' at prompt to stop
#   - Press Ctrl+C to abort immediately
#   - Do nothing for 120s to auto-continue

set -e

TIMEOUT=120  # seconds to wait before auto-continuing
PROJECT_DIR="/mnt/procyon-projects/rpg"
PASS_FILE="/tmp/e2e-fix-pass-streak"
LOG_FILE="$PROJECT_DIR/logs/e2e-fix-loop.log"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "═══════════════════════════════════════════════════════════"
echo "  AUTONOMOUS E2E FIX LOOP"
echo "  Press Ctrl+C or type 'n' to stop"
echo "  Auto-stops after 3 consecutive 100% pass iterations"
echo "  Timeout: ${TIMEOUT}s (auto-continues if no input)"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Log file: $LOG_FILE"
echo ""

# Initialize
echo "0" > "$PASS_FILE"
iteration=1
mkdir -p "$(dirname "$LOG_FILE")"
echo "=== E2E Fix Loop Started: $(date) ===" >> "$LOG_FILE"

while true; do
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    printf "║  ITERATION %-3d                                          ║\n" $iteration
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""

    # Log iteration start
    echo "" >> "$LOG_FILE"
    echo "--- Iteration $iteration: $(date) ---" >> "$LOG_FILE"

    # Run Claude Code with the e2e-fix command
    # Use tee to show output and capture it for parsing
    cd "$PROJECT_DIR"
    output=$(claude --dangerously-skip-permissions -p "/e2e-fix" 2>&1 | tee /dev/tty)

    # Log the output
    echo "$output" >> "$LOG_FILE"

    echo ""
    echo "───────────────────────────────────────────────────────────"

    # Check for PASS result by parsing output
    if echo "$output" | grep -q "RESULT: PASS"; then
        streak=$(($(cat "$PASS_FILE") + 1))
        echo "$streak" > "$PASS_FILE"
        echo -e "${GREEN}✓ Pass streak: $streak/3${NC}"

        if [ $streak -ge 3 ]; then
            echo ""
            echo "═══════════════════════════════════════════════════════════"
            echo -e "${GREEN}  3 CONSECUTIVE PASSES - STOPPING LOOP${NC}"
            echo "  All tests stable. Total iterations: $iteration"
            echo "═══════════════════════════════════════════════════════════"
            echo "=== Loop completed (3 passes): $(date) ===" >> "$LOG_FILE"
            break
        fi
    elif echo "$output" | grep -q "RESULT: FIXED"; then
        # Reset streak on fix (tests changed)
        echo "0" > "$PASS_FILE"
        echo -e "${YELLOW}→ Fix committed, resetting pass streak${NC}"
    else
        # Reset streak on any other result
        echo "0" > "$PASS_FILE"
    fi

    # Prompt with timeout
    echo ""
    read -t $TIMEOUT -p "Continue? [Y/n] (auto-yes in ${TIMEOUT}s): " answer || answer="y"

    case "${answer,,}" in
        n|no)
            echo ""
            echo "Stopping loop. Check git log for commits made."
            echo "=== Loop stopped by user: $(date) ===" >> "$LOG_FILE"
            break
            ;;
        *)
            iteration=$((iteration + 1))
            ;;
    esac
done

# Cleanup
rm -f "$PASS_FILE"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  LOOP ENDED - $iteration iterations completed"
echo "  Review commits: git log --oneline -10"
echo "═══════════════════════════════════════════════════════════"
