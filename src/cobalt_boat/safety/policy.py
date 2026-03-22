"""Safety policy engine with whitelist, rate limiting, and audit integration."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from cobalt_boat.config import Settings
from cobalt_boat.safety.models import ALLOWED_DOMAINS, DENIED_DOMAINS, CommandRequest, PolicyDecision
from cobalt_boat.storage.repositories import AuditLogRepository, CommandAuditEntry


@dataclass(frozen=True)
class WhitelistEntry:
    """Definition of an allowed command shape."""

    domain: str
    command_name: str
    required_params: tuple[str, ...]


DEFAULT_WHITELIST: tuple[WhitelistEntry, ...] = (
    WhitelistEntry(domain="audio", command_name="set_volume", required_params=("zone", "level")),
    WhitelistEntry(domain="audio", command_name="set_source", required_params=("source",)),
    WhitelistEntry(domain="lighting", command_name="set_color", required_params=("zone", "rgb")),
    WhitelistEntry(domain="lighting", command_name="set_brightness", required_params=("zone", "level")),
)


class PolicyEngine:
    """Evaluates command requests and writes audit logs for every attempt."""

    def __init__(
        self,
        settings: Settings,
        audit_log_repository: AuditLogRepository,
        whitelist: tuple[WhitelistEntry, ...] = DEFAULT_WHITELIST,
    ) -> None:
        self._settings = settings
        self._audit_log_repository = audit_log_repository
        self._whitelist = {(entry.domain, entry.command_name): entry for entry in whitelist}
        self._attempts: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def evaluate(self, request: CommandRequest) -> PolicyDecision:
        """Evaluate command request against strict Phase 1 policy."""

        decision = self._evaluate_internal(request)
        self._audit_log_repository.log_command(
            CommandAuditEntry(
                timestamp=request.timestamp.astimezone(timezone.utc),
                domain=request.domain,
                command_name=request.command_name,
                parameters=request.parameters,
                approved=decision.approved,
                reason=decision.reason,
                correlation_id=request.correlation_id,
            )
        )
        return decision

    def _evaluate_internal(self, request: CommandRequest) -> PolicyDecision:
        if self._settings.emergency_disable:
            return PolicyDecision(approved=False, reason="emergency_disable_enabled")

        if self._settings.read_only_mode:
            return PolicyDecision(approved=False, reason="read_only_mode_enabled")

        if not self._settings.write_enable:
            return PolicyDecision(approved=False, reason="write_enable_disabled")

        domain = request.domain.strip().lower()
        if domain in DENIED_DOMAINS:
            return PolicyDecision(approved=False, reason="domain_permanently_denied")
        if domain not in ALLOWED_DOMAINS:
            return PolicyDecision(approved=False, reason="domain_not_allowed")

        key = (domain, request.command_name)
        rule = self._whitelist.get(key)
        if rule is None:
            return PolicyDecision(approved=False, reason="command_not_whitelisted")

        missing = [name for name in rule.required_params if name not in request.parameters]
        if missing:
            return PolicyDecision(approved=False, reason=f"missing_required_params:{','.join(missing)}")

        if self._is_rate_limited(key, request.timestamp):
            return PolicyDecision(approved=False, reason="rate_limited")

        return PolicyDecision(approved=True, reason="approved")

    def _is_rate_limited(self, key: tuple[str, str], timestamp: datetime) -> bool:
        window = timedelta(seconds=self._settings.command_rate_limit_window_sec)
        max_attempts = self._settings.command_rate_limit_max_attempts

        queue = self._attempts[key]
        threshold = timestamp - window
        while queue and queue[0] < threshold:
            queue.popleft()

        queue.append(timestamp)
        return len(queue) > max_attempts
