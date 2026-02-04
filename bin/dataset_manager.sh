#!/bin/bash
# Launch Dataset Video Manager GUI
# Usage: ./bin/dataset_manager.sh

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the parent directory (project root)
DIST_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root directory
cd "$DIST_ROOT" || exit 1

# Run the Python script
python src/run_dataset_manager.py

# Check exit status and show error message if failed
if [ $? -ne 0 ]; then
    echo "Install Python 3.9+ and optionally: pip install -r requirements.txt"
    exit 1
fi
