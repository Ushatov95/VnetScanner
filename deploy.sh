#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting custom deployment script."

# Define paths
PROJECT_DIR="/home/site/wwwroot"
PYTHON_PACKAGES_DIR="$PROJECT_DIR/.python_packages/lib/site-packages"
STARTUP_SCRIPT="$PROJECT_DIR/startup.sh"

# Ensure the .python_packages directory exists
mkdir -p $PYTHON_PACKAGES_DIR

# Install Python dependencies from requirements.txt
echo "Installing Python dependencies..."
/opt/python/3.10.4/bin/python3.10 -m pip install -r requirements.txt --target $PYTHON_PACKAGES_DIR
echo "Python dependencies installed."

# Find the az executable
AZ_CLI_PATH=$(find $PYTHON_PACKAGES_DIR -name az -type f -print -quit)

if [ -z "$AZ_CLI_PATH" ]; then
    echo "ERROR: az executable not found in installed packages. Deployment failed."
    exit 1
fi

# Get the directory containing the az executable
AZ_CLI_DIR=$(dirname "$AZ_CLI_PATH")
echo "Found Azure CLI at: $AZ_CLI_DIR"

# Create a startup script that will be sourced by the function runtime
echo "Creating startup script..."
cat > $STARTUP_SCRIPT << EOF
#!/bin/bash
# This script is sourced by the function runtime to set up the environment
export PATH="\$PATH:$AZ_CLI_DIR"
echo "Added Azure CLI to PATH: $AZ_CLI_DIR"
EOF

# Make the startup script executable
chmod +x $STARTUP_SCRIPT

# Create a .env file to ensure the startup script is sourced
echo "Creating .env file..."
echo "source $STARTUP_SCRIPT" > $PROJECT_DIR/.env

# Sync files to wwwroot (if not using WEBSITE_RUN_FROM_PACKAGE)
# This is typically handled by Kudu, but for custom deployments, sometimes explicit copy is needed.
# However, with WEBSITE_RUN_FROM_PACKAGE=0, Kudu should sync files automatically.
# If you face issues with files not being present, uncomment and adjust the following lines.
# cp -r /home/site/repository/* /home/site/wwwroot/

echo "Custom deployment script finished successfully."