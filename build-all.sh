#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}▶ $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_section "Building all SDV components"

# Build base images
print_info "Building base images..."
./build-base-images.sh

# Build test framework v1 (existing)
print_section "Building test framework v1"
cd test-framework
docker build -t sdv-test-framework:latest .
cd ..
print_info "Test framework v1 built successfully"

# Build test framework v4 (new)
print_section "Building test framework v4"
./build-test-framework.sh

# Build example applications
print_section "Building example applications"
./build-examples.sh

# Summary
print_section "Build Summary"
echo "Base images:"
docker images | grep -E "(sdv-.*-(build|runtime)|REPOSITORY)" | head -7
echo ""
echo "Test frameworks:"
docker images | grep -E "(test-framework|REPOSITORY)" | head -4
echo ""
echo "Example applications:"
docker images | grep -E "(sdv-(speed|engine)-monitor|REPOSITORY)" | head -4

print_info "All components built successfully!"