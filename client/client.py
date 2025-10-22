import os
import sys
import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'protos')))

import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.booking_pb2 as booking_pb2
import protos.booking_pb2_grpc as booking_pb2_grpc
import protos.admin_pb2 as admin_pb2
import protos.admin_pb2_grpc as admin_pb2_grpc
import protos.chatbot_pb2 as chatbot_pb2
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc

class BookingClient:
    """Client for interacting with the booking system."""

    def __init__(self, address):
        self.channel = grpc.insecure_channel(address)
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(self.channel)
        self.booking_stub = booking_pb2_grpc.BookingServiceStub(self.channel)
        self.admin_stub = admin_pb2_grpc.AdminServiceStub(self.channel)
        self.chatbot_stub = chatbot_pb2_grpc.ChatbotServiceStub(self.channel)
        self.session_token = None
        self.user_id = None
        self.is_admin = False

    def _handle_grpc_error(self, e):
        """Prints a user-friendly message for gRPC errors."""
        print(f"Error: {e.details()} (code: {e.code().name})")

    def login(self, username, password):
        try:
            req = auth_pb2.LoginRequest(username=username, password=password)
            res = self.auth_stub.Login(req)
            if res.success:
                self.session_token = res.session_token
                self.user_id = res.user_id
                # After login, check if the user is an admin
                self.validate_session() 
                print(f"✅ Login successful. Session: {res.session_token[:8]}... User: {res.user_id}")
            else:
                print(f"❌ Login failed: {res.message}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)

    def logout(self):
        if not self.session_token:
            print("Not logged in.")
            return
        try:
            req = auth_pb2.LogoutRequest(session_token=self.session_token)
            res = self.auth_stub.Logout(req)
            if res.success:
                print("✅ Logged out successfully.")
            else:
                print(f"❌ Logout failed: {res.message}")
            self.session_token = None
            self.user_id = None
            self.is_admin = False
        except grpc.RpcError as e:
            self._handle_grpc_error(e)
            
    def validate_session(self):
        if not self.session_token:
            print("No active session to validate.")
            return
        try:
            req = auth_pb2.ValidateSessionRequest(session_token=self.session_token)
            res = self.auth_stub.ValidateSession(req)
            self.is_admin = res.is_admin
            if res.is_valid:
                role = "Admin" if res.is_admin else "User"
                print(f"✅ Session is valid for user {res.user_id} ({role}).")
            else:
                print("❌ Session is invalid or has expired.")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)
            
    def whoami(self):
        if self.session_token and self.user_id:
            role = "Admin" if self.is_admin else "User"
            print(f"Authenticated as: {self.user_id} ({role})")
            print(f"Session Token: {self.session_token}")
        else:
            print("Not logged in.")

    def get_seat_map(self, show_id):
        try:
            req = booking_pb2.GetSeatMapRequest(show_id=show_id)
            res = self.booking_stub.GetSeatMap(req)
            
            print(f"--- Seat Map for Show: {res.show_id} ---")
            if not res.seats:
                print("No seats found for this show.")
                return

            # Sort seats for consistent display, e.g., A1, A2, ..., B1, B2, ...
            sorted_seats = sorted(res.seats.items(), key=lambda item: (item[0][0], int(item[0][1:])))
            
            current_row = ''
            row_str = ''
            for seat_id, is_available in sorted_seats:
                row = seat_id[0]
                if row != current_row and current_row != '':
                    print(f"Row {current_row}: {row_str}")
                    row_str = ''
                current_row = row
                symbol = "✓" if is_available else "✗"
                row_str += f"{seat_id}:{symbol} "
            if row_str:
                print(f"Row {current_row}: {row_str}")

        except grpc.RpcError as e:
            self._handle_grpc_error(e)

    def reserve_seat(self, show_id, seat_id, amount_cents, currency):
        if not self.session_token:
            print("Please login first.")
            return
        try:
            req = booking_pb2.ReserveSeatRequest(
                session_token=self.session_token,
                show_id=show_id,
                seat_id=seat_id,
                amount_cents=amount_cents,
                currency=currency,
                description=f"Ticket for {show_id}"
            )
            res = self.booking_stub.ReserveSeat(req)
            if res.success:
                print(f"✅ Reservation successful!")
                print(f"   Booking ID: {res.booking_id}")
                print(f"   Payment Ref: {res.payment_reference}")
            else:
                print(f"❌ Reservation failed: {res.message}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)

    def cancel_booking(self, booking_id):
        if not self.session_token:
            print("Please login first.")
            return
        try:
            req = booking_pb2.CancelBookingRequest(session_token=self.session_token, booking_id=booking_id)
            res = self.booking_stub.CancelBooking(req)
            if res.success:
                print(f"✅ Booking {booking_id} cancelled successfully.")
            else:
                print(f"❌ Cancellation failed: {res.message}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)
            
    def list_shows(self):
        try:
            req = booking_pb2.ListShowsRequest()
            res = self.booking_stub.ListShows(req)
            print("--- Available Shows ---")
            if not res.shows:
                print("No shows currently scheduled.")
            for show in res.shows:
                print(f"- ID: {show.id}, Title: {show.movie_title} ({show.available_seats}/{show.total_seats} available)")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)
            
    def add_show(self, movie_title):
        if not self.session_token:
            print("Please login as admin first.")
            return
        try:
            req = admin_pb2.AddShowRequest(session_token=self.session_token, movie_title=movie_title)
            res = self.admin_stub.AddShow(req)
            if res.success:
                print(f"✅ Show '{movie_title}' added with ID: {res.show_id}")
            else:
                print(f"❌ Failed to add show: {res.message}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)

    def add_seats(self, show_id, seat_ids):
        if not self.session_token:
            print("Please login as admin first.")
            return
        try:
            req = admin_pb2.AddSeatsRequest(session_token=self.session_token, show_id=show_id, seat_ids=seat_ids)
            res = self.admin_stub.AddSeats(req)
            if res.success:
                print(f"✅ Added {len(seat_ids)} seats to show {show_id}.")
            else:
                print(f"❌ Failed to add seats: {res.message}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)
            
    def process_refund(self, payment_ref):
        if not self.session_token:
            print("Please login as admin first.")
            return
        try:
            req = admin_pb2.ProcessRefundRequest(session_token=self.session_token, payment_reference=payment_ref)
            res = self.admin_stub.ProcessRefund(req)
            if res.success:
                print(f"✅ Refund processed for {payment_ref}.")
            else:
                print(f"❌ Failed to process refund: {res.message}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)

    def ask_question(self, query):
        if not self.session_token:
            print("Please login first.")
            return
        try:
            req = chatbot_pb2.AskQuestionRequest(session_token=self.session_token, query=query)
            res = self.chatbot_stub.AskQuestion(req)
            source = "LLM" if res.from_llm else "System"
            print(f"🤖 Assistant ({source}): {res.answer}")
        except grpc.RpcError as e:
            self._handle_grpc_error(e)
