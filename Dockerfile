# Use a specific Debian-based Python image for reproducibility
FROM python:3.11-slim-bookworm

# Set environment variables to prevent Python from writing .pyc files and to run in unbuffered mode
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for Google Chrome and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    # Cleanup apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Add Google's official GPG key and Chrome repository to the system's sources
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

# Install the latest stable version of Google Chrome
RUN apt-get update && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install the matching version of ChromeDriver
# This command automatically finds the version of Chrome installed and downloads the corresponding ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | cut -d " " -f3) \
    && CD_VERSION=$(wget -qO- https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json | grep -A 20 "$CHROME_VERSION" | grep 'chromedriver' | grep 'linux64' | awk -F '"' '{print $4}') \
    && wget -q --continue -P /tmp $CD_VERSION \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin \
    && rm /tmp/chromedriver-linux64.zip

# Copy the requirements.txt file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port that Gunicorn will run on
EXPOSE 8080

# Set the command to run the application using Gunicorn
# This is a production-ready WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
