FROM python:3.11-slim

# Install system dependencies including ffmpeg for audio/video stream processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Set environment
ENV TORTUGA_HOST=0.0.0.0
ENV TORTUGA_PORT=5000
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Run entrypoint script (bot in background + web server)
CMD ["sh", "entrypoint.sh"]
