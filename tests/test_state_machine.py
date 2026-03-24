"""Tests for the job state machine transitions."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from api.worker.state_machine import can_transition, validate_transition
from api.models.approval_job import JobState


def test_pending_to_ciba_sent():
    assert can_transition(JobState.PENDING, JobState.CIBA_SENT)


def test_pending_to_pre_approved():
    assert can_transition(JobState.PENDING, JobState.PRE_APPROVED)


def test_pending_to_blocked():
    assert can_transition(JobState.PENDING, JobState.BLOCKED)


def test_pending_cannot_go_to_approved():
    assert not can_transition(JobState.PENDING, JobState.APPROVED)


def test_waiting_to_approved():
    assert can_transition(JobState.WAITING_APPROVAL, JobState.APPROVED)


def test_waiting_to_rejected():
    assert can_transition(JobState.WAITING_APPROVAL, JobState.REJECTED)


def test_waiting_to_timeout():
    assert can_transition(JobState.WAITING_APPROVAL, JobState.TIMEOUT)


def test_timeout_to_escalated():
    assert can_transition(JobState.TIMEOUT, JobState.ESCALATED)


def test_timeout_to_blocked():
    assert can_transition(JobState.TIMEOUT, JobState.BLOCKED)


def test_escalated_to_approved():
    assert can_transition(JobState.ESCALATED, JobState.APPROVED)


def test_escalated_to_blocked():
    assert can_transition(JobState.ESCALATED, JobState.BLOCKED)


def test_approved_is_terminal():
    assert not can_transition(JobState.APPROVED, JobState.PENDING)
    assert not can_transition(JobState.APPROVED, JobState.BLOCKED)


def test_rejected_is_terminal():
    assert not can_transition(JobState.REJECTED, JobState.APPROVED)


def test_blocked_is_terminal():
    assert not can_transition(JobState.BLOCKED, JobState.APPROVED)


def test_validate_invalid_transition_raises():
    with pytest.raises(ValueError, match="Invalid state transition"):
        validate_transition(JobState.APPROVED, JobState.PENDING)


def test_validate_valid_transition_ok():
    validate_transition(JobState.PENDING, JobState.CIBA_SENT)


def test_partially_approved_to_approved():
    assert can_transition(JobState.PARTIALLY_APPROVED, JobState.APPROVED)


def test_partially_approved_to_timeout():
    assert can_transition(JobState.PARTIALLY_APPROVED, JobState.TIMEOUT)
