# 🎬 Distributed Movie Ticket Booking System

A distributed systems implementation featuring gRPC communication, Raft consensus protocol, and LLM-powered customer support.

## ✨ Features

- **🔐 Authentication & Session Management** - Secure login with session-based auth
- **🎫 Real-time Seat Reservation** - Concurrency control to prevent race conditions
- **🛡️ Overbooking Prevention** - Distributed consistency via Raft consensus
- **💳 Payment Processing** - Mock payment service with charge/refund
- **🤖 AI Customer Support** - OpenAI-powered chatbot with fallback intents
- **🏗️ Fault Tolerance** - Raft leader election and recovery
- **📱 Interactive CLI** - Complete booking workflow interface

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Virtual environment (recommended)

### Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x scripts/*.sh

# Compile protobuf definitions
./scripts/compile_protos.sh
```

### Run the System

**Start the server:**
```bash
./scripts/run_server.sh --host 0.0.0.0 --port 50051
```

**Multiple nodes:**
```bash
./scripts/run_server.sh --port 50051 --node-id node-1 --peers node-2=localhost:50052,node-3=localhost:50053

**Terminal 2 (Node 2):**
This node listens on 50052 and knows about peers at 50051 and 50053.
```bash
./scripts/run_server.sh --port 50052 --node-id node-2 --peers node-1=localhost:50051,node-3=localhost:50053

**Terminal 3 (Node 3):**
This node listens on 50053 and knows about peers at 50051 and 50052.
```bash
./scripts/run_server.sh --port 50053 --node-id node-3 --peers node-1=localhost:50051,node-2=localhost:50052

### 3. Identifying the Leader and Followers

The easiest way to know which node is the leader is to look at the logs in each terminal window.

* **Leader:** You will see logs like `[Raft] Became LEADER for term X`. It will also be the node sending periodic heartbeats (`Sending heartbeat to...`).
* **Follower:** You will see logs indicating it is receiving heartbeats or entries, or that it has voted for another node.

You can also test this by connecting your client to different ports.
* If you connect to the **leader** (e.g., `./scripts/run_client.sh --addr localhost:50051`), your commands will succeed immediately.
* If you connect to a **follower**, the standard Raft behavior (which might need to be explicitly implemented depending on the depth of your current code) is to either forward the request to the leader or reject it, telling the client who the leader is. In this simple implementation, it might just process it if it's a read-only request, or fail if it's a write request that needs consensus.
```

**Start the interactive client:**
```bash
./scripts/run_client.sh --addr localhost:50051
```

## 🎮 Usage

The client provides an interactive interface with these commands:

### 🔐 Authentication
- `login <username> <password>` - Login to the system
- `validate` - Check current session
- `logout` - End current session
- `whoami` - Show current session info

### 🎫 Booking Operations
- `seatmap <show_id>` - View seat matrix with availability
- `reserve <show_id> <total_amount_rupees> [seat_1] [seat_2]` ... - Reserve one or more seats (e.g., reserve show-1 3000 A1 A2)
- `cancel <booking_id>` - Cancel a booking

### 👨‍💼 Admin Operations (admin/password)
- `addshow <movie_title>` - Add a new show
- `addseats <show_id> <seat_ids...>` - Add seats to a show
- `listshows` - List all shows with details
- `refund <payment_ref>` - Process a refund

### 🤖 AI Assistant
- `ask <question>` - Ask the chatbot a question

### ℹ️ System
- `help` - Show help message
- `exit` / `quit` / `q` - Exit the client

## 📋 Example Workflow

### Customer Workflow
```bash
# Login as customer
> login bob secret
ok session=abc123 user=bob

# View seat matrix
> seatmap show-1
Show: show-1
Total seats: 50, Available: 50

Seat Matrix:
Row A: A1:✓ A2:✓ A3:✓ A4:✓ A5:✓ A6:✓ A7:✓ A8:✓ A9:✓ A10:✓
Row B: B1:✓ B2:✓ B3:✓ B4:✓ B5:✓ B6:✓ B7:✓ B8:✓ B9:✓ B10:✓
Row C: C1:✓ C2:✓ C3:✓ C4:✓ C5:✓ C6:✓ C7:✓ C8:✓ C9:✓ C10:✓
Row D: D1:✓ D2:✓ D3:✓ D4:✓ D5:✓ D6:✓ D7:✓ D8:✓ D9:✓ D10:✓
Row E: E1:✓ E2:✓ E3:✓ E4:✓ E5:✓ E6:✓ E7:✓ E8:✓ E9:✓ E10:✓

# Reserve and pay for seat (one-step)
> reserve show-1 A1 1500 Movie Ticket
ok=True booking_id=book_456 payment_ref=pay_789 message=ok

# Ask chatbot
> ask How do I cancel a booking?
answer=To cancel a booking, provide your booking ID and we will release the seat.

# Logout
> logout
ok=True
```

### Admin Workflow
```bash
# Login as admin
> login admin password
ok session=admin_xyz user=admin_admin

# List all shows
> listshows
Show: show-1 - Avengers Endgame 
Show: show-2 - Spider-Man No Way Home 

# Add a new show
> addshow 'Avengers Endgame'
ok=True show_id=show-abc123 message=show added

# Add seats to the new show
> addseats show-abc123 C1 C2 C3 C4 C5
ok=True message=seats added

# Process a refund
> refund pay_789
ok=True message=refund processed
```

## 🏗️ Architecture

### Services
- **AuthService** - Session management and authentication (supports admin users)
- **BookingService** - Seat reservation with integrated payment (one-step booking)
- **AdminService** - Show/seat management and refund processing
- **PaymentService** - Payment processing (mock implementation)
- **ChatbotService** - AI-powered customer support
- **RaftService** - Consensus protocol implementation

### Distributed Features
- **Raft Consensus** - Leader election, log replication, fault tolerance
- **State Machine** - Booking operations replicated across nodes
- **Concurrency Control** - Seat locking prevents overbooking
- **Session Management** - Secure authentication with TTL

## 🔧 Configuration

### Environment Variables
- `BOOKING_HOST` - Server host (default: 0.0.0.0)
- `BOOKING_PORT` - Server port (default: 50051)
- `BOOKING_ADDR` - Client server address (default: localhost:50051)
- `BOOKING_USER` - Default username for client (default: alice)
- `BOOKING_PASS` - Default password for client (default: secret)
- `RAFT_NODE_ID` - Raft node identifier (default: node-1)
- `OPENAI_API_KEY` - OpenAI API key for chatbot (optional)

### Multi-Node Setup
To run multiple Raft nodes, set different `RAFT_NODE_ID` and configure peer addresses in the Raft node initialization.

## 🧪 Testing

The system includes comprehensive error handling and can be tested with:
- Concurrent seat reservations
- Network failures
- Leader election scenarios
- Payment processing
- Chatbot queries

## 📚 Technical Details

- **gRPC** - High-performance RPC framework
- **Protocol Buffers** - Efficient serialization
- **Raft Algorithm** - Distributed consensus protocol
- **Threading** - Concurrent request handling
- **OpenAI API** - Large language model integration

