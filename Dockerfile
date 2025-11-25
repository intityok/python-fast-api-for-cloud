# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run sets PORT environment variable, default to 8080
ENV PORT=8080

# Expose port (documentation only, Cloud Run ignores this)
EXPOSE 8080

# Run the application
# Use PORT environment variable from Cloud Run
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
