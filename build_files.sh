#!/bin/bash

# Exit on any error
set -e

echo "Building the project..."

# Install dependencies using a virtual environment to avoid "externally-managed-environment" error
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Make Migration..."
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput


echo "Collect Static..."
python3 manage.py collectstatic --noinput --clear

