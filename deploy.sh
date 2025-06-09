#!/bin/bash

echo "Running custom deployment script for Linux Function App..."

# Define the path to the Python virtual environment that Azure Functions sets up
# This is where your requirements.txt packages are installed, and where we'll install Azure CLI
PYTHON_VENV_PATH="/home/site/wwwroot/.python_packages"
PYTHON_EXE="${PYTHON_VENV_PATH}/bin/python" # Path to the Python executable within the venv

# Check if the 'az' command is already available in the venv's bin directory
# If not, proceed with installation
if [ ! -f "${PYTHON_VENV_PATH}/bin/az" ]; then
    echo "Azure CLI not found, installing into function's Python environment..."
    # Install azure-cli core package into the function's Python environment
    # Using --target ensures it installs into the specified path, avoiding system-wide conflicts
    "${PYTHON_EXE}" -m pip install azure-cli --target="${PYTHON_VENV_PATH}"

    # Check the exit status of the pip install command
    if [ $? -ne 0 ]; then
        echo "ERROR: Azure CLI pip install failed."
        exit 1 # Exit with an error code if installation fails
    fi
    echo "Azure CLI installed successfully."
else
    echo "Azure CLI already installed, skipping installation."
fi

# IMPORTANT: Call Kudu's default deployment script to sync application files
# This step is crucial. It ensures your actual function code (from your Git repo)
# is properly copied from the /home/site/repository source to /home/site/wwwroot
# This command and its parameters are standard for Kudu deployments.
echo "Running KuduSync to deploy application files..."
/opt/Kudu/bin/kudusync -v 500 -f /home/site/repository -t /home/site/wwwroot -n /home/site/deployments/tools -p /home/site/deployments/temp -i ".git;.deployment;deploy.sh"
if [ $? -ne 0 ]; then
    echo "ERROR: KuduSync failed during file synchronization."
    exit 1 # Exit with an error code if KuduSync fails
fi

echo "Custom deployment script finished successfully."