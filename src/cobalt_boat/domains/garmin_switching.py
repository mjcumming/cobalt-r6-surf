"""Garmin-oriented NMEA 2000 digital switching profile models.

This module defines a simulated switch bank profile for planning and validation.
It does not transmit any CAN messages and does not expose raw frame controls.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GarminShadowCommand:
    """One typed, policy-routable command in a simulated switch action."""

    kind: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class GarminSwitchControl:
    """One virtual switch control that could map to Garmin switching UI."""

    instance: int
    label: str
    description: str
    shadow_commands: tuple[GarminShadowCommand, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "instance": self.instance,
            "label": self.label,
            "description": self.description,
            "shadow_commands": [
                {"kind": command.kind, "parameters": command.parameters}
                for command in self.shadow_commands
            ],
        }


@dataclass(frozen=True)
class GarminSwitchBankProfile:
    """Simulated NMEA switch bank profile for interoperability planning."""

    bank_instance: int
    bank_label: str
    status_pgn: int
    control_pgn: int
    controls: tuple[GarminSwitchControl, ...]
    write_eligible: bool
    gate_reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "bank_instance": self.bank_instance,
            "bank_label": self.bank_label,
            "status_pgn": self.status_pgn,
            "control_pgn": self.control_pgn,
            "write_eligible": self.write_eligible,
            "gate_reason": self.gate_reason,
            "controls": [control.as_dict() for control in self.controls],
        }


def default_switch_bank_template() -> dict[str, object]:
    """Return editable profile template without runtime gate state fields."""

    return {
        "bank_instance": 1,
        "bank_label": "Cobalt Virtual Switching",
        "status_pgn": 127501,
        "control_pgn": 127502,
        "controls": [
            {
                "instance": 1,
                "label": "Evening Lights",
                "description": "Warm low-brightness cockpit and underwater lighting scene.",
                "shadow_commands": [
                    {"kind": "lighting.set_color", "zone": "cockpit", "rgb": [255, 180, 120]},
                    {"kind": "lighting.set_brightness", "zone": "cockpit", "level": 35},
                    {"kind": "lighting.set_brightness", "zone": "underwater", "level": 20},
                ],
            },
            {
                "instance": 2,
                "label": "Dock Quiet",
                "description": "Lower stereo volume for dockside conversations.",
                "shadow_commands": [
                    {"kind": "audio.set_volume", "zone": "cockpit", "level": 18}
                ],
            },
            {
                "instance": 3,
                "label": "All Accent Off",
                "description": "Set accent lighting brightness to off for known zones.",
                "shadow_commands": [
                    {"kind": "lighting.set_brightness", "zone": "cockpit", "level": 0},
                    {"kind": "lighting.set_brightness", "zone": "underwater", "level": 0},
                ],
            },
        ],
    }


def _gate_reason(*, read_only_mode: bool, write_enable: bool, emergency_disable: bool) -> str:
    if emergency_disable:
        return "emergency_disable_enabled"
    if read_only_mode:
        return "read_only_mode_enabled"
    if not write_enable:
        return "write_enable_disabled"
    return "eligible_if_policy_approved"


def build_default_switch_bank_profile(
    *,
    read_only_mode: bool,
    write_enable: bool,
    emergency_disable: bool,
) -> GarminSwitchBankProfile:
    """Build a conservative virtual switch bank for Garmin interoperability tests."""

    template = default_switch_bank_template()
    return build_switch_bank_profile_from_template(
        template=template,
        read_only_mode=read_only_mode,
        write_enable=write_enable,
        emergency_disable=emergency_disable,
    )


def build_switch_bank_profile_from_template(
    *,
    template: dict[str, object],
    read_only_mode: bool,
    write_enable: bool,
    emergency_disable: bool,
) -> GarminSwitchBankProfile:
    """Build profile from a validated template and apply runtime safety gate state."""

    controls_input = template["controls"]
    controls = tuple(
        GarminSwitchControl(
            instance=int(control["instance"]),
            label=str(control["label"]),
            description=str(control["description"]),
            shadow_commands=tuple(
                GarminShadowCommand(
                    kind=str(command["kind"]),
                    parameters=_shadow_parameters_from_command(command),
                )
                for command in control["shadow_commands"]
            ),
        )
        for control in controls_input  # type: ignore[arg-type]
    )

    reason = _gate_reason(
        read_only_mode=read_only_mode,
        write_enable=write_enable,
        emergency_disable=emergency_disable,
    )
    return GarminSwitchBankProfile(
        bank_instance=int(template["bank_instance"]),
        bank_label=str(template["bank_label"]),
        status_pgn=int(template["status_pgn"]),
        control_pgn=int(template["control_pgn"]),
        controls=controls,
        write_eligible=reason == "eligible_if_policy_approved",
        gate_reason=reason,
    )


def _shadow_parameters_from_command(command: dict[str, object]) -> dict[str, object]:
    kind = str(command["kind"])
    if kind == "audio.set_volume":
        return {"zone": str(command["zone"]), "level": int(command["level"])}
    if kind == "audio.set_source":
        return {"source": str(command["source"])}
    if kind == "lighting.set_brightness":
        return {"zone": str(command["zone"]), "level": int(command["level"])}
    if kind == "lighting.set_color":
        rgb = command["rgb"]
        return {"zone": str(command["zone"]), "rgb": list(rgb)}  # type: ignore[arg-type]
    raise ValueError(f"unsupported command kind in template: {kind}")
