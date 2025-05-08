# Kleinblatt App Launcher

This folder contains files to create a double-clickable app for launching Kleinblatt.

## Files
- `launch_kleinblatt.sh` - Shell script that sets up the environment and launches the application
- `Kleinblatt.applescript` - AppleScript to run the shell script in a Terminal window

## Creating a Double-Clickable App

Follow these steps to create a double-clickable app:

1. Open `Script Editor` on your Mac (you can find it using Spotlight or in the Applications/Utilities folder)
2. Open the `Kleinblatt.applescript` file
3. Go to `File → Export...` in the menu
4. Set the following options:
   - File Format: `Application`
   - Options: Check `Run Only` and `Stay Open`
   - Save the file as `Kleinblatt.app` in your desired location

## Features

- Automatically checks for and pulls the latest version from Git if available
- Sets up or activates the Python virtual environment
- Installs required dependencies if needed
- Launches the Kleinblatt application

## Usage

1. Double-click the `Kleinblatt.app` to launch the application
2. A Terminal window will open, showing the progress of the launch
3. The application will start automatically once the environment is ready

## Troubleshooting

If you encounter any issues:

1. Check that both scripts (`launch_kleinblatt.sh` and `Kleinblatt.applescript`) are in the same folder
2. Make sure `launch_kleinblatt.sh` is executable (run `chmod +x launch_kleinblatt.sh` in Terminal)
3. If git update is failing, try running `git pull` manually in the project directory
4. If dependency installation fails, try running `pip install -r requirements.txt` manually 