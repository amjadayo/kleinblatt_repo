#!/bin/bash

# Script to update Kleinblatt to the latest version

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Updating Kleinblatt..."

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: Git is not installed. Please install git to enable automatic updates."
    exit 1
fi

# Check if this is a git repository
if [ ! -d ".git" ]; then
    echo "Error: This doesn't appear to be a git repository."
    echo "Please clone the repository using: git clone https://github.com/GingerApe/kleinblatt.git"
    exit 1
fi

# Fetch the latest changes
echo "Fetching latest changes..."
git fetch origin

# Get the current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Get the latest commit from the remote branch
LATEST_COMMIT=$(git rev-parse origin/$CURRENT_BRANCH)

# Get the current commit
CURRENT_COMMIT=$(git rev-parse HEAD)

# Check if we need to update
if [ "$LATEST_COMMIT" = "$CURRENT_COMMIT" ]; then
    echo "Already up to date!"
    exit 0
fi

# Pull the latest changes
echo "Pulling latest changes..."
git pull origin $CURRENT_BRANCH

# Make sure the launcher script is executable
chmod +x "$SCRIPT_DIR/launch_kleinblatt.sh"

echo "Update completed successfully!"
exit 0
