import os
import sys

import grpc

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import protos.admin_pb2 as admin_pb2
import protos.admin_pb2_grpc as admin_pb2_grpc
import protos.auth_pb2 as auth_pb2
import protos.auth_pb2_grpc as auth_pb2_grpc
import protos.booking_pb2 as booking_pb2
import protos.booking_pb2_grpc as booking_pb2_grpc
import protos.chatbot_pb2 as chatbot_pb2
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc


class BookingClient:
    """Thin gRPC client wrapper for the booking system."""

    def __init__(self, address):
        self.channel = grpc.insecure_channel(address)
        self.auth_stub = auth_pb2_grpc.AuthServiceStub(self.channel)
        self.booking_stub = booking_pb2_grpc.BookingServiceStub(self.channel)
        self.admin_stub = admin_pb2_grpc.AdminServiceStub(self.channel)
        self.chatbot_stub = chatbot_pb2_grpc.ChatbotServiceStub(self.channel)
        self.session_token = None
        self.user_id = None
        self.is_admin = False

    def _handle_grpc_error(self, exc):
        print(f"[error] {exc.details()} (code: {exc.code().name})")

    def login(self, username, password):
        try:
            res = self.auth_stub.Login(
                auth_pb2.LoginRequest(username=username, password=password)
            )
            if res.success:
                self.session_token = res.session_token
                self.user_id = res.user_id
                self.validate_session()
                print(f"Logged in as {res.user_id} (session {res.session_token[:8]}...).")
            else:
                print(f"Login failed: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def logout(self):
        if not self.session_token:
            print("Not logged in.")
            return
        try:
            res = self.auth_stub.Logout(
                auth_pb2.LogoutRequest(session_token=self.session_token)
            )
            print("Logged out." if res.success else f"Logout failed: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)
        finally:
            self.session_token = None
            self.user_id = None
            self.is_admin = False

    def validate_session(self):
        if not self.session_token:
            print("No active session to validate.")
            return
        try:
            res = self.auth_stub.ValidateSession(
                auth_pb2.ValidateSessionRequest(session_token=self.session_token)
            )
            self.is_admin = res.is_admin
            if res.is_valid:
                role = "Admin" if res.is_admin else "User"
                print(f"Session valid for {res.user_id} ({role}).")
            else:
                print("Session is invalid or has expired.")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def whoami(self):
        if self.session_token and self.user_id:
            role = "Admin" if self.is_admin else "User"
            print(f"Authenticated as {self.user_id} ({role}).")
            print(f"Session token: {self.session_token}")
        else:
            print("Not logged in.")

    def get_seat_map(self, show_id):
        try:
            res = self.booking_stub.GetSeatMap(
                booking_pb2.GetSeatMapRequest(show_id=show_id)
            )
            print(f"--- Seat map for show: {res.show_id} ---")
            if not res.seats:
                print("No seats found for this show.")
                return

            sorted_seats = sorted(
                res.seats.items(), key=lambda item: (item[0][0], int(item[0][1:]))
            )
            current_row = ""
            row_str = ""
            for seat_id, is_available in sorted_seats:
                row = seat_id[0]
                if row != current_row and current_row != "":
                    print(f"Row {current_row}: {row_str}")
                    row_str = ""
                current_row = row
                symbol = "." if is_available else "X"
                row_str += f"{seat_id}:{symbol} "
            if row_str:
                print(f"Row {current_row}: {row_str}")
            print("Legend: . = available, X = reserved")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def reserve_seat(self, show_id, seat_ids, amount_cents, currency):
        if not self.session_token:
            print("Please log in first.")
            return
        try:
            res = self.booking_stub.ReserveSeat(
                booking_pb2.ReserveSeatRequest(
                    session_token=self.session_token,
                    show_id=show_id,
                    seat_ids=seat_ids,
                    amount_cents=amount_cents,
                    currency=currency,
                    description=f"Tickets for {show_id}",
                )
            )
            if res.success:
                print("Reservation successful.")
                print(f"  Booking ID:  {res.booking_id}")
                print(f"  Payment ref: {res.payment_reference}")
            else:
                print(f"Reservation failed: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def cancel_booking(self, booking_id):
        if not self.session_token:
            print("Please log in first.")
            return
        try:
            res = self.booking_stub.CancelBooking(
                booking_pb2.CancelBookingRequest(
                    session_token=self.session_token, booking_id=booking_id
                )
            )
            if res.success:
                print(f"Booking {booking_id} cancelled.")
            else:
                print(f"Cancellation failed: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def list_shows(self):
        try:
            res = self.booking_stub.ListShows(booking_pb2.ListShowsRequest())
            print("--- Available shows ---")
            if not res.shows:
                print("No shows currently scheduled.")
            for show in res.shows:
                print(
                    f"- {show.id}: {show.movie_title} "
                    f"({show.available_seats}/{show.total_seats} available)"
                )
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def add_show(self, movie_title):
        if not self.session_token:
            print("Please log in as admin first.")
            return
        try:
            res = self.admin_stub.AddShow(
                admin_pb2.AddShowRequest(
                    session_token=self.session_token, movie_title=movie_title
                )
            )
            if res.success:
                print(f"Show '{movie_title}' added with ID {res.show_id}.")
            else:
                print(f"Failed to add show: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def add_seats(self, show_id, seat_ids):
        if not self.session_token:
            print("Please log in as admin first.")
            return
        try:
            res = self.admin_stub.AddSeats(
                admin_pb2.AddSeatsRequest(
                    session_token=self.session_token, show_id=show_id, seat_ids=seat_ids
                )
            )
            if res.success:
                print(f"Added {len(seat_ids)} seats to show {show_id}.")
            else:
                print(f"Failed to add seats: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def process_refund(self, payment_ref):
        if not self.session_token:
            print("Please log in as admin first.")
            return
        try:
            res = self.admin_stub.ProcessRefund(
                admin_pb2.ProcessRefundRequest(
                    session_token=self.session_token, payment_reference=payment_ref
                )
            )
            if res.success:
                print(f"Refund processed for {payment_ref}.")
            else:
                print(f"Failed to process refund: {res.message}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)

    def ask_question(self, query):
        if not self.session_token:
            print("Please log in first.")
            return
        try:
            res = self.chatbot_stub.AskQuestion(
                chatbot_pb2.AskQuestionRequest(
                    session_token=self.session_token, query=query
                )
            )
            source = "LLM" if res.from_llm else "System"
            print(f"Assistant ({source}): {res.answer}")
        except grpc.RpcError as exc:
            self._handle_grpc_error(exc)
