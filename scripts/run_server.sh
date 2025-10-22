#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Add the project root to the PYTHONPATH to ensure modules are found
export PYTHONPATH=$PYTHONPATH:.

# Run the server from the project root
python server/main.py "$@"

