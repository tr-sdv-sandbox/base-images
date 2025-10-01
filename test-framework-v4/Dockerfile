FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI for log capture
RUN curl -fsSL https://get.docker.com | sh - && \
    apt-get purge -y docker-ce docker-ce-cli && \
    apt-get install -y docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Copy framework files
COPY requirements.txt .
COPY setup.py .
COPY kuksa_test/ ./kuksa_test/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# Copy examples
COPY examples/ ./examples/

# Default command
CMD ["python", "-m", "kuksa_test.cli", "--help"]