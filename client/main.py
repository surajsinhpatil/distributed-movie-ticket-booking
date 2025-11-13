import os
import sys
import argparse
from dotenv import load_dotenv
from client import BookingClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def print_help():
    """Prints the help message for the client CLI."""
    help_text = """
    Distributed Movie Ticket Booking System Client
    ---------------------------------------------
    Commands:
      login <user> <pass>   - Login to the system
      logout                - Logout from the current session
      validate              - Check if the current session is valid
      whoami                - Show current session info
      
      listshows             - List all available movie shows
      seatmap <show_id>     - View the seat map for a show
      reserve <show_id> <total_amount_rupees> <seat_1> [seat_2] ...
                            - Reserve one or more seats (e.g., reserve show-1 3000 A5 A6)
      cancel <booking_id>   - Cancel a reservation
      
      addshow <movie_title> - (Admin) Add a new show
      addseats <show_id> <seat_ids...>
                            - (Admin) Add seats to a show (e.g., addseats show-1 F1 F2)
      refund <payment_ref>  - (Admin) Process a refund for a payment
                            
      ask "<question>"      - Ask the AI assistant a question
      
      help                  - Show this help message
      exit, quit, q         - Exit the client
    """
    print(help_text)

def main(addr):
    """Main function to run the interactive client."""
    client = BookingClient(addr)
    print("🎬 Welcome to the Movie Ticket Booking CLI!")
    print("Type 'help' for a list of commands.")

    while True:
        try:
            cmd_line = input("> ").strip()
            if not cmd_line:
                continue

            parts = cmd_line.split()
            command = parts[0].lower()
            args = parts[1:]

            if command in ["exit", "quit", "q"]:
                break
            elif command == "help":
                print_help()
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
                if len(args) >= 3: # show_id, amount, at least one seat
                    show_id = args[0]
                    try:
                        amount = int(args[1])
                        seat_ids = args[2:]
                        client.reserve_seat(show_id, seat_ids, amount, "USD") # Currency hardcoded for simplicity
                    except ValueError:
                        print("Error: Amount must be an integer.")
                else:
                    print("Usage: reserve <show_id> <total_amount_cents> <seat_1> [seat_2] ...")
            elif command == "cancel":
                if args:
                    client.cancel_booking(args[0])
                else:
                    print("Usage: cancel <booking_id>")
            elif command == "addshow":
                 if args:
                    # Handle movie titles with spaces
                    movie_title = " ".join(args)
                    client.add_show(movie_title)
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
                    question = " ".join(args)
                    client.ask_question(question)
                else:
                    print("Usage: ask <question>")
            else:
                print(f"Unknown command: '{command}'. Type 'help' for options.")

        except (EOFError, KeyboardInterrupt):
            print("\nExiting client. Goodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == '__main__':
    load_dotenv()
    parser = argparse.ArgumentParser(description="Booking system client")
    parser.add_argument("--addr", default=os.getenv("BOOKING_ADDR", "localhost:50051"), help="Server address")
    args = parser.parse_args()
    main(args.addr)

