import os
import sys
import argparse
from concurrent import futures
import grpc
from dotenv import load_dotenv

# Add protos to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'protos')))

# Import generated proto files
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.booking_pb2_grpc as booking_pb2_grpc
import protos.admin_pb2_grpc as admin_pb2_grpc
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc
import protos.raft_pb2_grpc as raft_pb2_grpc

# Import services
from services.auth_service import AuthServiceImpl
from services.booking_service import BookingServiceImpl
from services.admin_service import AdminServiceImpl
from services.chatbot_service import ChatbotServiceImpl
from raft.raft_node import RaftNode

def serve(host, port):
    """Starts the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Initialize Raft node (for a real distributed setup, this would be more complex)
    # In this single-node example, it primarily manages the state machine.
    raft_node = RaftNode(node_id="node-1", peers=[])

    # Add services to the server
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServiceImpl(raft_node.state_machine), server)
    booking_pb2_grpc.add_BookingServiceServicer_to_server(BookingServiceImpl(raft_node.state_machine), server)
    admin_pb2_grpc.add_AdminServiceServicer_to_server(AdminServiceImpl(raft_node.state_machine), server)
    chatbot_pb2_grpc.add_ChatbotServiceServicer_to_server(ChatbotServiceImpl(raft_node.state_machine), server)
    # The Raft service would be added here for inter-node communication in a real multi-node setup.
    # raft_pb2_grpc.add_RaftServiceServicer_to_server(raft_node, server)

    server.add_insecure_port(f'{host}:{port}')
    print(f"✅ Server started, listening on {host}:{port}")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    load_dotenv()
    parser = argparse.ArgumentParser(description="Distributed Movie Ticket Booking Server")
    parser.add_argument("--host", default=os.getenv("BOOKING_HOST", "0.0.0.0"), help="Host to bind")
    parser.add_argument("--port", type=int, default=os.getenv("BOOKING_PORT", 50051), help="Port to listen on")
    args = parser.parse_args()
    
    serve(args.host, args.port)
