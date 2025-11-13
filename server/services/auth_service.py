import os
import sys
import uuid
import time
from datetime import datetime, timedelta

# Add protos to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
from raft.state_machine import StateMachine

class AuthServiceImpl(auth_pb2_grpc.AuthServiceServicer):
    """Implements the authentication and session management service."""

    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine

    def Login(self, request, context):
        """Handles user login."""
        print(f"🔐 Login attempt for user: {request.username}")
        user_id = self.state_machine.apply_command("authenticate_user", {"username": request.username, "password": request.password})

        if user_id:
            session_token = f"session_{uuid.uuid4().hex}"
            self.state_machine.apply_command("create_session", {"session_token": session_token, "user_id": user_id})
            print(f"✅ Login successful for {request.username}")
            return auth_pb2.LoginResponse(
                success=True,
                session_token=session_token,
                user_id=user_id
            )
        else:
            print(f"❌ Login failed for {request.username}")
            return auth_pb2.LoginResponse(success=False, message="Invalid credentials")

    def Logout(self, request, context):
        """Handles user logout."""
        print(f"🔐 Logout attempt for session: {request.session_token}")
        success = self.state_machine.apply_command("delete_session", {"session_token": request.session_token})
        
        if success:
            print(f"✅ Logout successful for session: {request.session_token}")
            return auth_pb2.LogoutResponse(success=True, message="Logged out successfully")
        else:
            print(f"❌ Logout failed for session: {request.session_token}")
            return auth_pb2.LogoutResponse(success=False, message="Invalid session token")


    def ValidateSession(self, request, context):
        """Validates a user's session token."""
        session_info = self.state_machine.get_session(request.session_token)
        if session_info:
            is_admin = self.state_machine.is_admin(session_info['user_id'])
            return auth_pb2.ValidateSessionResponse(is_valid=True, user_id=session_info['user_id'], is_admin=is_admin)
        return auth_pb2.ValidateSessionResponse(is_valid=False)
