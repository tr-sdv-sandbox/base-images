#!/bin/bash
#
# Install development dependencies for SDV SDK and applications
#
# This script installs all required packages for building:
# - C++ SDK (state machine + VSS client)
# - Example applications (climate control, engine monitor, etc.)
#

set -e

echo "Installing SDV development dependencies..."

sudo apt-get update

sudo apt-get install -y \
    build-essential \
    cmake \
    g++ \
    libprotobuf-dev \
    protobuf-compiler \
    protobuf-compiler-grpc \
    libgrpc++-dev \
    libgrpc-dev \
    libgoogle-glog-dev \
    libyaml-cpp-dev \
    pkg-config \
    ca-certificates

echo ""
echo "✓ All dependencies installed successfully!"
echo ""
echo "You can now build the SDK and applications:"
echo "  cd examples/cpp-climate-control/build"
echo "  cmake .."
echo "  make"
