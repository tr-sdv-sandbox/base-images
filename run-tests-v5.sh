#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DOCKER_IMAGE=""
TEST_PATH=""
TEST_PATTERN="*.yaml"
CONTAINER_NAME=""
ENV_VARS=()
WAIT_TIME=5
VERBOSE=false
KEEP_RUNNING=false
FAIL_FAST=false

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] --image <docker-image> --tests <path>

Run SDV test framework v5 (C++) against a user function Docker image

Required Arguments:
    -i, --image     Docker image to test (e.g., my-function:latest)
    -t, --tests     Path to test file or directory

Optional Arguments:
    -p, --pattern   File pattern when testing directory (default: *.yaml)
    -n, --name      Container name (default: auto-generated)
    -e, --env       Environment variable (can be used multiple times)
    -w, --wait      Time to wait for services to start (default: 5s)
    --fail-fast     Stop on first test failure
    -v, --verbose   Show detailed output
    -k, --keep      Keep containers running after tests
    -h, --help      Show this help message

Examples:
    # Run all tests in a directory
    $0 --image my-function:latest --tests ./tests

    # Run a specific test file
    $0 --image my-function:latest --tests ./tests/integration.yaml

    # Run with custom environment and fail fast
    $0 -i my-function:latest -t ./tests -e LOG_LEVEL=debug --fail-fast

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--image)
            DOCKER_IMAGE="$2"
            shift 2
            ;;
        -t|--tests)
            TEST_PATH="$2"
            shift 2
            ;;
        -p|--pattern)
            TEST_PATTERN="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -e|--env)
            ENV_VARS+=("-e" "$2")
            shift 2
            ;;
        -w|--wait)
            WAIT_TIME="$2"
            shift 2
            ;;
        --fail-fast)
            FAIL_FAST=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -k|--keep)
            KEEP_RUNNING=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown argument: $1"
            usage
            ;;
    esac
done

# Check required arguments
if [ -z "$DOCKER_IMAGE" ]; then
    print_error "Missing required argument: --image"
    usage
fi

if [ -z "$TEST_PATH" ]; then
    print_error "Missing required argument: --tests"
    usage
fi

# Check if test path exists
if [ ! -e "$TEST_PATH" ]; then
    print_error "Test path not found: $TEST_PATH"
    exit 1
fi

# Collect test files
TEST_FILES=()
if [ -f "$TEST_PATH" ]; then
    # Single file specified
    TEST_FILES=("$TEST_PATH")
