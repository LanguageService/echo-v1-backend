#!/bin/bash

# Exit on any error
set -e

echo "--- STARTING BUILD PROCESS ---"

# Install dependencies using a virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing requirements (this may take a few minutes)..."
pip install -r requirements.txt --no-cache-dir

echo "Checking environment variables..."
if [ -z "$DATABASE_URL" ]; then
    echo "WARNING: DATABASE_URL is not set. Migrations might fail if they require a DB connection."
fi

echo "Running: makemigrations..."
python3 manage.py makemigrations --noinput

echo "Running: migrate..."
# We use || true here to prevent build failure if DB is unreachable during build
python3 manage.py migrate --noinput || echo "Migration failed, but continuing build..."

echo "Running: collectstatic..."
python3 manage.py collectstatic --noinput --clear

echo "--- BUILD PROCESS FINISHED ---"
