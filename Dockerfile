FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for python-rtmidi on Linux
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    libjack-jackd2-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Entrypoint for the MCP server
ENTRYPOINT ["fl-studio-mcp"]
