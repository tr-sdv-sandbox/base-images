# Build stage - use the C++ build image with all dev tools
FROM sdv-cpp-build:latest AS builder

# Copy source files
COPY . /app/
WORKDIR /app

# Build the application
RUN mkdir -p build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    strip --strip-all engine_monitor

# Runtime stage - use minimal runtime base image
FROM sdv-cpp-runtime:latest

# Copy the stripped binary from builder
COPY --from=builder /app/build/engine_monitor /usr/local/bin/

# Set application-specific environment variables
ENV RPM_LIMIT=4500 \
    TEMP_LIMIT=105.0

# Run the engine monitor
CMD ["engine_monitor"]