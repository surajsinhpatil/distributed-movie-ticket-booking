#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

echo "Starting client..."

# Run the client from the project root
python client/main.py "$@"

