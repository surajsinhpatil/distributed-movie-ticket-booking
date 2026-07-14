import logging
import os
import random
import sys
import threading

import grpc

# Ensure the project root is importable regardless of working directory.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import protos.raft_pb2 as raft_pb2
import protos.raft_pb2_grpc as raft_pb2_grpc
from .state_machine import StateMachine

logger = logging.getLogger(__name__)

# Raft node states
FOLLOWER = "FOLLOWER"
CANDIDATE = "CANDIDATE"
LEADER = "LEADER"

# Election timeout range and heartbeat interval, in seconds.
ELECTION_TIMEOUT_MIN = 3.0
ELECTION_TIMEOUT_MAX = 5.0
HEARTBEAT_INTERVAL = 1.0


class RaftNode(raft_pb2_grpc.RaftServiceServicer):
    """A minimal Raft implementation for leader election and heartbeats."""

    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers  # {node_id: address}
        self.state_machine = StateMachine()

        # Raft state
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

        logger.info("Raft node '%s' initialized with peers: %s", node_id, list(peers.keys()))
        self.start_election_timer()

    def _log(self, message):
        logger.info("[%s | %s | T%d] %s", self.node_id, self.state, self.current_term, message)

    def start_election_timer(self):
        """Start a background timer that triggers an election when it fires."""
        if self.heartbeat_timer_thread:
            self.heartbeat_timer_thread.cancel()
            self.heartbeat_timer_thread = None

        timeout = random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)
        self.election_timer_thread = threading.Timer(timeout, self.start_election)
        self.election_timer_thread.daemon = True
        self.election_timer_thread.start()
        self._log(f"Started election timer ({timeout:.2f}s).")

    def reset_election_timer(self):
        if self.election_timer_thread:
            self.election_timer_thread.cancel()
        self.start_election_timer()

    def start_heartbeat_timer(self):
        """Start a periodic heartbeat timer (leaders only)."""
        if self.election_timer_thread:
            self.election_timer_thread.cancel()
            self.election_timer_thread = None

        self.send_heartbeats()  # Send immediately
        self.heartbeat_timer_thread = threading.Timer(HEARTBEAT_INTERVAL, self.start_heartbeat_timer)
        self.heartbeat_timer_thread.daemon = True
        self.heartbeat_timer_thread.start()

    def step_down(self, new_term):
        """Revert to FOLLOWER state for a newer term."""
        with self.lock:
            self.state = FOLLOWER
            self.current_term = new_term
            self.voted_for = None
            self.leader_id = None
        self._log(f"Stepping down to FOLLOWER for term {new_term}.")
        self.start_election_timer()

    def start_election(self):
        """Transition to CANDIDATE and request votes from peers."""
        with self.lock:
            if self.state == LEADER:
                return  # Leaders do not start elections

            self.state = CANDIDATE
            self.current_term += 1
            self.voted_for = self.node_id
            self._log(f"Starting election for term {self.current_term}.")
            votes_received = 1  # Vote for self

        majority = (len(self.peers) + 1) // 2 + 1

        for peer_id, stub in self.peer_stubs.items():
            req = raft_pb2.RequestVoteRequest(
                term=self.current_term,
                candidate_id=self.node_id,
                last_log_index=0,
                last_log_term=0,
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
                    self._log(f"Vote denied by {peer_id}; term {resp.term} is higher.")
                    self.step_down(resp.term)
                    return
            except grpc.RpcError as exc:
                self._log(f"Could not request vote from {peer_id}: {exc.details()}")

        if self.state == CANDIDATE:
            self._log(f"Election failed; received {votes_received}/{majority} votes.")
            self.start_election_timer()

    def become_leader(self):
        self.state = LEADER
        self.leader_id = self.node_id
        self._log(f"Became LEADER for term {self.current_term}.")
        self.start_heartbeat_timer()

    def send_heartbeats(self):
        """Send empty AppendEntries RPCs to peers to maintain leadership."""
        if self.state != LEADER:
            return

        self._log("Sending heartbeats to peers.")
        for peer_id, stub in self.peer_stubs.items():
            req = raft_pb2.AppendEntriesRequest(
                term=self.current_term,
                leader_id=self.node_id,
                leader_commit=0,
            )
            try:
                resp = stub.AppendEntries(req, timeout=0.5)
                if not resp.success and resp.term > self.current_term:
                    self._log(f"Peer {peer_id} has higher term {resp.term}; stepping down.")
                    self.step_down(resp.term)
                    return
            except grpc.RpcError as exc:
                self._log(f"Could not send heartbeat to {peer_id}: {exc.details()}")

    # --- gRPC service methods ---

    def AppendEntries(self, request, context):
        """Handle AppendEntries RPCs (heartbeats or log entries)."""
        with self.lock:
            if request.term < self.current_term:
                return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)

            if request.term > self.current_term:
                self.step_down(request.term)

            if self.state == CANDIDATE:
                self.state = FOLLOWER
                self._log(f"AppendEntries from leader {request.leader_id}; stepping down.")

            self.leader_id = request.leader_id
            self.reset_election_timer()
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=True)

    def RequestVote(self, request, context):
        """Handle RequestVote RPCs."""
        with self.lock:
            if request.term < self.current_term:
                self._log(f"Rejecting vote for {request.candidate_id} (stale term {request.term}).")
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)

            if request.term > self.current_term:
                self._log(f"Term {request.term} is higher; stepping down.")
                self.step_down(request.term)

            if self.voted_for is None or self.voted_for == request.candidate_id:
                self.voted_for = request.candidate_id
                self._log(f"Granting vote to {request.candidate_id} for term {self.current_term}.")
                self.reset_election_timer()
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=True)

            self._log(f"Rejecting vote for {request.candidate_id} (already voted for {self.voted_for}).")
            return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)
