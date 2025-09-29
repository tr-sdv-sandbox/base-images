# Minimal C++ runtime image for SDV user functions
# Contains only runtime dependencies for KUKSA.val gRPC communication

FROM debian:bookworm-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    libprotobuf32 \
    libgrpc++1.51 \
    libgoogle-glog0v6 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/share/doc/* \
    && rm -rf /usr/share/man/* \
    && rm -rf /usr/share/locale/* \
    && find /var/log -type f -delete

# Create non-root user
RUN useradd -m -u 1000 -s /bin/false sdvuser

# Set working directory
WORKDIR /app

# Switch to non-root user
USER sdvuser

# Set default environment variables for KUKSA connection
ENV KUKSA_ADDRESS=kuksa-databroker \
    KUKSA_PORT=55555

# Default command (to be overridden by user functions)
CMD ["/bin/sh"]