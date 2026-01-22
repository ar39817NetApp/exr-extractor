FROM python:3.11-slim

# Install system dependencies required for OpenEXR and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenexr-dev \
    libilmbase-dev \
    pkg-config \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from requirements; copying only requirements first
# helps layer caching during iterative development.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# Copy project files
COPY . /app

# Expose gRPC port
EXPOSE 50051

ENV PYTHONPATH=/app

CMD ["python", "-m", "server.main"]