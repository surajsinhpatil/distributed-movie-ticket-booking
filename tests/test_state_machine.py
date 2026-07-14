"""Unit tests for the replicated StateMachine (no gRPC / network required)."""
import os
import sys

import pytest

# Make the server package importable (StateMachine lives in server/raft).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "server"))

from raft.state_machine import StateMachine  # noqa: E402


@pytest.fixture
def sm():
    return StateMachine()


def test_authenticate_valid_and_invalid(sm):
    assert sm.apply_command("authenticate_user", {"username": "bob", "password": "secret"}) == "user-bob"
    assert sm.apply_command("authenticate_user", {"username": "bob", "password": "wrong"}) is None


def test_admin_flag(sm):
    assert sm.is_admin("user-admin") is True
    assert sm.is_admin("user-bob") is False


def reserve(sm, seats, amount=3000):
    return sm.apply_command(
        "reserve_seat",
        {
            "user_id": "user-bob",
            "show_id": "show-1",
            "seat_ids": seats,
            "amount_cents": amount,
            "currency": "USD",
            "description": "test",
        },
    )


def test_reserve_marks_seats_unavailable(sm):
    result = reserve(sm, ["A1", "A2"])
    assert result["success"] is True
    seat_map = sm.get_seat_map("show-1")
    assert seat_map["A1"] is False
    assert seat_map["A2"] is False
    assert seat_map["A3"] is True


def test_double_booking_is_rejected(sm):
    assert reserve(sm, ["A1"])["success"] is True
    second = reserve(sm, ["A1"])
    assert second["success"] is False
    assert "already reserved" in second["message"].lower()


def test_reserve_unknown_seat_is_rejected(sm):
    result = reserve(sm, ["Z9"])
    assert result["success"] is False
    assert "not found" in result["message"].lower()


def test_cancel_frees_seats_and_refunds(sm):
    booked = reserve(sm, ["B1", "B2"])
    booking_id = booked["booking_id"]
    payment_ref = booked["payment_ref"]

    cancelled = sm.apply_command("cancel_booking", {"user_id": "user-bob", "booking_id": booking_id})
    assert cancelled["success"] is True

    seat_map = sm.get_seat_map("show-1")
    assert seat_map["B1"] is True and seat_map["B2"] is True
    assert sm.store["payments"][payment_ref]["status"] == "refunded"


def test_cancel_other_users_booking_is_denied(sm):
    booked = reserve(sm, ["C1"])
    denied = sm.apply_command("cancel_booking", {"user_id": "user-someone-else", "booking_id": booked["booking_id"]})
    assert denied["success"] is False
    assert "permission" in denied["message"].lower()


def test_admin_add_show_and_seats(sm):
    show = sm.apply_command("add_show", {"movie_title": "Inception"})
    assert show["success"] is True
    show_id = show["show_id"]

    added = sm.apply_command("add_seats", {"show_id": show_id, "seat_ids": ["A1", "A2", "A3"]})
    assert added["success"] is True

    shows = {s["id"]: s for s in sm.list_shows()}
    assert shows[show_id]["movie_title"] == "Inception"
    assert shows[show_id]["total_seats"] == 3
    assert shows[show_id]["available_seats"] == 3


def test_refund_is_idempotent(sm):
    booked = reserve(sm, ["D1"])
    ref = booked["payment_ref"]
    assert sm.apply_command("process_refund", {"payment_ref": ref})["success"] is True
    second = sm.apply_command("process_refund", {"payment_ref": ref})
    assert second["success"] is False
    assert "already refunded" in second["message"].lower()
