#!/bin/bash
set -e

echo "Building fixture runner..."
cd "$(dirname "$0")/.."
docker build -t sdv-fixture-runner:latest -f fixture-runner/Dockerfile .
echo "Fixture runner built: sdv-fixture-runner:latest"
