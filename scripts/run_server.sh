#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

echo "Starting server..."

# Run the server from the project root
python server/main.py "$@"

