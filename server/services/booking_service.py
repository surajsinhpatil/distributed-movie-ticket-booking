import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'protos')))

import protos.booking_pb2 as booking_pb2
import protos.booking_pb2_grpc as booking_pb2_grpc
from raft.state_machine import StateMachine

class BookingServiceImpl(booking_pb2_grpc.BookingServiceServicer):
    """Implements the booking service."""
    
    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine

    def _validate_session(self, session_token):
        return self.state_machine.get_session(session_token)

    def GetSeatMap(self, request, context):
        """Returns the seat map for a given show."""
        print(f"🗺️  Fetching seat map for show: {request.show_id}")
        seats = self.state_machine.get_seat_map(request.show_id)
        if seats is not None:
            return booking_pb2.GetSeatMapResponse(show_id=request.show_id, seats=seats)
        context.set_code(404)
        context.set_details(f"Show '{request.show_id}' not found.")
        return booking_pb2.GetSeatMapResponse()

    def ReserveSeat(self, request, context):
        """Reserves one or more seats for a show."""
        session = self._validate_session(request.session_token)
        if not session:
            context.set_code(401)
            context.set_details("Unauthorized: Invalid session token.")
            return booking_pb2.ReserveSeatResponse(success=False, message="Unauthorized")

        if not request.seat_ids:
            context.set_code(400)
            context.set_details("No seats provided.")
            return booking_pb2.ReserveSeatResponse(success=False, message="You must specify at least one seat.")

        print(f"🎫 Reserve seats '{', '.join(request.seat_ids)}' for show '{request.show_id}' by user '{session['user_id']}'")
        
        result = self.state_machine.apply_command("reserve_seat", {
            "user_id": session['user_id'],
            "show_id": request.show_id,
            "seat_ids": list(request.seat_ids), # Pass the list of seats
            "amount_cents": request.amount_cents,
            "currency": request.currency,
            "description": request.description
        })

        if result and result.get("success"):
            print(f"✅ Seats '{', '.join(request.seat_ids)}' reserved successfully.")
            return booking_pb2.ReserveSeatResponse(
                success=True,
                booking_id=result["booking_id"],
                payment_reference=result["payment_ref"],
                message="Seats reserved and payment processed."
            )
        else:
            print(f"❌ Failed to reserve seats: {result.get('message', 'Unknown error')}")
            context.set_code(400)
            context.set_details(result.get("message", "Failed to reserve seats."))
            return booking_pb2.ReserveSeatResponse(success=False, message=result.get("message"))

    def CancelBooking(self, request, context):
        """Cancels a booking."""
        session = self._validate_session(request.session_token)
        if not session:
            context.set_code(401)
            context.set_details("Unauthorized: Invalid session token.")
            return booking_pb2.CancelBookingResponse(success=False, message="Unauthorized")
        
        print(f"🚫 Cancel booking '{request.booking_id}' by user '{session['user_id']}'")
        result = self.state_machine.apply_command("cancel_booking", {
            "user_id": session['user_id'],
            "booking_id": request.booking_id
        })

        if result and result.get("success"):
            print(f"✅ Booking '{request.booking_id}' cancelled.")
            return booking_pb2.CancelBookingResponse(success=True, message="Booking cancelled.")
        else:
            print(f"❌ Failed to cancel booking '{request.booking_id}': {result.get('message')}")
            context.set_code(400)
            context.set_details(result.get("message", "Failed to cancel booking."))
            return booking_pb2.CancelBookingResponse(success=False, message=result.get("message"))

    def ListShows(self, request, context):
        """Lists all available shows."""
        print("🎬 Listing all shows")
        shows_data = self.state_machine.list_shows()
        shows_proto = [
            booking_pb2.Show(
                id=s['id'],
                movie_title=s['movie_title'],
                total_seats=s['total_seats'],
                available_seats=s['available_seats']
            ) for s in shows_data
        ]
        return booking_pb2.ListShowsResponse(shows=shows_proto)

