# ADAPT v3.0 Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install ADAPT in development mode
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 adapt && \
    chown -R adapt:adapt /app

USER adapt

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health').raise_for_status()"

# Run API server
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
