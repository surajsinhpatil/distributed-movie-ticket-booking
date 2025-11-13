import argparse
import os
import sys
import time
from concurrent import futures

import grpc

# --- Fix this block ---
# Add project root to sys.path for cross-platform module imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- End block ---

import protos.admin_pb2_grpc as admin_pb2_grpc
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.booking_pb2_grpc as booking_pb2_grpc
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc
import protos.raft_pb2_grpc as raft_pb2_grpc  # Import Raft gRPC
from raft.raft_node import RaftNode
from services.admin_service import AdminServiceImpl
from services.auth_service import AuthServiceImpl
from services.booking_service import BookingServiceImpl
from services.chatbot_service import ChatbotServiceImpl

def parse_peers(peers_str):
    """Parses a comma-separated string of peers into a dictionary."""
    if not peers_str:
        return {}
    peers = {}
    for peer in peers_str.split(','):
        parts = peer.split('=')
        if len(parts) == 2:
            peers[parts[0].strip()] = parts[1].strip()
    return peers

def serve():
    parser = argparse.ArgumentParser(description="Distributed Movie Booking Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=50051, help="Port to bind to")
    parser.add_argument("--node-id", default="node-1", help="Unique ID for this Raft node")
    # New argument for peers
    parser.add_argument("--peers", default="", help="Comma-separated list of peers (e.g., node-2=localhost:50052,node-3=localhost:50053)")
    
    args = parser.parse_args()

    # Parse peers from command line
    peers = parse_peers(args.peers)

    print(f"🚀 Starting server on {args.host}:{args.port} as '{args.node_id}'...")
    if peers:
        print(f"🔗 Configured peers: {peers}")
    else:
        print("ℹ️  Running in standalone mode (no peers configured).")

    # Initialize Raft node (which holds the state machine)
    # The RaftNode itself IS the RaftServiceServicer
    raft_node = RaftNode(args.node_id, peers)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # --- Register ALL services ---
    
    # Application services
    auth_pb2_grpc.add_AuthServiceServicer_to_server(
        AuthServiceImpl(raft_node.state_machine), server
    )
    booking_pb2_grpc.add_BookingServiceServicer_to_server(
        BookingServiceImpl(raft_node.state_machine), server
    )
    admin_pb2_grpc.add_AdminServiceServicer_to_server(
        AdminServiceImpl(raft_node.state_machine), server
    )
    chatbot_pb2_grpc.add_ChatbotServiceServicer_to_server(
        ChatbotServiceImpl(raft_node.state_machine), server
    )
    
    # --- THIS IS THE FIX ---
    # Register the Raft service so nodes can communicate
    raft_pb2_grpc.add_RaftServiceServicer_to_server(raft_node, server)
    # --- END FIX ---

    # Start listening
    server.add_insecure_port(f"{args.host}:{args.port}")
    server.start()
    print(f"✅ Server is running and listening on port {args.port}")

    try:
        while True:
            time.sleep(86400) # Keep the main thread alive
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        server.stop(0)

if __name__ == "__main__":
    serve()