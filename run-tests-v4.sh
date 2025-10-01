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
TAGS=()

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

Run SDV test framework v4 against a user function Docker image

Required Arguments:
    -i, --image     Docker image to test (e.g., my-function:latest)
    -t, --tests     Path to test file or directory

Optional Arguments:
    -p, --pattern   File pattern when testing directory (default: *.yaml)
    -n, --name      Container name (default: auto-generated)
    -e, --env       Environment variable (can be used multiple times)
    -w, --wait      Time to wait for services to start (default: 5s)
    --tag           Run only tests with specific tag (can be used multiple times)
    --fail-fast     Stop on first test failure
    -v, --verbose   Show detailed output
    -k, --keep      Keep containers running after tests
    --log-dir       Directory for saving detailed test logs
    --console-log-level  Console log level (INFO or DEBUG, default: INFO)
    --no-container-logs  Disable interleaving container logs in output
    -h, --help      Show this help message

Examples:
    # Run all tests in a directory
    $0 --image my-function:latest --tests ./tests

    # Run a specific test file
    $0 --image my-function:latest --tests ./tests/integration.yaml

    # Run only yaml files matching pattern
    $0 -i my-function:latest -t ./tests -p "integration-*.yaml"

    # Run only tests tagged as "smoke"
    $0 -i my-function:latest -t ./tests --tag smoke

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
        --tag)
            TAGS+=("$2")
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
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        --console-log-level)
            CONSOLE_LOG_LEVEL="$2"
            shift 2
            ;;
        --no-container-logs)
            NO_CONTAINER_LOGS=true
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

# Create docker-compose override for test framework v4
COMPOSE_DIR="test-framework-v4"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.test.yml"

# Check if test framework v4 is built
if ! docker images | grep -q "sdv-test-framework-v4"; then
    print_error "Test framework v4 not found. Please run ./build-test-framework.sh first"
    exit 1
fi

# Track test results
TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0
RESULTS_ROOT="test-results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_ROOT"

# Set up cleanup function
cleanup() {
    print_info "Cleaning up..."
    
    # Stop and remove the test subject container
    if [ "$KEEP_RUNNING" != "true" ]; then
        if docker ps -a | grep -q "$CONTAINER_NAME"; then
            print_info "Stopping container: $CONTAINER_NAME"
            docker stop "$CONTAINER_NAME" 2>/dev/null || true
            docker rm "$CONTAINER_NAME" 2>/dev/null || true
        fi
        
        # Stop test framework services
        cd "$COMPOSE_DIR"
        docker-compose -f docker-compose.test.yml down 2>/dev/null || true
        cd - > /dev/null
    else
        print_info "Keeping containers running (--keep flag was set)"
        print_info "To clean up manually, run:"
        print_info "  docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
        print_info "  cd $COMPOSE_DIR && docker-compose -f docker-compose.test.yml down"
    fi
}

# Register cleanup on exit
trap cleanup EXIT INT TERM

# Start KUKSA databroker using test framework v4 compose
print_info "Starting KUKSA databroker (test framework v4)..."
cd "$COMPOSE_DIR"
docker-compose -f docker-compose.test.yml up -d databroker
cd - > /dev/null

# Wait for databroker to be ready
print_info "Waiting for KUKSA databroker to be ready..."
for i in $(seq 1 20); do
    if nc -z localhost 55556 2>/dev/null; then
        print_info "KUKSA databroker is ready"
        break
    fi
    if [ $i -eq 20 ]; then
        print_error "KUKSA databroker failed to start"
        cd "$COMPOSE_DIR"
        docker-compose -f docker-compose.test.yml logs databroker
        cd - > /dev/null
        exit 1
    fi
    sleep 1
done

