# Alpine-based C++ development image for building minimal SDV applications
FROM alpine:3.18

# Install build dependencies and development tools
RUN apk add --no-cache \
    # Build essentials
    build-base \
    cmake \
    ninja \
    pkgconf \
    # gRPC and protobuf
    grpc-cpp \
    grpc-dev \
    protobuf-dev \
    # Logging
    glog-dev \
    # SSL/TLS
    openssl-dev \
    # JSON handling
    nlohmann-json \
    # Git for fetching dependencies
    git \
    # Additional useful tools
    gdb \
    valgrind \
    strace \
    # Required for some builds
    linux-headers \
    # For downloading files
    curl

# Set up pkg-config path
ENV PKG_CONFIG_PATH=/usr/lib/pkgconfig:/usr/local/lib/pkgconfig

# Download KUKSA.val proto files with proper directory structure
WORKDIR /tmp
RUN mkdir -p /usr/local/include/kuksa/val/v1 && \
    curl -sSL https://raw.githubusercontent.com/eclipse/kuksa.val/0.4.1/proto/kuksa/val/v1/types.proto -o /usr/local/include/kuksa/val/v1/types.proto && \
    curl -sSL https://raw.githubusercontent.com/eclipse/kuksa.val/0.4.1/proto/kuksa/val/v1/val.proto -o /usr/local/include/kuksa/val/v1/val.proto

# Create a non-root user for development
RUN adduser -D -u 1000 -s /bin/sh developer

# Set working directory
WORKDIR /workspace

# Default to non-root user
USER developer

# Set default command
CMD ["/bin/sh"]