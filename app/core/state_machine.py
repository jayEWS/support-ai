from enum import Enum
from typing import List, Dict
from app.core.logging import logger

class TicketStatus(str, Enum):
    ON_HOLD = "ON_HOLD"                       # A- (Critical)
    PENDING_PROGRAMMER = "PENDING_PROGRAMMER" # B- (Escalated)
    PENDING_USER = "PENDING_USER"             # C- (Pending User)
    PENDING_AGENT = "PENDING_AGENT"           # D- (Pending Investigator)
    CLOSED = "CLOSED"                         # E- (Resolved)

# Prefix to Status Mapping
PREFIX_STATUS_MAP = {
    "A-": TicketStatus.ON_HOLD,
    "B-": TicketStatus.PENDING_PROGRAMMER,
    "C-": TicketStatus.PENDING_USER,
    "D-": TicketStatus.PENDING_AGENT,
    "E-": TicketStatus.CLOSED,
}

# Valid Transitions
VALID_TRANSITIONS: Dict[TicketStatus, List[TicketStatus]] = {
    TicketStatus.ON_HOLD: [TicketStatus.PENDING_PROGRAMMER, TicketStatus.PENDING_AGENT, TicketStatus.CLOSED],
    TicketStatus.PENDING_PROGRAMMER: [TicketStatus.PENDING_AGENT, TicketStatus.CLOSED],
    TicketStatus.PENDING_USER: [TicketStatus.PENDING_AGENT, TicketStatus.ON_HOLD, TicketStatus.CLOSED],
    TicketStatus.PENDING_AGENT: [TicketStatus.PENDING_USER, TicketStatus.PENDING_PROGRAMMER, TicketStatus.ON_HOLD, TicketStatus.CLOSED],
    TicketStatus.CLOSED: [TicketStatus.PENDING_AGENT] # Can be reopened
}

class TicketStateMachine:
    @staticmethod
    def get_status_from_summary(summary: str) -> TicketStatus:
        for prefix, status in PREFIX_STATUS_MAP.items():
            if summary.startswith(prefix):
                return status
        return TicketStatus.PENDING_AGENT # Default

    @staticmethod
    def transition(ticket_id: int, current_status: str, next_status: TicketStatus, agent_id: str = "System"):
        if current_status == next_status:
            return next_status

        current_status_enum = TicketStatus(current_status) if current_status in TicketStatus.__members__ else None
        
        # If unknown current status, allow transition to any valid initial state
        if current_status_enum and next_status not in VALID_TRANSITIONS.get(current_status_enum, []):
            logger.warning(
                f"Invalid ticket state transition",
                extra={"extra_data": {
                    "ticket_id": ticket_id,
                    "from": current_status,
                    "to": next_status,
                    "agent_id": agent_id
                }}
            )
            # In production we might raise an error, but here we'll log and allow for flexibility if needed, 
            # or strictly enforce. Let's strictly enforce.
            raise ValueError(f"Invalid transition from {current_status} to {next_status}")

        logger.info(
            f"Ticket state transition",
            extra={"extra_data": {
                "ticket_id": ticket_id,
                "from": current_status,
                "to": next_status,
                "agent_id": agent_id,
                "event": "state_transition"
            }}
        )
        return next_status