elif [ -d "$TEST_PATH" ]; then
    # Directory specified - find all matching files
    while IFS= read -r -d '' file; do
        TEST_FILES+=("$file")
    done < <(find "$TEST_PATH" -name "$TEST_PATTERN" -type f -print0 | sort -z)

    if [ ${#TEST_FILES[@]} -eq 0 ]; then
        print_error "No test files found matching pattern: $TEST_PATTERN in $TEST_PATH"
        exit 1
    fi
else
    print_error "Test path is neither file nor directory: $TEST_PATH"
    exit 1
fi

print_info "Found ${#TEST_FILES[@]} test file(s) to run"

# Generate container name if not provided
if [ -z "$CONTAINER_NAME" ]; then
    CONTAINER_NAME="test-subject-$(date +%s)"
fi

# Check if test framework v5 is built
if ! docker images | grep -q "test-framework-v5"; then
    print_error "Test framework v5 not found. Please build it first with ./test-framework-v5/build.sh"
    exit 1
fi

# Track test results
TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0

# Function to merge VSS extensions if present
merge_vss_with_extensions() {
    local test_dir="$1"
    local vss_extensions="${test_dir}/vss_extensions.json"

    # Check if extensions file exists
    if [ -f "$vss_extensions" ]; then
        print_info "Found VSS extensions: $vss_extensions" >&2

        # Create temp merged VSS file
        MERGED_VSS="/tmp/vss_merged_$(date +%s).json"

        # Use Python to merge (jq doesn't handle deep merging well)
        python3 ./merge-vss-extensions.py \
            test-data/vss_full.json \
            "$vss_extensions" \
            "$MERGED_VSS" >&2

        echo "$MERGED_VSS"
    else
        # Return absolute path
        echo "$(pwd)/test-data/vss_full.json"
    fi
}

# Set up cleanup function
cleanup() {
    print_info "Cleaning up..."

    # Stop and remove the test subject container
    if [ "$KEEP_RUNNING" != "true" ]; then
        if [ -n "$CONTAINER_NAME" ]; then
            print_info "Stopping container: $CONTAINER_NAME"
            docker stop --time 1 "$CONTAINER_NAME" >/dev/null 2>&1 || true
            docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
        fi

        # Stop fixture container if it exists
        if [ -n "$FIXTURE_CONTAINER" ]; then
            docker stop --time 1 "$FIXTURE_CONTAINER" >/dev/null 2>&1 || true
            docker rm "$FIXTURE_CONTAINER" >/dev/null 2>&1 || true
        fi

        # Stop databroker
        docker stop --time 1 databroker-test-v5 >/dev/null 2>&1 || true
        docker rm databroker-test-v5 >/dev/null 2>&1 || true

        # Remove network
        docker network rm test-network-v5 >/dev/null 2>&1 || true

        # Clean up temp fixture files
        rm -f /tmp/fixtures-*.json 2>/dev/null || true
    else
        print_info "Keeping containers running (--keep flag was set)"
    fi
}

# Register cleanup on exit, interrupt, termination, and errors
trap cleanup EXIT INT TERM ERR

# Determine test directory for VSS extensions
if [ -f "$TEST_PATH" ]; then
    TEST_DIR=$(dirname "$TEST_PATH")
else
    TEST_DIR="$TEST_PATH"
fi

# Merge VSS with extensions if present
VSS_FILE=$(merge_vss_with_extensions "$TEST_DIR")
export VSS_FILE

# Create dedicated network
print_info "Creating test network..."
docker network create test-network-v5 >/dev/null 2>&1 || true
NETWORK_NAME="test-network-v5"

# Start KUKSA databroker
print_info "Starting KUKSA databroker..."
print_info "Using VSS file: $VSS_FILE"
docker run -d \
    --name databroker-test-v5 \
    --network "$NETWORK_NAME" \
    -p 55556:55555 \
    -v "$VSS_FILE:/vss.json:ro" \
    ghcr.io/eclipse-kuksa/kuksa-databroker:0.6.0 \
    --metadata /vss.json

# Wait for databroker to be ready
print_info "Waiting for KUKSA databroker to be ready..."
for i in $(seq 1 20); do
    if nc -z localhost 55556 2>/dev/null; then
        print_info "KUKSA databroker is ready"
        break
    fi
    if [ $i -eq 20 ]; then
        print_error "KUKSA databroker failed to start"
        docker logs databroker-test-v5
        exit 1
    fi
    sleep 1
done

# Start fixture runner if test file has fixtures
# This ensures providers register BEFORE test subject starts
FIXTURE_CONTAINER=""
if [ "${#TEST_FILES[@]}" -eq 1 ]; then
    FIRST_TEST_FILE="${TEST_FILES[0]}"
    # Check if test file has fixtures section
    if grep -q "fixtures:" "$FIRST_TEST_FILE" 2>/dev/null; then
        print_info "Test has fixtures - starting fixture runner..."

        # Generate fixture config from test YAML
        FIXTURE_TEMP_FILE="/tmp/fixtures-$(date +%s).json"
        python3 -c "
import yaml
import json
import sys

with open('$FIRST_TEST_FILE', 'r') as f:
    spec = yaml.safe_load(f)

fixtures = spec.get('test_suite', {}).get('fixtures', [])
if fixtures:
    with open('$FIXTURE_TEMP_FILE', 'w') as out:
        json.dump({'fixtures': fixtures}, out, indent=2)
    print(f'Created {len(fixtures)} fixture(s)')
else:
    sys.exit(1)
"

        if [ $? -eq 0 ] && [ -f "$FIXTURE_TEMP_FILE" ]; then
            chmod 644 "$FIXTURE_TEMP_FILE"

            FIXTURE_CONTAINER="fixture-runner-$(date +%s)"
            docker run -d \
                --name "$FIXTURE_CONTAINER" \
                --network "$NETWORK_NAME" \
                --mount "type=bind,source=$FIXTURE_TEMP_FILE,target=/app/fixtures.json" \
                sdv-fixture-runner:latest \
                fixture-runner --config /app/fixtures.json

            if [ $? -ne 0 ]; then
                print_error "Failed to start fixture runner"
                exit 1
            fi

            print_info "Fixture runner started: $FIXTURE_CONTAINER"
            print_info "Waiting 3 seconds for providers to register..."
            sleep 3

            # Verify fixture is still running
            if ! docker ps | grep -q "$FIXTURE_CONTAINER"; then
                print_error "Fixture runner stopped unexpectedly"
                docker logs "$FIXTURE_CONTAINER" 2>&1 | tail -20
                exit 1
            fi
        fi
    fi
fi

# Start the user function container
print_info "Starting container: $CONTAINER_NAME"
print_info "Using image: $DOCKER_IMAGE"

# Build docker run command
DOCKER_RUN_CMD=(
    docker run -d
    --name "$CONTAINER_NAME"
    --network "$NETWORK_NAME"
    -e KUKSA_ADDRESS=databroker-test-v5
    -e KUKSA_PORT=55555
    -e KUKSA_TLS=false
)

DOCKER_RUN_CMD+=(
    "${ENV_VARS[@]}"
    "$DOCKER_IMAGE"
)

# Execute docker run
if [ "$VERBOSE" = true ]; then
    print_info "Docker command: ${DOCKER_RUN_CMD[*]}"
fi

"${DOCKER_RUN_CMD[@]}"

if [ $? -ne 0 ]; then
    print_error "Failed to start container"
    exit 1
fi

# Wait for container to start
print_info "Waiting $WAIT_TIME seconds for container to start..."
sleep "$WAIT_TIME"

# Check if container is still running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    print_error "Container stopped unexpectedly"
    print_error "Container logs:"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -20
    exit 1
fi

# Run each test file
for test_file in "${TEST_FILES[@]}"; do
    TOTAL_SUITES=$((TOTAL_SUITES + 1))

    # Extract test file name for results
    test_name=$(basename "$test_file" .yaml)

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_info "Running test suite: $test_file"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

    # Build test framework command
    TEST_FRAMEWORK_CMD=(
        docker run --rm
        --network "$NETWORK_NAME"
        --name test-framework-runner-$$
        -v "$(realpath "$test_file"):/tests/test-suite.yaml:ro"
        test-framework-v5:latest
        /tests/test-suite.yaml
        --kuksa-url databroker-test-v5:55555
    )

    # Run the test
    "${TEST_FRAMEWORK_CMD[@]}"
    TEST_EXIT_CODE=$?

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_info "Container logs (sorted by timestamp):"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

    # Collect all logs with timestamps and merge them by timestamp
    # Write to temp file to avoid broken pipe issues with set -e
    TEMP_LOGS="/tmp/merged-logs-$$.txt"
    {
        docker logs --timestamps "$CONTAINER_NAME" 2>&1 | sed "s/^/SUBJECT /"
        if [ -n "$FIXTURE_CONTAINER" ]; then
            docker logs --timestamps "$FIXTURE_CONTAINER" 2>&1 | sed "s/^/FIXTURE /"
        fi
    } | sort -k1,1 > "$TEMP_LOGS"

    # Apply colors and display
    sed -e "s/^SUBJECT /\x1b[36m[TEST-SUBJECT]\x1b[0m /" -e "s/^FIXTURE /\x1b[33m[TEST-FIXTURE]\x1b[0m /" "$TEMP_LOGS"
    rm -f "$TEMP_LOGS"

    echo ""

    if [ $TEST_EXIT_CODE -eq 0 ]; then
        PASSED_SUITES=$((PASSED_SUITES + 1))
        print_info "✅ Test suite PASSED: $test_name"
    else
        FAILED_SUITES=$((FAILED_SUITES + 1))
        print_error "❌ Test suite FAILED: $test_name"

        if [ "$FAIL_FAST" = true ]; then
            print_error "Fail-fast enabled, stopping test execution"
            break
        fi
    fi
done

# Summary report
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    TEST SUMMARY                            ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "Image tested:    $DOCKER_IMAGE"
echo -e "Test path:       $TEST_PATH"
if [ -d "$TEST_PATH" ]; then
    echo -e "Test pattern:    $TEST_PATTERN"
fi
echo -e "Total suites:    ${BLUE}$TOTAL_SUITES${NC}"
echo -e "Passed:          ${GREEN}$PASSED_SUITES${NC}"
echo -e "Failed:          ${RED}$FAILED_SUITES${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Exit with appropriate code
if [ $FAILED_SUITES -eq 0 ]; then
    print_info "🎉 All test suites passed!"
    exit 0
else
    print_error "💥 $FAILED_SUITES test suite(s) failed!"
    exit 1
fi
