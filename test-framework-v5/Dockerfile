# Build stage for test-framework-v5
FROM ubuntu:24.04 AS builder

# Install build tools and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    g++ \
    libgrpc++-dev \
    libprotobuf-dev \
    protobuf-compiler-grpc \
    libyaml-cpp-dev \
    libgoogle-glog-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /workspace

# Build SDK first
COPY test-framework-v5/sdk /workspace/sdk
WORKDIR /workspace/sdk/build
RUN cmake .. && make -j$(nproc) && make install

# Copy framework source
WORKDIR /workspace
COPY test-framework-v5 /workspace/test-framework-v5

# Build the framework
WORKDIR /workspace/test-framework-v5/build
RUN cmake .. && make -j$(nproc)

# Runtime stage
FROM ubuntu:24.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgrpc++1.51t64 \
    libprotobuf32t64 \
    libyaml-cpp0.8 \
    libgoogle-glog0v6t64 \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK libraries (statically linked, no .so needed)

# Copy the built executable
COPY --from=builder /workspace/test-framework-v5/build/test-framework-v5 /usr/local/bin/

# Set library path
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

# Set up test directory
WORKDIR /tests

ENTRYPOINT ["/usr/local/bin/test-framework-v5"]
