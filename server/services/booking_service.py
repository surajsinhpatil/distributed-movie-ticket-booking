import logging
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import protos.booking_pb2 as booking_pb2
import protos.booking_pb2_grpc as booking_pb2_grpc
from raft.state_machine import StateMachine

logger = logging.getLogger(__name__)


class BookingServiceImpl(booking_pb2_grpc.BookingServiceServicer):
    """Seat reservation and booking service."""

    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine

    def _validate_session(self, session_token):
        return self.state_machine.get_session(session_token)

    def GetSeatMap(self, request, context):
        logger.info("Seat map requested for show '%s'", request.show_id)
        seats = self.state_machine.get_seat_map(request.show_id)
        if seats is None:
            return booking_pb2.GetSeatMapResponse(show_id=request.show_id)
        return booking_pb2.GetSeatMapResponse(show_id=request.show_id, seats=seats)

    def ReserveSeat(self, request, context):
        session = self._validate_session(request.session_token)
        if not session:
            return booking_pb2.ReserveSeatResponse(
                success=False, message="Unauthorized: please log in first."
            )

        if not request.seat_ids:
            return booking_pb2.ReserveSeatResponse(
                success=False, message="You must specify at least one seat."
            )

        logger.info(
            "Reserve %s for show '%s' by user '%s'",
            list(request.seat_ids), request.show_id, session["user_id"],
        )
        result = self.state_machine.apply_command(
            "reserve_seat",
            {
                "user_id": session["user_id"],
                "show_id": request.show_id,
                "seat_ids": list(request.seat_ids),
                "amount_cents": request.amount_cents,
                "currency": request.currency,
                "description": request.description,
            },
        )

        if result and result.get("success"):
            logger.info("Reserved %s (booking %s)", list(request.seat_ids), result["booking_id"])
            return booking_pb2.ReserveSeatResponse(
                success=True,
                booking_id=result["booking_id"],
                payment_reference=result["payment_ref"],
                message="Seats reserved and payment processed.",
            )

        message = result.get("message", "Failed to reserve seats.")
        logger.info("Reservation rejected: %s", message)
        return booking_pb2.ReserveSeatResponse(success=False, message=message)

    def CancelBooking(self, request, context):
        session = self._validate_session(request.session_token)
        if not session:
            return booking_pb2.CancelBookingResponse(
                success=False, message="Unauthorized: please log in first."
            )

        logger.info("Cancel booking '%s' by user '%s'", request.booking_id, session["user_id"])
        result = self.state_machine.apply_command(
            "cancel_booking",
            {"user_id": session["user_id"], "booking_id": request.booking_id},
        )

        if result and result.get("success"):
            return booking_pb2.CancelBookingResponse(success=True, message="Booking cancelled.")

        message = result.get("message", "Failed to cancel booking.")
        return booking_pb2.CancelBookingResponse(success=False, message=message)

    def ListShows(self, request, context):
        shows_data = self.state_machine.list_shows()
        shows_proto = [
            booking_pb2.Show(
                id=s["id"],
                movie_title=s["movie_title"],
                total_seats=s["total_seats"],
                available_seats=s["available_seats"],
            )
            for s in shows_data
        ]
        return booking_pb2.ListShowsResponse(shows=shows_proto)
