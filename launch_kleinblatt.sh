#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the application directory
cd "$SCRIPT_DIR"

# Check if this is a git repository
if [ -d ".git" ]; then
    echo "Checking for updates..."
    # Pull the latest changes from the repository
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null
    
    # Check if the pull was successful
    if [ $? -eq 0 ]; then
        echo "Successfully updated to the latest version!"
    else
        echo "Could not update automatically. Please update manually."
    fi
fi

# Check if a virtual environment exists
if [ -d "kb" ]; then
    # Activate the virtual environment
    source /Applications/Logistik_App/kleinblatt/kb/bin/activate
    
    # Install requirements
    python3 -m pip install -r /Applications/Logistik_App/kleinblatt/requirements.txt
fi

# Launch the application
python3 /Applications/Logistik_App/kleinblatt/main.py 