from api.models.approval_job import JobState

VALID_TRANSITIONS = {
    JobState.PENDING: [JobState.CIBA_SENT, JobState.PRE_APPROVED, JobState.BLOCKED],
    JobState.CIBA_SENT: [JobState.WAITING_APPROVAL],
    JobState.WAITING_APPROVAL: [
        JobState.APPROVED,
        JobState.REJECTED,
        JobState.TIMEOUT,
        JobState.PARTIALLY_APPROVED,
    ],
    JobState.PARTIALLY_APPROVED: [
        JobState.APPROVED,
        JobState.TIMEOUT,
        JobState.BLOCKED,
    ],
    JobState.TIMEOUT: [JobState.ESCALATED, JobState.BLOCKED],
    JobState.ESCALATED: [JobState.APPROVED, JobState.REJECTED, JobState.BLOCKED],
    JobState.APPROVED: [],
    JobState.REJECTED: [],
    JobState.BLOCKED: [],
    JobState.PRE_APPROVED: [JobState.APPROVED, JobState.BLOCKED],
}


def can_transition(current: JobState, target: JobState) -> bool:
    allowed = VALID_TRANSITIONS.get(current, [])
    return target in allowed


def validate_transition(current: JobState, target: JobState) -> None:
    if not can_transition(current, target):
        raise ValueError(f"Invalid state transition: {current.value} -> {target.value}")