# Get the network name created by docker-compose
NETWORK_NAME=$(cd "$COMPOSE_DIR" && docker-compose -f docker-compose.test.yml ps -q databroker | xargs docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' | head -1)
NETWORK_NAME=$(docker network inspect "$NETWORK_NAME" -f '{{.Name}}' 2>/dev/null || echo "test-framework-v4_default")

print_info "Using network: $NETWORK_NAME"

# Start the user function container
print_info "Starting container: $CONTAINER_NAME"
print_info "Using image: $DOCKER_IMAGE"

# Build docker run command
DOCKER_RUN_CMD=(
    docker run -d
    --name "$CONTAINER_NAME"
    --network "$NETWORK_NAME"
    -e KUKSA_ADDRESS=databroker
    -e KUKSA_PORT=55555
    -e KUKSA_TLS=false
)

# Pass log level to container if specified
if [ -n "$CONSOLE_LOG_LEVEL" ]; then
    DOCKER_RUN_CMD+=(-e "LOG_LEVEL=$CONSOLE_LOG_LEVEL")
fi

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
    results_dir="$RESULTS_ROOT/$test_name"
    mkdir -p "$results_dir"
    
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    print_info "Running test suite: $test_file"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    # Build test framework command using new CLI
    TEST_FRAMEWORK_CMD=(
        docker run --rm
        --network "$NETWORK_NAME"
        -v "$(realpath "$test_file"):/app/test-suite.yaml:ro"
        -v "$(realpath "$results_dir"):/app/results"
        -v /var/run/docker.sock:/var/run/docker.sock:ro
        -e CONTAINER_NAME="$CONTAINER_NAME"
        sdv-test-framework-v4:latest
        python -m kuksa_test.cli
        /app/test-suite.yaml
        --kuksa-url databroker:55555
        --format json
        --output /app/results/test-report.json
    )
    
    # Add verbose flag if needed
    if [ "$VERBOSE" = true ]; then
        TEST_FRAMEWORK_CMD+=(--verbose)
    fi
    
    # Add logging options
    if [ -n "$LOG_DIR" ]; then
        TEST_FRAMEWORK_CMD+=(--log-dir "/app/logs")
        # Mount the log directory
        TEST_FRAMEWORK_CMD=("${TEST_FRAMEWORK_CMD[@]:0:7}" -v "$(realpath "$LOG_DIR"):/app/logs" "${TEST_FRAMEWORK_CMD[@]:7}")
    fi
    
    if [ -n "$CONSOLE_LOG_LEVEL" ]; then
        TEST_FRAMEWORK_CMD+=(--console-log-level "$CONSOLE_LOG_LEVEL")
    fi
    
    if [ "$NO_CONTAINER_LOGS" = true ]; then
        TEST_FRAMEWORK_CMD+=(--no-container-logs)
    fi
    
    # Run the test
    "${TEST_FRAMEWORK_CMD[@]}"
    TEST_EXIT_CODE=$?
    
    # Build console output command
    CONSOLE_CMD=(
        docker run --rm
        --network "$NETWORK_NAME"
        -v "$(realpath "$test_file"):/app/test-suite.yaml:ro"
        -v "$(realpath "$results_dir"):/app/results"
        -v /var/run/docker.sock:/var/run/docker.sock:ro
        -e CONTAINER_NAME="$CONTAINER_NAME"
    )
    
    # Add log directory mount if specified
    if [ -n "$LOG_DIR" ]; then
        CONSOLE_CMD+=(-v "$(realpath "$LOG_DIR"):/app/logs")
    fi
    
    CONSOLE_CMD+=(
        sdv-test-framework-v4:latest
        python -m kuksa_test.cli
        /app/test-suite.yaml
        --kuksa-url databroker:55555
        --format console
    )
    
    # Add logging options
    if [ -n "$LOG_DIR" ]; then
        CONSOLE_CMD+=(--log-dir "/app/logs")
    fi
    
    if [ -n "$CONSOLE_LOG_LEVEL" ]; then
        CONSOLE_CMD+=(--console-log-level "$CONSOLE_LOG_LEVEL")
    fi
    
    if [ "$NO_CONTAINER_LOGS" = true ]; then
        CONSOLE_CMD+=(--no-container-logs)
    fi
    
    # Generate console output for immediate feedback
    "${CONSOLE_CMD[@]}"
    
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

# Show container logs once at the end
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
print_info "Container logs (last 50 lines):"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
docker logs "$CONTAINER_NAME" 2>&1 | tail -50

# Summary report
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    TEST SUMMARY                            ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "Image tested:    $DOCKER_IMAGE"
echo -e "Test path:       $TEST_PATH"
if [ -d "$TEST_PATH" ]; then
    echo -e "Test pattern:    $TEST_PATTERN"
fi
if [ ${#TAGS[@]} -gt 0 ]; then
    echo -e "Tags filtered:   ${TAGS[*]}"
fi
echo -e "Total suites:    ${BLUE}$TOTAL_SUITES${NC}"
echo -e "Passed:          ${GREEN}$PASSED_SUITES${NC}"
echo -e "Failed:          ${RED}$FAILED_SUITES${NC}"
echo -e "Results saved:   $RESULTS_ROOT"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Create summary report
cat > "$RESULTS_ROOT/summary.json" <<EOF
{
  "image": "$DOCKER_IMAGE",
  "test_path": "$TEST_PATH",
  "total_suites": $TOTAL_SUITES,
  "passed_suites": $PASSED_SUITES,
  "failed_suites": $FAILED_SUITES,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "framework_version": "v4",
  "suites": [
EOF

# Add individual suite results
first=true
for test_file in "${TEST_FILES[@]}"; do
    test_name=$(basename "$test_file" .yaml)
    report_file="$RESULTS_ROOT/$test_name/test-report.json"
    if [ -f "$report_file" ]; then
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$RESULTS_ROOT/summary.json"
        fi
        echo -n "    {\"name\": \"$test_name\", \"file\": \"$test_file\", \"report\": \"$test_name/test-report.json\"}" >> "$RESULTS_ROOT/summary.json"
    fi
done

cat >> "$RESULTS_ROOT/summary.json" <<EOF

  ]
}
EOF

# Exit with appropriate code
if [ $FAILED_SUITES -eq 0 ]; then
    print_info "🎉 All test suites passed!"
    exit 0
else
    print_error "💥 $FAILED_SUITES test suite(s) failed!"
    exit 1
fi