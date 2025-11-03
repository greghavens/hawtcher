#!/bin/bash
# Setup script for Hawtcher

set -e

echo "Setting up Hawtcher - Claude Code Monitoring Agent"
echo "=================================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Error: Python 3 not found. Please install Python 3.11+"; exit 1; }
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo ""

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo ".env file created - please review and update settings"
else
    echo ".env file already exists"
fi
echo ""

echo "=================================================="
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Review and update .env file with your settings"
echo "3. Start LM Studio and load the devstral model"
echo "4. Run: python hawtcher.py"
echo ""
echo "For more information, see README.md"
