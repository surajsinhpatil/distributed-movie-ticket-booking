#!/bin/bash

# Directory where the .proto files are located
PROTO_DIR=./protos
# Directory for the Python output
OUTPUT_DIR=./protos

# Create the output directory if it doesn't exist
mkdir -p ${OUTPUT_DIR}

# Find all .proto files and compile them
find ${PROTO_DIR} -name "*.proto" | while read proto_file; do
  echo "Compiling ${proto_file}..."
  python -m grpc_tools.protoc \
    --proto_path=${PROTO_DIR} \
    --python_out=${OUTPUT_DIR} \
    --grpc_python_out=${OUTPUT_DIR} \
    "${proto_file}"
done

# Create __init__.py files to make the output directories Python packages
touch ${OUTPUT_DIR}/__init__.py

echo "✅ Protobuf compilation finished."
