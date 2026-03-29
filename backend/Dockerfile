# Use a lightweight Python 3.10 image
FROM python:3.10-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app

# Set the working directory
WORKDIR $APP_HOME

# Install system dependencies required for gcc and scientific packages
# libgomp1 is needed for some scikit-learn/lightgbm features
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy local code to the container image
COPY . ./

# Install Python dependencies
# Using --no-cache-dir to keep image size down
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port defined by Cloud Run (default 8080)
ENV PORT=8080

# Run the web service on container startup using gunicorn with uvicorn workers
# Timeout set to 0 to allow Cloud Run to handle timeouts
# Lists files in /app to Cloud Run logs before starting
CMD ls -la /app && exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 -k uvicorn.workers.UvicornWorker main:app