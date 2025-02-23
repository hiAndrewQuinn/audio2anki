FROM python:3.11-slim

# Install system dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the repository files into the container.
COPY . /app

# Install latest yt-dlp binary.
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp

# Install latest OpenAI Whisper.
RUN pip install git+https://github.com/openai/whisper.git

# Upgrade pip and install Python dependencies directly.
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Declare volumes for directories that will contain generated files.
VOLUME ["/app/clips", "/app/transcripts", "/app/youtube"]

# Set the entrypoint to run your CLI program.
ENTRYPOINT ["python", "main.py"]

