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
print_section "SDV Test Framework v4 - Example Test Runner"
print_info "Testing the new v4 framework with existing test cases"
echo

# Check if test framework v4 is built
if ! docker images | grep -q "sdv-test-framework-v4"; then
    print_error "Test framework v4 not found. Building it now..."
    ./build-test-framework.sh
    if [ $? -ne 0 ]; then
        print_error "Failed to build test framework v4"
        exit 1
    fi
fi

# Check if examples are built
if ! docker images | grep -q "sdv-cpp-engine-monitor"; then
    print_error "Example images not found. Please run ./build-examples.sh first"
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
    print_info "Command: ./run-tests-v4.sh -i $image -t $test_path ${args[*]}"
    echo -e "${YELLOW}────────────────────────────────────────────────────────────────${NC}\n"
    
    if ./run-tests-v4.sh -i "$image" -t "$test_path" "${args[@]}"; then
        print_info "✅ $name: PASSED"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        print_error "❌ $name: FAILED"
    fi
}

# Clean up any existing test results
rm -rf test-results/*

# Test 1: C++ Engine Monitor - Integration Tests
print_section "Test 1: C++ Engine Monitor - Integration Tests"
run_test_suite \
    "C++ Engine Monitor - Integration" \
    "sdv-cpp-engine-monitor:latest" \
    "examples/cpp-engine-monitor/tests/integration.yaml"

# Test 2: Python Speed Monitor - Smoke Tests
print_section "Test 2: Python Speed Monitor - Smoke Tests"
run_test_suite \
    "Python Speed Monitor - Smoke" \
    "sdv-python-speed-monitor:latest" \
    "examples/python-speed-monitor/tests/smoke.yaml"

# Test 3: Python Speed Monitor - All Tests in Directory
print_section "Test 3: Python Speed Monitor - All Tests"
run_test_suite \
    "Python Speed Monitor - All Tests" \
    "sdv-python-speed-monitor:latest" \
    "examples/python-speed-monitor/tests"

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

# Show migration notes
print_section "Migration Notes"
echo "The test framework v4 provides:"
echo "✓ Full compatibility with existing test YAML format"
echo "✓ Enhanced reporting with requirements tracking"
echo "✓ State machine observability through structured logging"
echo "✓ Support for VSS actuator modes (target/actual)"
echo "✓ Complex expression evaluation in expectations"
echo ""
echo "To migrate existing tests:"
echo "1. Use ./run-tests-v4.sh instead of ./run-tests-v2.sh"
echo "2. All existing test files work without modification"
echo "3. Optionally add VFF specifications for enhanced validation"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    print_info "🎉 All test scenarios completed successfully!"
    exit 0
else
    print_error "💥 Some test scenarios failed!"
    exit 1
fi