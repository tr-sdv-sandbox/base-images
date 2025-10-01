#!/bin/bash
set -e

# Build base images first if they don't exist
check_base_images() {
    if ! docker image inspect sdv-cpp-runtime:latest >/dev/null 2>&1 || \
       ! docker image inspect sdv-cpp-alpine-runtime:latest >/dev/null 2>&1 || \
       ! docker image inspect sdv-python-runtime:latest >/dev/null 2>&1; then
        echo "Base runtime images not found. Building them first..."
        ./build-base-images.sh
    fi
}

echo "Building SDV example user functions..."
check_base_images

# Build Python speed monitor
echo ""
echo "Building Python speed monitor..."
cd examples/python-speed-monitor
docker build -t sdv-python-speed-monitor:latest .
cd ../..

# Build C++ engine monitor (Debian)
echo ""
echo "Building C++ engine monitor (Debian)..."
cd examples/cpp-engine-monitor
docker build -t sdv-cpp-engine-monitor:latest .
cd ../..

# Build C++ engine monitor (Alpine)
echo ""
echo "Building C++ engine monitor (Alpine)..."
cd examples/cpp-engine-monitor
docker build -f Dockerfile.alpine -t sdv-cpp-engine-monitor:alpine .
cd ../..

echo ""
echo "Example images built successfully!"
echo ""
echo "Example images:"
docker images | grep -E "(sdv-(cpp-engine|python-speed)-monitor|REPOSITORY)" | head -5

echo ""
echo "Image sizes comparison:"
echo "Debian-based C++ image: $(docker images sdv-cpp-engine-monitor:latest --format "{{.Size}}")"
echo "Alpine-based C++ image: $(docker images sdv-cpp-engine-monitor:alpine --format "{{.Size}}")"
echo "Python image: $(docker images sdv-python-speed-monitor:latest --format "{{.Size}}")"