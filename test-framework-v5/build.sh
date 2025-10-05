#!/bin/bash

set -e

IMAGE_NAME="test-framework-v5"
TAG="latest"

echo "Building test-framework-v5 Docker image..."

# Build from the base-images directory
cd "$(dirname "$0")/.."

# Copy SDK to test-framework-v5 for build
echo "Copying SDK source..."
rm -rf test-framework-v5/sdk
cp -r sdk/cpp test-framework-v5/sdk

# Exclude build artifacts
rm -rf test-framework-v5/sdk/build
rm -rf test-framework-v5/sdk/cmake-build-debug
rm -rf test-framework-v5/sdk/.idea

docker build \
    -f test-framework-v5/Dockerfile \
    -t ${IMAGE_NAME}:${TAG} \
    .

# Clean up SDK copy
rm -rf test-framework-v5/sdk

echo "Successfully built ${IMAGE_NAME}:${TAG}"
