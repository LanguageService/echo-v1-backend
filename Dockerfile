# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to prevent generating .pyc files and to run Python unbuffered
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set PYTHONPATH to include the project directory
ENV PYTHONPATH /app

# Set the working directory in the container
WORKDIR /app

# Install uv, the fast Python package installer
RUN pip install uv

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the entrypoint script
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy the rest of the application's code into the container
COPY . .

# Run the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
