#!/bin/bash

# Exit on any error
set -e

echo "--- STARTING BUILD PROCESS ---"
echo "Current Directory: $(pwd)"

# Install dependencies using a virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing requirements..."
pip install -r requirements.txt --no-cache-dir

echo "Checking environment variables..."
if [ -z "$DATABASE_URL" ]; then
    echo "WARNING: DATABASE_URL is not set."
fi

echo "Running: makemigrations..."
python3 manage.py makemigrations --noinput

echo "Running: migrate..."
python3 manage.py migrate --noinput || echo "Migration failed, continuing build..."

echo "Running: collectstatic..."
python3 manage.py collectstatic --noinput --clear

echo "Verifying output directory..."
if [ -d "staticfiles_build" ]; then
    echo "SUCCESS: staticfiles_build directory exists."
    ls -ld staticfiles_build
else
    echo "ERROR: staticfiles_build directory NOT FOUND in $(pwd)"
    echo "Searching for staticfiles_build elsewhere..."
    find . -name "staticfiles_build" -type d
fi

echo "--- BUILD PROCESS FINISHED ---"
