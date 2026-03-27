# Use Python 3.13 as specified in their conda instructions
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Install system dependencies (if any are needed for package building)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy the dependency files first to leverage Docker cache
COPY requirements.txt pyproject.toml ./

# Install the package and its dependencies
RUN pip install --no-cache-dir .

# Copy the rest of the application code
COPY . .

# Set default command (Running the CLI module directly)
CMD ["python", "-m", "cli.main"]