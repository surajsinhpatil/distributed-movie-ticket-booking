import os
import sys
import random
import threading
import time
from concurrent import futures

import grpc

# --- Fix this block ---
# Add project root to sys.path for cross-platform module imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- End block ---

import protos.raft_pb2 as raft_pb2
import protos.raft_pb2_grpc as raft_pb2_grpc
from .state_machine import StateMachine

# Raft node states
FOLLOWER = "FOLLOWER"
CANDIDATE = "CANDIDATE"
LEADER = "LEADER"

# Election timeout range (in seconds)
ELECTION_TIMEOUT_MIN = 3.0
ELECTION_TIMEOUT_MAX = 5.0
# Heartbeat interval (in seconds)
HEARTBEAT_INTERVAL = 1.0

class RaftNode(raft_pb2_grpc.RaftServiceServicer):
    """A minimal implementation of Raft for leader election and heartbeats."""
    
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers # dict of {node_id: address}
        self.state_machine = StateMachine()
        
        # Raft state variables
        self.state = FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.leader_id = None
        
        # Timers
        self.election_timer_thread = None
        self.heartbeat_timer_thread = None
        self.last_heartbeat = 0
        
        self.lock = threading.Lock()
        
        # gRPC stubs for peers
        self.peer_stubs = {}
        for peer_id, peer_addr in self.peers.items():
            channel = grpc.insecure_channel(peer_addr)
            self.peer_stubs[peer_id] = raft_pb2_grpc.RaftServiceStub(channel)

        print(f"✅ Raft node '{self.node_id}' initialized with peers: {list(peers.keys())}")
        self.start_election_timer()

    def _log(self, message):
        """Helper for formatted logging."""
        print(f"[RAFT-{self.node_id} | {self.state} | T{self.current_term}] {message}")

    def start_election_timer(self):
        """Starts a background timer that triggers an election when it fires."""
        if self.heartbeat_timer_thread:
            self.heartbeat_timer_thread.cancel()
            self.heartbeat_timer_thread = None

        timeout = random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)
        self.election_timer_thread = threading.Timer(timeout, self.start_election)
        self.election_timer_thread.daemon = True
        self.election_timer_thread.start()
        self._log(f"Started election timer ({timeout:.2f}s).")

    def reset_election_timer(self):
        """Resets the election timer."""
        if self.election_timer_thread:
            self.election_timer_thread.cancel()
        self.start_election_timer()

    def start_heartbeat_timer(self):
        """Starts a periodic heartbeat timer (only for leaders)."""
        if self.election_timer_thread:
            self.election_timer_thread.cancel()
            self.election_timer_thread = None
            
        self.send_heartbeats() # Send immediately
        self.heartbeat_timer_thread = threading.Timer(HEARTBEAT_INTERVAL, self.start_heartbeat_timer)
        self.heartbeat_timer_thread.daemon = True
        self.heartbeat_timer_thread.start()

    def step_down(self, new_term):
        """Steps down to FOLLOWER state."""
        with self.lock:
            self.state = FOLLOWER
            self.current_term = new_term
            self.voted_for = None
            self.leader_id = None
        self._log(f"Stepping down to FOLLOWER for term {new_term}.")
        self.start_election_timer()

    def start_election(self):
        """Transitions to CANDIDATE and starts an election."""
        with self.lock:
            if self.state == LEADER:
                return # Leaders don't start elections

            self.state = CANDIDATE
            self.current_term += 1
            self.voted_for = self.node_id
            self._log(f"Starting election for term {self.current_term}.")
            votes_received = 1 # Vote for self
        
        majority = (len(self.peers) + 1) // 2 + 1
        
        for peer_id, stub in self.peer_stubs.items():
            # In a real impl, we'd send last_log_index/term
            req = raft_pb2.RequestVoteRequest(
                term=self.current_term,
                candidate_id=self.node_id,
                last_log_index=0, 
                last_log_term=0
            )
            
            try:
                resp = stub.RequestVote(req, timeout=0.5)
                if resp.vote_granted:
                    with self.lock:
                        votes_received += 1
                        self._log(f"Vote granted by {peer_id}.")
                        if votes_received >= majority and self.state == CANDIDATE:
                            self.become_leader()
                elif resp.term > self.current_term:
                    self._log(f"Vote denied by {peer_id}, term {resp.term} is higher.")
                    self.step_down(resp.term)
                    return
            except grpc.RpcError as e:
                # --- THIS IS THE FIX ---
                details = e.details() if hasattr(e, 'details') else str(e)
                self._log(f"Could not request vote from {peer_id}: {details}")
                # --- END FIX ---
        
        # If we're still a candidate after all that, we didn't win.
        # Reset timer to try again later.
        if self.state == CANDIDATE:
            self._log(f"Election failed, received {votes_received}/{majority} votes.")
            self.start_election_timer()

    def become_leader(self):
        """Transitions to LEADER state."""
        self.state = LEADER
        self.leader_id = self.node_id
        self._log(f"🎉 BECAME LEADER FOR TERM {self.current_term} 🎉")
        self.start_heartbeat_timer()

    def send_heartbeats(self):
        """Sends empty AppendEntries RPCs to all peers to maintain leadership."""
        if self.state != LEADER:
            return

        self._log(f"Sending heartbeats...")
        
        for peer_id, stub in self.peer_stubs.items():
            # This is just a heartbeat, so 'entries' is empty
            req = raft_pb2.AppendEntriesRequest(
                term=self.current_term,
                leader_id=self.node_id,
                leader_commit=0 # Not implemented
            )
            
            try:
                resp = stub.AppendEntries(req, timeout=0.5)
                if not resp.success and resp.term > self.current_term:
                    self._log(f"Peer {peer_id} has higher term {resp.term}. Stepping down.")
                    self.step_down(resp.term)
                    return
            except grpc.RpcError as e:
                # --- THIS IS THE FIX ---
                details = e.details() if hasattr(e, 'details') else str(e)
                self._log(f"Could not send heartbeat to {peer_id}: {details}")
                # --- END FIX ---

    # --- gRPC Service Methods ---

    def AppendEntries(self, request, context):
        """Handles AppendEntries RPCs (heartbeats or log entries)."""
        with self.lock:
            # If request's term is lower, reject
            if request.term < self.current_term:
                return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
            
            # If request's term is higher, step down
            if request.term > self.current_term:
                self.step_down(request.term)
            
            # If we're a candidate, step down (leader has been found)
            if self.state == CANDIDATE:
                self.state = FOLLOWER
                self._log(f"Received AppendEntries from new leader {request.leader_id}, stepping down.")

            self.leader_id = request.leader_id
            self.reset_election_timer()
            
            # (In a real impl, we'd append 'request.entries' to our log here)
            # For now, just a successful heartbeat
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=True)

    def RequestVote(self, request, context):
        """Handles RequestVote RPCs."""
        with self.lock:
            # If request's term is lower, reject
            if request.term < self.current_term:
                self._log(f"Rejecting vote for {request.candidate_id} (term {request.term} < {self.current_term})")
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)

            # If request's term is higher, step down and update term
            if request.term > self.current_term:
                self._log(f"Term {request.term} is higher. Stepping down and updating term.")
                self.step_down(request.term)

            # Check if we can grant the vote
            # (In a real impl, we'd also check if candidate's log is up-to-date)
            if self.voted_for is None or self.voted_for == request.candidate_id:
                self.voted_for = request.candidate_id
                self._log(f"Granting vote for {request.candidate_id} for term {self.current_term}.")
                self.reset_election_timer()
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=True)
            else:
                self._log(f"Rejecting vote for {request.candidate_id} (already voted for {self.voted_for})")
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)