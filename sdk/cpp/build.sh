#!/bin/bash
# Build script for SDV State Machine C++ SDK

set -e

# Default build type
BUILD_TYPE=${BUILD_TYPE:-Release}
BUILD_DIR=${BUILD_DIR:-build}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            BUILD_TYPE=Debug
            shift
            ;;
        --release)
            BUILD_TYPE=Release
            shift
            ;;
        --clean)
            echo "Cleaning build directory..."
            rm -rf "$BUILD_DIR"
            shift
            ;;
        --tests)
            RUN_TESTS=1
            shift
            ;;
        --examples)
            RUN_EXAMPLES=1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--debug|--release] [--clean] [--tests] [--examples]"
            exit 1
            ;;
    esac
done

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure
echo "Configuring CMake (Build type: $BUILD_TYPE)..."
cmake .. \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    -DBUILD_EXAMPLES=ON \
    -DBUILD_TESTS=ON \
    -DWITH_PROMETHEUS=OFF \
    -DWITH_KUKSA=OFF

# Build
echo "Building..."
make -j$(nproc)

# Run tests if requested
if [ "$RUN_TESTS" = "1" ]; then
    echo "Running tests..."
    ctest --output-on-failure
fi

# Run examples if requested
if [ "$RUN_EXAMPLES" = "1" ]; then
    echo "Running examples..."
    echo "=== Door Example ==="
    ./examples/door_example
    echo ""
    echo "=== Vehicle Example ==="
    ./examples/vehicle_example
fi

echo "Build complete!"