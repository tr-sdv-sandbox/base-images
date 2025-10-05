#!/bin/bash
set -e

echo "Building climate control application..."
cd "$(dirname "$0")/../.."
docker build -t sdv-cpp-climate-control:latest -f examples/cpp-climate-control/Dockerfile.climate .
echo "Climate control built: sdv-cpp-climate-control:latest"
