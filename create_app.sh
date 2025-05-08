#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Extract version from main.py
VERSION=$(grep "VERSION =" "$SCRIPT_DIR/main.py" | sed 's/VERSION = "\(.*\)"/\1/')
echo "Creating Kleinblatt app version $VERSION"

# Make sure the launch script is executable
chmod +x "$SCRIPT_DIR/launch_kleinblatt.sh"
chmod +x "$SCRIPT_DIR/update_kleinblatt.sh"

# Create a temporary directory for our app
TEMP_DIR=$(mktemp -d)

# Create the app structure
mkdir -p "$TEMP_DIR/Kleinblatt.app/Contents/MacOS"
mkdir -p "$TEMP_DIR/Kleinblatt.app/Contents/Resources"

# Create the Info.plist file
cat > "$TEMP_DIR/Kleinblatt.app/Contents/Info.plist" << EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>KleinblattLauncher</string>
	<key>CFBundleIconFile</key>
	<string>AppIcon</string>
	<key>CFBundleIdentifier</key>
	<string>com.gingerape.kleinblatt</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>Kleinblatt</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>$VERSION</string>
	<key>NSHighResolutionCapable</key>
	<true/>
</dict>
</plist>
EOL

# Create the launcher script
cat > "$TEMP_DIR/Kleinblatt.app/Contents/MacOS/KleinblattLauncher" << EOL
#!/bin/bash

# Path to original repository directory
REPO_DIR="$SCRIPT_DIR"

# Run the launch script in Terminal
osascript -e 'tell application "Terminal"
    activate
    do script "echo \"Launching Kleinblatt...\"; bash \"'$SCRIPT_DIR/launch_kleinblatt.sh'\""
    set custom title of front window to "Kleinblatt"
end tell'
EOL

# Make the launcher script executable
chmod +x "$TEMP_DIR/Kleinblatt.app/Contents/MacOS/KleinblattLauncher"

# Check if app already exists in current directory
if [ -d "$SCRIPT_DIR/Kleinblatt.app" ]; then
    echo "Removing existing Kleinblatt.app..."
    rm -rf "$SCRIPT_DIR/Kleinblatt.app"
fi

# Move the app to the original directory
mv "$TEMP_DIR/Kleinblatt.app" "$SCRIPT_DIR/"

# Clean up
rm -rf "$TEMP_DIR"

echo "Kleinblatt.app version $VERSION created successfully!"
echo "You can now double-click Kleinblatt.app to run the application." 