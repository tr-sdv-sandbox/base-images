# Minimal Python runtime image for SDV user functions
# Contains Python and KUKSA client dependencies

FROM python:3.11-slim

# Install KUKSA Python client
RUN pip install --no-cache-dir kuksa-client>=0.4.0 grpcio>=1.54.0

# Create non-root user
RUN useradd -m -u 1000 -s /bin/false sdvuser

# Set working directory
WORKDIR /app

# Switch to non-root user
USER sdvuser

# Set default environment variables for KUKSA connection
ENV KUKSA_ADDRESS=kuksa-databroker \
    KUKSA_PORT=55555 \
    PYTHONUNBUFFERED=1

# Default command
CMD ["python"]