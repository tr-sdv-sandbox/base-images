# Build stage - use the C++ build image with SDK pre-installed
FROM sdv-cpp-build:latest AS builder

# Copy fixture runner source
COPY fixture-runner /app/
WORKDIR /app

# Build the application (SDK is already installed in /usr/local)
RUN rm -rf build && mkdir -p build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    strip --strip-all fixture-runner

# Runtime stage - use minimal runtime base image
FROM sdv-cpp-runtime:latest

# Copy the stripped binary from builder
COPY --from=builder /app/build/fixture-runner /usr/local/bin/

# Run the fixture runner
CMD ["fixture-runner"]
