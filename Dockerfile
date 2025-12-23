# Builder stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for building lxml
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies to a temporary location
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install only runtime dependencies for lxml
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY app.py .

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000

# Add healthcheck using Python (no curl needed)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"FLASK_PORT\", \"5000\")}/health')" || exit 1

# Run the application
CMD ["python", "app.py"]
