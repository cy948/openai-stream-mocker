#!/bin/bash
# filepath: /home/cy948/dev/github/openai-stream-mocker/install.sh

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Miniconda or Anaconda first."
    echo "Visit: https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html"
    exit 1
fi

# Create and activate conda environment
echo "Creating conda environment 'openai-stream-mocker'..."
conda env create -f environment.yml

echo ""
echo "Installation complete! Activate the environment with:"
echo "conda activate openai-stream-mocker"
echo ""
echo "Then start the server with:"
echo "python main.py"