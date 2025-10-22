import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'protos')))

import protos.admin_pb2 as admin_pb2
import protos.admin_pb2_grpc as admin_pb2_grpc
from raft.state_machine import StateMachine

class AdminServiceImpl(admin_pb2_grpc.AdminServiceServicer):
    """Implements the admin service for managing shows and seats."""

    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine

    def _validate_admin_session(self, session_token):
        """Validates if the session belongs to an admin user."""
        session = self.state_machine.get_session(session_token)
        if session and self.state_machine.is_admin(session['user_id']):
            return session
        return None

    def AddShow(self, request, context):
        """Adds a new movie show."""
        session = self._validate_admin_session(request.session_token)
        if not session:
            context.set_code(403)
            context.set_details("Forbidden: Admin access required.")
            return admin_pb2.AddShowResponse(success=False, message="Forbidden")

        print(f"🎬 Admin '{session['user_id']}' adding show: '{request.movie_title}'")
        result = self.state_machine.apply_command("add_show", {"movie_title": request.movie_title})
        
        if result and result.get("success"):
            print(f"✅ Show '{request.movie_title}' added with ID: {result['show_id']}")
            return admin_pb2.AddShowResponse(success=True, show_id=result["show_id"], message="Show added successfully.")
        else:
            context.set_code(500)
            context.set_details("Failed to add show.")
            return admin_pb2.AddShowResponse(success=False, message="Failed to add show.")

    def AddSeats(self, request, context):
        """Adds seats to an existing show."""
        session = self._validate_admin_session(request.session_token)
        if not session:
            context.set_code(403)
            context.set_details("Forbidden: Admin access required.")
            return admin_pb2.AddSeatsResponse(success=False, message="Forbidden")

        print(f"💺 Admin '{session['user_id']}' adding {len(request.seat_ids)} seats to show '{request.show_id}'")
        result = self.state_machine.apply_command("add_seats", {"show_id": request.show_id, "seat_ids": list(request.seat_ids)})
        
        if result and result.get("success"):
            print(f"✅ Seats added to show '{request.show_id}'")
            return admin_pb2.AddSeatsResponse(success=True, message="Seats added successfully.")
        else:
            context.set_code(400)
            context.set_details(result.get("message", "Failed to add seats."))
            return admin_pb2.AddSeatsResponse(success=False, message=result.get("message"))
            
    def ProcessRefund(self, request, context):
        """Processes a refund for a payment."""
        session = self._validate_admin_session(request.session_token)
        if not session:
            context.set_code(403)
            context.set_details("Forbidden: Admin access required.")
            return admin_pb2.ProcessRefundResponse(success=False, message="Forbidden")

        print(f"💳 Admin '{session['user_id']}' processing refund for '{request.payment_reference}'")
        result = self.state_machine.apply_command("process_refund", {"payment_ref": request.payment_reference})

        if result and result.get("success"):
            print(f"✅ Refund processed for '{request.payment_reference}'")
            return admin_pb2.ProcessRefundResponse(success=True, message="Refund processed.")
        else:
            context.set_code(400)
            context.set_details(result.get("message", "Failed to process refund."))
            return admin_pb2.ProcessRefundResponse(success=False, message=result.get("message"))
