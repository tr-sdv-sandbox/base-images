#!/bin/bash
set -e

echo "Building SDV Test Framework v4..."

cd test-framework-v4
docker build -t sdv-test-framework-v4:latest .
cd ..

echo ""
echo "Test framework built successfully!"
echo ""
echo "Test framework images:"
docker images | grep -E "(sdv-test-framework-v4|REPOSITORY)" | head -2