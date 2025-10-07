# C++ base image for SDV user functions
# Optimized for small size with gRPC/protobuf support for KUKSA.val

FROM debian:bookworm-slim AS builder

# Install build tools and dependencies
RUN apt-get update && apt-get install -y \
    g++ \
    cmake \
    make \
    git \
    ca-certificates \
    libssl-dev \
    libprotobuf-dev \
    protobuf-compiler \
    libgrpc++-dev \
    libgrpc-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download KUKSA.val proto files with proper directory structure
WORKDIR /proto
RUN mkdir -p kuksa/val/v1 && \
    curl -sSL https://raw.githubusercontent.com/eclipse/kuksa.val/0.4.1/proto/kuksa/val/v1/types.proto -o kuksa/val/v1/types.proto && \
    curl -sSL https://raw.githubusercontent.com/eclipse/kuksa.val/0.4.1/proto/kuksa/val/v1/val.proto -o kuksa/val/v1/val.proto

# Final stage - minimal runtime image
FROM debian:bookworm-slim

# Install runtime dependencies and development headers
RUN apt-get update && apt-get install -y \
    g++ \
    cmake \
    make \
    libssl-dev \
    libprotobuf-dev \
    protobuf-compiler \
    protobuf-compiler-grpc \
    libgrpc++-dev \
    libgrpc-dev \
    libgoogle-glog-dev \
    libgtest-dev \
    libyaml-cpp-dev \
    pkg-config \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy proto files from builder with directory structure
COPY --from=builder /proto/kuksa /usr/local/include/kuksa

# Copy and build SDK
COPY --from=src ./cpp /tmp/sdk-build
RUN cd /tmp/sdk-build && \
    mkdir -p build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release \
          -DBUILD_EXAMPLES=OFF \
          -DBUILD_TESTS=OFF \
          -DCMAKE_INSTALL_PREFIX=/usr/local \
          .. && \
    make -j$(nproc) && \
    make install && \
    cd / && rm -rf /tmp/sdk-build

# Set environment variables
ENV KUKSA_ADDRESS="kuksa-val-server" \
    KUKSA_PORT="8090" \
    KUKSA_PROTOCOL="grpc" \
    KUKSA_TLS="false"

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash sdvuser

# Create app directory
WORKDIR /app
RUN chown sdvuser:sdvuser /app

# Switch to non-root user
USER sdvuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD protoc --version || exit 1

# Default command (to be overridden by user functions)
CMD ["/bin/bash"]
