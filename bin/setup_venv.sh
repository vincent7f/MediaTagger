#!/bin/bash
# Setup virtual environment with tkinter support and install requirements
# Usage: ./bin/setup_venv.sh

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the parent directory (project root)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root directory
cd "$PROJECT_ROOT" || exit 1

echo "Setting up virtual environment with tkinter support..."
echo "Project root: $PROJECT_ROOT"
echo ""

# Find a Python interpreter that supports tkinter
PYTHON_CMD=""
PYTHON_VERSION=""

echo "Searching for Python with tkinter support..."

# Try common Python paths in order of preference (prefer Python 3.12+)
for py_cmd in /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 python3.12 /usr/bin/python3 python3 /Library/Frameworks/Python.framework/Versions/*/bin/python3 python; do
    if command -v "$py_cmd" >/dev/null 2>&1; then
        # Check if this Python has tkinter
        if "$py_cmd" -c "import tkinter" >/dev/null 2>&1; then
            PYTHON_CMD="$py_cmd"
            PYTHON_VERSION=$("$py_cmd" --version 2>&1)
            echo "Found Python with tkinter: $PYTHON_CMD ($PYTHON_VERSION)"
            break
        fi
    fi
done

# If no Python with tkinter found, exit with error
if [ -z "$PYTHON_CMD" ]; then
    echo "Error: No Python interpreter with tkinter support found!"
    echo ""
    echo "Please install Python with tkinter support:"
    echo "  - On macOS: Use system Python (/usr/bin/python3) or install Python from python.org"
    echo "  - Note: Homebrew Python may not include tkinter by default"
    echo ""
    exit 1
fi

# Remove existing venv if it exists
if [ -d "venv" ]; then
    echo ""
    echo "Removing existing venv directory..."
    rm -rf venv
fi

# Create new virtual environment
echo ""
echo "Creating virtual environment with $PYTHON_CMD..."
"$PYTHON_CMD" -m venv venv

# Verify venv was created successfully
if [ ! -f "venv/bin/activate" ]; then
    echo "Error: Failed to create virtual environment!"
    exit 1
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install requirements
if [ -f "requirements.txt" ]; then
    echo ""
    echo "Installing requirements from requirements.txt..."
    pip install -r requirements.txt
    echo ""
    echo "Successfully installed all requirements!"
else
    echo ""
    echo "Warning: requirements.txt not found, skipping dependency installation."
fi

# Verify tkinter is still available in venv
echo ""
echo "Verifying tkinter availability in venv..."
if venv/bin/python3 -c "import tkinter; print('✓ tkinter is available')" 2>/dev/null; then
    echo "✓ Virtual environment setup completed successfully!"
    echo ""
    echo "To activate the virtual environment, run:"
    echo "  source venv/bin/activate"
    echo ""
    echo "To run the dataset manager, use:"
    echo "  ./bin/dataset_manager.sh"
    echo ""
else
    echo "Warning: tkinter is not available in the new virtual environment."
    echo "This may cause issues when running the application."
    echo ""
    exit 1
fi
