-- Kleinblatt Launcher

-- Get the path to the script directory
set scriptPath to do shell script "dirname " & quoted form of POSIX path of (path to me)

-- Path to the shell script
set launchScript to scriptPath & "/launch_kleinblatt.sh"

-- Create a new terminal window and run the script
tell application "Terminal"
    activate
    -- Create a new terminal window with a title
    do script "echo 'Launching Kleinblatt...'; bash \"" & launchScript & "\""
    set custom title of front window to "Kleinblatt"
end tell 