#!/bin/bash
set -e

echo "Building SDV base images..."

# Build images
echo "Building C++ build image (Debian)..."
docker build -f dockerfiles/build/cpp-build.Dockerfile -t sdv-cpp-build:latest .

echo "Building C++ build image (Alpine)..."
docker build -f dockerfiles/build/cpp-alpine-build.Dockerfile -t sdv-cpp-alpine-build:latest .

echo "Building C++ runtime image (Debian)..."
docker build -f dockerfiles/runtime/cpp-runtime.Dockerfile -t sdv-cpp-runtime:latest .

echo "Building C++ runtime image (Alpine)..."
docker build -f dockerfiles/runtime/cpp-alpine-runtime.Dockerfile -t sdv-cpp-alpine-runtime:latest .

echo "Building Python runtime image..."
docker build -f dockerfiles/runtime/python-runtime.Dockerfile -t sdv-python-runtime:latest .

echo "Base images built successfully!"
echo ""
echo "Build images (for compilation):"
docker images | grep -E "(sdv-.*-build|REPOSITORY)" | head -5
echo ""
echo "Runtime images (for deployment):"
docker images | grep -E "(sdv-.*-runtime|REPOSITORY)" | head -6