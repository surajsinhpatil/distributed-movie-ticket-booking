#!/bin/bash
echo "Compiling protocol buffers..."

# This is the key change.
# We run protoc from the root directory (I=.) and output to the root directory (python_out=.).
# This makes protoc aware of the 'protos' package structure and
# generates correct relative imports (e.g., "from . import auth_pb2")
# inside the generated _grpc.py files.
python -m grpc_tools.protoc -I=. --python_out=. --grpc_python_out=. \
    protos/admin.proto \
    protos/auth.proto \
    protos/booking.proto \
    protos/chatbot.proto \
    protos/raft.proto


echo "Done."
