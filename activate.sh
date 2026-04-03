#!/bin/bash
# Quick activation script for the virtual environment

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
    echo "Virtual environment created!"
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "✓ Virtual environment is now active!"
echo "  To deactivate, run: deactivate"
echo ""
echo "  Quick commands:"
echo "    python main.py --fixture fixtures/mr_artifacts.json --members ana bruno carla diego --deadline 2024-11-29T23:59:00Z"
echo "    pytest tests/ -v"
echo ""
