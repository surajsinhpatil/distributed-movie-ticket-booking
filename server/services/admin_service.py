import logging
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import protos.admin_pb2 as admin_pb2
import protos.admin_pb2_grpc as admin_pb2_grpc
from raft.state_machine import StateMachine

logger = logging.getLogger(__name__)


class AdminServiceImpl(admin_pb2_grpc.AdminServiceServicer):
    """Admin service for managing shows, seats and refunds."""

    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine

    def _validate_admin_session(self, session_token):
        session = self.state_machine.get_session(session_token)
        if session and self.state_machine.is_admin(session["user_id"]):
            return session
        return None

    def AddShow(self, request, context):
        session = self._validate_admin_session(request.session_token)
        if not session:
            return admin_pb2.AddShowResponse(
                success=False, message="Forbidden: admin access required."
            )

        logger.info("Admin '%s' adding show '%s'", session["user_id"], request.movie_title)
        result = self.state_machine.apply_command(
            "add_show", {"movie_title": request.movie_title}
        )

        if result and result.get("success"):
            return admin_pb2.AddShowResponse(
                success=True, show_id=result["show_id"], message="Show added successfully."
            )
        return admin_pb2.AddShowResponse(success=False, message="Failed to add show.")

    def AddSeats(self, request, context):
        session = self._validate_admin_session(request.session_token)
        if not session:
            return admin_pb2.AddSeatsResponse(
                success=False, message="Forbidden: admin access required."
            )

        logger.info(
            "Admin '%s' adding %d seats to show '%s'",
            session["user_id"], len(request.seat_ids), request.show_id,
        )
        result = self.state_machine.apply_command(
            "add_seats", {"show_id": request.show_id, "seat_ids": list(request.seat_ids)}
        )

        if result and result.get("success"):
            return admin_pb2.AddSeatsResponse(success=True, message="Seats added successfully.")
        message = result.get("message", "Failed to add seats.")
        return admin_pb2.AddSeatsResponse(success=False, message=message)

    def ProcessRefund(self, request, context):
        session = self._validate_admin_session(request.session_token)
        if not session:
            return admin_pb2.ProcessRefundResponse(
                success=False, message="Forbidden: admin access required."
            )

        logger.info("Admin '%s' refunding '%s'", session["user_id"], request.payment_reference)
        result = self.state_machine.apply_command(
            "process_refund", {"payment_ref": request.payment_reference}
        )

        if result and result.get("success"):
            return admin_pb2.ProcessRefundResponse(success=True, message="Refund processed.")
        message = result.get("message", "Failed to process refund.")
        return admin_pb2.ProcessRefundResponse(success=False, message=message)
