#!/bin/bash
# Run KUKSA Test Framework v4 tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}KUKSA Test Framework v4${NC}"
echo "========================="

# Default values
TEST_FILE=""
SPEC_FILE=""
FORMAT="console"
OUTPUT_DIR="./results"
KUKSA_URL="localhost:55556"
COMPOSE_FILE="docker-compose.yml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--test)
            TEST_FILE="$2"
            shift 2
            ;;
        -s|--spec)
            SPEC_FILE="$2"
            shift 2
            ;;
        -f|--format)
            FORMAT="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -k|--kuksa)
            KUKSA_URL="$2"
            shift 2
            ;;
        -c|--compose)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -t, --test FILE      Test suite file (required)"
            echo "  -s, --spec FILE      VFF specification file"
            echo "  -f, --format FORMAT  Report format (console|json|markdown|junit)"
            echo "  -o, --output DIR     Output directory for reports"
            echo "  -k, --kuksa URL      KUKSA databroker URL"
            echo "  -c, --compose FILE   Docker compose file"
            echo "  -h, --help           Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if test file is provided
if [ -z "$TEST_FILE" ]; then
    echo -e "${RED}Error: Test file is required${NC}"
    echo "Use -h for help"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Build the test framework image
echo -e "${YELLOW}Building test framework image...${NC}"
docker-compose -f "$COMPOSE_FILE" build test-runner

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose -f "$COMPOSE_FILE" up -d databroker

# Wait for databroker to be ready
echo -e "${YELLOW}Waiting for KUKSA databroker...${NC}"
sleep 5

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Build command
CMD="python -m kuksa_test.cli /app/${TEST_FILE} --kuksa-url databroker:55555"

if [ ! -z "$SPEC_FILE" ]; then
    CMD="$CMD --spec /app/${SPEC_FILE}"
fi

# Add output file based on format
case $FORMAT in
    json)
        OUTPUT_FILE="/app/results/report_${TIMESTAMP}.json"
        ;;
    markdown)
        OUTPUT_FILE="/app/results/report_${TIMESTAMP}.md"
        ;;
    junit)
        OUTPUT_FILE="/app/results/report_${TIMESTAMP}.xml"
        ;;
    *)
        OUTPUT_FILE=""
        ;;
esac

if [ ! -z "$OUTPUT_FILE" ]; then
    CMD="$CMD --format $FORMAT --output $OUTPUT_FILE"
else
    CMD="$CMD --format console"
fi

# Run the test container
docker-compose -f "$COMPOSE_FILE" run --rm \
    -v "$(pwd):/app/tests" \
    -v "$(pwd)/$OUTPUT_DIR:/app/results" \
    test-runner $CMD

EXIT_CODE=$?

# Show results
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Some tests failed!${NC}"
fi

# Cleanup
echo -e "${YELLOW}Cleaning up...${NC}"
docker-compose -f "$COMPOSE_FILE" down

exit $EXIT_CODE