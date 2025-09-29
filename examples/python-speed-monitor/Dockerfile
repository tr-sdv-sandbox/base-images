FROM sdv-python-runtime:latest

# Switch to root to install additional dependencies if needed
USER root

# Copy application code and requirements
COPY speed_monitor.py /app/
COPY requirements.txt /app/

# Install additional dependencies if any are specified
RUN if [ -s /app/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/requirements.txt; \
    fi

# Switch back to non-root user
USER sdvuser

# Run the speed monitor
CMD ["python", "-u", "speed_monitor.py"]