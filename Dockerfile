# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway will override with $PORT)
EXPOSE 8080

# Start command (Railway will set $PORT environment variable)
# Use shell form to allow environment variable expansion
CMD ["sh", "-c", "python3 scripts/api-server-v2.py --production --port ${PORT:-8080}"]
