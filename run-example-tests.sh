#!/bin/bash
# Test runner for all example user functions with the new architecture

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

# Check if example images exist
check_images() {
    local missing=0
    
    if ! docker image inspect sdv-speed-monitor:latest >/dev/null 2>&1; then
        print_error "Image sdv-speed-monitor:latest not found"
        missing=1
    fi
    
    if ! docker image inspect sdv-engine-monitor:latest >/dev/null 2>&1; then
        print_error "Image sdv-engine-monitor:latest not found"
        missing=1
    fi
    
    if ! docker image inspect sdv-engine-monitor:alpine >/dev/null 2>&1; then
        print_error "Image sdv-engine-monitor:alpine not found"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        print_info "Building example images..."
        ./build-examples.sh
    fi
}

# Main execution
print_section "SDV Example Test Runner"
check_images

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
    print_info "Image: $image"
    print_info "Test Path: $test_path"
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

# Test Python Speed Monitor
print_section "Testing Python Speed Monitor"
run_test_suite \
    "Python Speed Monitor - All Tests" \
    "sdv-speed-monitor:latest" \
    "examples/python-speed-monitor/tests" \
    --pattern "*.yaml"

# Test C++ Engine Monitor (Debian)
print_section "Testing C++ Engine Monitor (Debian)"
run_test_suite \
    "C++ Engine Monitor (Debian) - All Tests" \
    "sdv-engine-monitor:latest" \
    "examples/cpp-engine-monitor/tests" \
    --pattern "*.yaml"

# Test C++ Engine Monitor (Alpine)
print_section "Testing C++ Engine Monitor (Alpine)"
run_test_suite \
    "C++ Engine Monitor (Alpine) - All Tests" \
    "sdv-engine-monitor:alpine" \
    "examples/cpp-engine-monitor/tests" \
    --pattern "*.yaml"

# Summary
print_section "Overall Test Summary"
PASSED_TESTS=$((TOTAL_TESTS - FAILED_TESTS))
echo -e "Total Test Suites:    ${BLUE}$TOTAL_TESTS${NC}"
echo -e "Passed:               ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:               ${RED}$FAILED_TESTS${NC}"
echo

# Show image sizes
print_section "Image Size Comparison"
echo -e "Python Speed Monitor:          $(docker images sdv-speed-monitor:latest --format "{{.Size}}")"
echo -e "C++ Engine Monitor (Debian):   $(docker images sdv-engine-monitor:latest --format "{{.Size}}")"
echo -e "C++ Engine Monitor (Alpine):   $(docker images sdv-engine-monitor:alpine --format "{{.Size}}")"
echo
echo -e "Runtime Base Images:"
echo -e "Python Runtime:                $(docker images sdv-python-runtime:latest --format "{{.Size}}")"
echo -e "C++ Runtime (Debian):          $(docker images sdv-cpp-runtime:latest --format "{{.Size}}")"
echo -e "C++ Runtime (Alpine):          $(docker images sdv-cpp-alpine-runtime:latest --format "{{.Size}}")"

if [ $FAILED_TESTS -eq 0 ]; then
    print_info "🎉 All tests passed successfully!"
    exit 0
else
    print_error "💥 Some tests failed!"
    exit 1
fi