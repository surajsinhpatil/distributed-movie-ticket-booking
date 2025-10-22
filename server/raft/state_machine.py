import threading
import uuid
from datetime import datetime, timedelta

# This class represents the replicated state machine in the Raft consensus protocol.
# All changes to the application's state must go through this state machine
# by applying commands. This ensures that all nodes in the cluster apply the
# same commands in the same order, maintaining consistency.

class StateMachine:
    """Manages the application state and applies commands consistently."""
    
    def __init__(self):
        self._lock = threading.Lock()
        # In-memory data store
        self.store = {
            "users": {
                "user-alice": {"username": "alice", "password_hash": "secret", "is_admin": False},
                "user-admin": {"username": "admin", "password_hash": "password", "is_admin": True}
            },
            "sessions": {}, # session_token -> {user_id, expiry}
            "shows": {}, # show_id -> {movie_title, seats: {seat_id -> is_available}}
            "bookings": {}, # booking_id -> {user_id, show_id, seat_id, payment_ref}
            "payments": {} # payment_ref -> {amount, currency, status}
        }
        # Add some initial data
        self._initialize_data()

    def _initialize_data(self):
        # Add a default show and seats
        show_id = "show-1"
        self.store["shows"][show_id] = {"movie_title": "Avengers: Endgame", "seats": {}}
        for row in "ABCDE":
            for i in range(1, 11):
                seat_id = f"{row}{i}"
                self.store["shows"][show_id]["seats"][seat_id] = True # True means available


    def apply_command(self, command, args):
        """Applies a command to the state machine in a thread-safe manner."""
        with self._lock:
            method = getattr(self, f"_command_{command}", None)
            if method:
                return method(**args)
            raise AttributeError(f"Command '{command}' not found.")

    # --- Command Implementations (protected methods) ---

    def _command_authenticate_user(self, username, password):
        for user_id, user in self.store["users"].items():
            if user["username"] == username and user["password_hash"] == password:
                return user_id
        return None
        
    def _command_create_session(self, session_token, user_id):
        self.store["sessions"][session_token] = {
            "user_id": user_id,
            "expiry": datetime.now() + timedelta(hours=1)
        }
        return True

    def _command_delete_session(self, session_token):
        if session_token in self.store["sessions"]:
            del self.store["sessions"][session_token]
            return True
        return False
        
    def _command_reserve_seat(self, user_id, show_id, seat_id, amount_cents, currency, description):
        show = self.store["shows"].get(show_id)
        if not show:
            return {"success": False, "message": "Show not found."}
        
        if seat_id not in show["seats"]:
            return {"success": False, "message": "Seat not found."}

        if not show["seats"][seat_id]: # If seat is not available
            return {"success": False, "message": "Seat already reserved."}

        # Mock payment processing
        payment_ref = f"pay_{uuid.uuid4().hex[:8]}"
        self.store["payments"][payment_ref] = {"amount": amount_cents, "currency": currency, "status": "succeeded"}

        # Reserve seat
        show["seats"][seat_id] = False # Mark as unavailable
        
        booking_id = f"book_{uuid.uuid4().hex[:8]}"
        self.store["bookings"][booking_id] = {
            "user_id": user_id,
            "show_id": show_id,
            "seat_id": seat_id,
            "payment_ref": payment_ref
        }

        return {"success": True, "booking_id": booking_id, "payment_ref": payment_ref}

    def _command_cancel_booking(self, user_id, booking_id):
        booking = self.store["bookings"].get(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found."}
        
        if booking["user_id"] != user_id and not self.is_admin(user_id):
            return {"success": False, "message": "Permission denied."}
            
        # Make seat available again
        show = self.store["shows"].get(booking["show_id"])
        if show and booking["seat_id"] in show["seats"]:
            show["seats"][booking["seat_id"]] = True
        
        # Mock refund
        self._command_process_refund(booking["payment_ref"])

        del self.store["bookings"][booking_id]
        return {"success": True}

    def _command_add_show(self, movie_title):
        show_id = f"show_{uuid.uuid4().hex[:6]}"
        self.store["shows"][show_id] = {"movie_title": movie_title, "seats": {}}
        return {"success": True, "show_id": show_id}

    def _command_add_seats(self, show_id, seat_ids):
        show = self.store["shows"].get(show_id)
        if not show:
            return {"success": False, "message": "Show not found."}
        
        for seat_id in seat_ids:
            show["seats"][seat_id] = True # Mark as available
        return {"success": True}

    def _command_process_refund(self, payment_ref):
        payment = self.store["payments"].get(payment_ref)
        if not payment:
            return {"success": False, "message": "Payment not found."}
        
        if payment["status"] == "refunded":
            return {"success": False, "message": "Payment already refunded."}
        
        payment["status"] = "refunded"
        return {"success": True}

    # --- Read-only methods (do not need to be commands) ---
    def get_session(self, session_token):
        session = self.store["sessions"].get(session_token)
        if session and session["expiry"] > datetime.now():
            return session
        return None
    
    def is_admin(self, user_id):
        user = self.store["users"].get(user_id)
        return user and user.get("is_admin", False)

    def get_seat_map(self, show_id):
        with self._lock:
            show = self.store["shows"].get(show_id)
            return show["seats"] if show else None

    def list_shows(self):
        with self._lock:
            show_list = []
            for show_id, show_data in self.store["shows"].items():
                seats = show_data.get("seats", {})
                available_seats = sum(1 for is_avail in seats.values() if is_avail)
                show_list.append({
                    "id": show_id,
                    "movie_title": show_data["movie_title"],
                    "total_seats": len(seats),
                    "available_seats": available_seats
                })
            return show_list
