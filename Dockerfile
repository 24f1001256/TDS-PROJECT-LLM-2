# Use a specific Debian-based Python image for reproducibility
FROM python:3.11-slim-bookworm

# Set environment variables to prevent Python from writing .pyc files and to run in unbuffered mode
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for Google Chrome, utilities, jq for parsing JSON, and ffmpeg for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    jq \
    ffmpeg \
    # Cleanup apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Add Google's official GPG key and Chrome repository to the system's sources
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# Install the latest stable version of Google Chrome
RUN apt-get update && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install the latest stable version of ChromeDriver using the official JSON endpoints
RUN CD_URL=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | jq -r '.channels.Stable.downloads.chromedriver[] | select(.platform=="linux64") | .url') \
    && wget -q --continue -P /tmp $CD_URL \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin \
    # The zip archive contains a directory, so move the binary to the final location
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    # Clean up the downloaded zip and extracted directory
    && rm /tmp/chromedriver-linux64.zip \
    && rm -rf /usr/local/bin/chromedriver-linux64

# Copy the requirements.txt file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port that Gunicorn will run on
EXPOSE 8080

# Set the command to run the application using Gunicorn
# This is a production-ready WSGI server
CMD ["gunicorn", "--bind", "0.-", "main:app"]
