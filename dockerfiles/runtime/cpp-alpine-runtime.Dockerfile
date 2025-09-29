# Minimal Alpine C++ runtime image for SDV user functions
# Contains only runtime dependencies for KUKSA.val gRPC communication

FROM alpine:3.18

# Install only runtime dependencies
RUN apk add --no-cache \
    libstdc++ \
    libssl3 \
    libprotobuf \
    grpc-cpp \
    glog \
    ca-certificates

# Create non-root user
RUN adduser -D -u 1000 -s /bin/sh sdvuser

# Set working directory
WORKDIR /app

# Switch to non-root user
USER sdvuser

# Set default environment variables for KUKSA connection
ENV KUKSA_ADDRESS=kuksa-databroker \
    KUKSA_PORT=55555

# Default command
CMD ["/bin/sh"]