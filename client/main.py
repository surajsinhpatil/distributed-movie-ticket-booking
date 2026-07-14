import argparse
import os
import sys

from dotenv import load_dotenv

# Make the project root importable before importing local modules.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# BookingClient lives in client/client.py (same directory as this script)
from client import BookingClient

HELP_TEXT = """
Distributed Movie Ticket Booking System - Client
-------------------------------------------------
Session
  login <user> <pass>    Log in to the system
  logout                 Log out of the current session
  validate               Check whether the current session is valid
  whoami                 Show current session info

Browsing & booking
  listshows              List all available shows
  seatmap <show_id>      View the seat map for a show
  reserve <show_id> <amount_cents> <seat_1> [seat_2] ...
                         Reserve one or more seats (e.g. reserve show-1 3000 A5 A6)
  cancel <booking_id>    Cancel a reservation (auto-refunds)

Admin (log in as admin/password)
  addshow <movie_title>  Add a new show
  addseats <show_id> <seat_ids...>
                         Add seats to a show (e.g. addseats show-1 F1 F2)
  refund <payment_ref>   Process a refund for a payment

Assistant
  ask <question>         Ask the support assistant a question

Misc
  help                   Show this help message
  exit, quit, q          Exit the client
"""


def main(addr):
    client = BookingClient(addr)
    print("Movie Ticket Booking client. Type 'help' for commands.")

    while True:
        try:
            cmd_line = input("> ").strip()
            if not cmd_line:
                continue

            parts = cmd_line.split()
            command = parts[0].lower()
            args = parts[1:]

            if command in ("exit", "quit", "q"):
                break
            elif command == "help":
                print(HELP_TEXT)
            elif command == "login":
                if len(args) == 2:
                    client.login(args[0], args[1])
                else:
                    print("Usage: login <username> <password>")
            elif command == "logout":
                client.logout()
            elif command == "validate":
                client.validate_session()
            elif command == "whoami":
                client.whoami()
            elif command == "listshows":
                client.list_shows()
            elif command == "seatmap":
                if args:
                    client.get_seat_map(args[0])
                else:
                    print("Usage: seatmap <show_id>")
            elif command == "reserve":
                if len(args) >= 3:
                    show_id = args[0]
                    try:
                        amount = int(args[1])
                    except ValueError:
                        print("Error: amount must be an integer number of cents.")
                        continue
                    client.reserve_seat(show_id, args[2:], amount, "USD")
                else:
                    print("Usage: reserve <show_id> <amount_cents> <seat_1> [seat_2] ...")
            elif command == "cancel":
                if args:
                    client.cancel_booking(args[0])
                else:
                    print("Usage: cancel <booking_id>")
            elif command == "addshow":
                if args:
                    client.add_show(" ".join(args))
                else:
                    print("Usage: addshow <movie_title>")
            elif command == "addseats":
                if len(args) >= 2:
                    client.add_seats(args[0], args[1:])
                else:
                    print("Usage: addseats <show_id> <seat_ids...>")
            elif command == "refund":
                if args:
                    client.process_refund(args[0])
                else:
                    print("Usage: refund <payment_ref>")
            elif command == "ask":
                if args:
                    client.ask_question(" ".join(args))
                else:
                    print("Usage: ask <question>")
            else:
                print(f"Unknown command: '{command}'. Type 'help' for options.")

        except (EOFError, KeyboardInterrupt):
            print("\nExiting client. Goodbye!")
            break
        except Exception as exc:
            print(f"An error occurred: {exc}")


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description="Booking system client")
    parser.add_argument(
        "--addr",
        default=os.getenv("BOOKING_ADDR", "localhost:50051"),
        help="Server address (host:port)",
    )
    args = parser.parse_args()
    main(args.addr)
