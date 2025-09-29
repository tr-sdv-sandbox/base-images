#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_section() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}▶ $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

# Main execution
print_section "SDV Test Framework - Example Test Runner v2"
print_info "Demonstrating the new test discovery and execution features"
echo

# Check if test framework is built
if ! docker images | grep -q "sdv-test-framework"; then
    print_error "Test framework not found. Please run ./build-all.sh first"
    exit 1
fi

# Track overall results
TOTAL_TESTS=0
FAILED_TESTS=0

# Function to run tests and check results
run_test_suite() {
    local name="$1"
    local image="$2"
    local test_path="$3"
    shift 3
    local args=("$@")
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -e "\n${YELLOW}────────────────────────────────────────────────────────────────${NC}"
    print_info "Test Suite: $name"
    print_info "Command: ./run-tests-v2.sh -i $image -t $test_path ${args[*]}"
    echo -e "${YELLOW}────────────────────────────────────────────────────────────────${NC}\n"
    
    if ./run-tests-v2.sh -i "$image" -t "$test_path" "${args[@]}"; then
        print_info "✅ $name: PASSED"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        print_error "❌ $name: FAILED"
    fi
}

# Clean up any existing test results
rm -rf test-results/*

print_section "Test Scenario 1: Run All Tests in Directory"
run_test_suite \
    "Python Speed Monitor - All Tests" \
    "sdv-engine-monitor:latest" \
    "examples/cpp-engine-monitor/tests"
    
# Summary
print_section "Overall Test Summary"
PASSED_TESTS=$((TOTAL_TESTS - FAILED_TESTS))
echo -e "Total Test Scenarios: ${BLUE}$TOTAL_TESTS${NC}"
echo -e "Passed:               ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:               ${RED}$FAILED_TESTS${NC}"
echo

# Show results structure
print_section "Test Results Structure"
print_info "Results are organized by timestamp and test suite:"
tree test-results/ 2>/dev/null || find test-results -type f -name "*.json" | sort

if [ $FAILED_TESTS -eq 0 ]; then
    print_info "🎉 All test scenarios completed successfully!"
    exit 0
else
    print_error "💥 Some test scenarios failed!"
    exit 1
fi
