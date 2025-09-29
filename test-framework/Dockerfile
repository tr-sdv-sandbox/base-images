FROM python:3.11-slim-bookworm

# Install docker client for log capture
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install test framework dependencies
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy test framework
COPY test_runner.py /app/
COPY examples/ /app/examples/

# Create non-root user (but don't switch to it for docker access)
RUN useradd -m -u 1000 -s /bin/bash testuser && \
    chown -R testuser:testuser /app

# Run as root to access docker socket
# USER testuser

# Default entrypoint
ENTRYPOINT ["python", "test_runner.py"]
CMD ["--help"]