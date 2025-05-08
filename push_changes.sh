#!/bin/bash

# Script to push all changes to the repository with a standard commit message

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Pushing changes to repository..."

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: Git is not installed."
    exit 1
fi

# Check if this is a git repository
if [ ! -d ".git" ]; then
    echo "Error: This doesn't appear to be a git repository."
    exit 1
fi

# Check if there are any changes to commit
if [ -z "$(git status --porcelain)" ]; then
    echo "No changes to commit."
    exit 0
fi

# Add all changes
echo "Adding all changes..."
git add .

# Commit changes with standard message
echo "Committing changes..."
git commit -m "Automatic upload"

# Push to remote repository
echo "Pushing to remote repository..."
git push origin $(git rev-parse --abbrev-ref HEAD)

echo "Changes pushed successfully!"
exit 0
