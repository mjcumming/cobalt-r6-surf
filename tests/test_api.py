from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from cobalt_boat.api.app import create_app
from cobalt_boat.config import Settings


def make_settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    captures_dir = data_dir / "captures"
    log_path = tmp_path / "cobalt-boat.log"
    log_path.write_text("line1\nline2\n", encoding="utf-8")
    return Settings(
        api_host="127.0.0.1",
        api_port=8080,
        sqlite_path=data_dir / "cobalt_boat.db",
        data_dir=data_dir,
        capture_dir=captures_dir,
        app_log_path=log_path,
        can_interface="can0",
        decoder_backend="basic",
        allow_basic_decoder_insecure=True,
        read_only_mode=True,
        write_enable=False,
        emergency_disable=False,
    )


def test_health_endpoint(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["database_ready"] is True
    assert payload["ok"] in (True, False)
    assert payload["decoder_ready"] is True


def test_status_endpoint_defaults_to_read_only(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only_mode"] is True
    assert payload["write_enable"] is False
    assert payload["emergency_disable"] is False
    assert payload["can_interface"] == "can0"


def test_debug_endpoints(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        logs_response = client.get("/debug/logs?lines=10")
        events_response = client.get("/debug/events?limit=10")
        catalog_response = client.get("/debug/catalog?limit=10")
        watchlist_response = client.get("/debug/watchlist")
        page_response = client.get("/debug")
        root_response = client.get("/", follow_redirects=False)
        root_head_response = client.head("/", follow_redirects=False)
        debug_head_response = client.head("/debug")

    assert logs_response.status_code == 200
    lines = logs_response.json()["lines"]
    assert "line1" in lines
    assert "line2" in lines

    assert events_response.status_code == 200
    assert isinstance(events_response.json(), list)

    assert catalog_response.status_code == 200
    assert isinstance(catalog_response.json(), list)
    assert watchlist_response.status_code == 200
    assert isinstance(watchlist_response.json(), list)

    assert page_response.status_code == 200
    assert "Cobalt Boat Debug Console" in page_response.text
    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/debug"
    assert root_head_response.status_code == 307
    assert root_head_response.headers["location"] == "/debug"
    assert debug_head_response.status_code == 200


def test_shadow_command_preview_denied_in_read_only_mode(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/commands/preview",
            json={
                "kind": "lighting.set_brightness",
                "zone": "underwater",
                "level": 42,
                "correlation_id": "test-123",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "lighting"
    assert payload["command_name"] == "set_brightness"
    assert payload["approved"] is False
    assert payload["reason"] == "read_only_mode_enabled"
    assert payload["mode"] == "shadow_no_transmit"
    assert payload["write_transmitted"] is False

    with sqlite3.connect(settings.sqlite_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM command_audit").fetchone()[0]
    assert count >= 1


def test_shadow_command_validate_endpoint(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/commands/validate",
            json={
                "kind": "audio.set_volume",
                "zone": "cockpit",
                "level": 10,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "audio"
    assert payload["command_name"] == "set_volume"
    assert payload["approved"] is False
    assert payload["reason"] == "read_only_mode_enabled"


def test_watchlist_crud_endpoints(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        put_response = client.put(
            "/debug/watchlist/127501",
            json={"tag": "lighting-candidate", "note": "from research"},
        )
        list_response = client.get("/debug/watchlist")
        filtered_catalog_response = client.get("/debug/catalog?watch_only=true&limit=10")
        delete_response = client.delete("/debug/watchlist/127501")

    assert put_response.status_code == 200
    assert any(row["pgn"] == 127501 for row in put_response.json())
    assert list_response.status_code == 200
    assert any(row["pgn"] == 127501 for row in list_response.json())
    assert filtered_catalog_response.status_code == 200
    assert isinstance(filtered_catalog_response.json(), list)
    assert delete_response.status_code == 200
    assert all(row["pgn"] != 127501 for row in delete_response.json())


def test_garmin_switch_bank_profile_endpoint(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/debug/garmin/switch-bank")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status_pgn"] == 127501
    assert payload["control_pgn"] == 127502
    assert payload["write_eligible"] is False
    assert payload["gate_reason"] == "read_only_mode_enabled"
    assert len(payload["controls"]) >= 1
    assert payload["controls"][0]["shadow_commands"][0]["kind"].startswith("lighting.")


def test_garmin_switch_bank_template_update_roundtrip(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        template_before = client.get("/debug/garmin/switch-bank/template")
        assert template_before.status_code == 200
        profile = template_before.json()
        profile["bank_label"] = "Cobalt Virtual Scenes"
        profile["controls"][0]["label"] = "Evening Relax"

        put_response = client.put(
            "/debug/garmin/switch-bank",
            json={
                "operator": "tester",
                "reason": "rename scene",
                "profile": profile,
            },
        )
        template_after = client.get("/debug/garmin/switch-bank/template")
        events = client.get("/debug/events?limit=20")

    assert put_response.status_code == 200
    payload = put_response.json()
    assert payload["bank_label"] == "Cobalt Virtual Scenes"
    assert payload["controls"][0]["label"] == "Evening Relax"
    assert payload["write_eligible"] is False
    assert template_after.status_code == 200
    assert template_after.json()["bank_label"] == "Cobalt Virtual Scenes"
    assert events.status_code == 200
    assert any(row["event_type"] == "garmin_switch_bank_profile_updated" for row in events.json())


def test_garmin_switch_bank_template_rejects_bad_pgn(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.put(
            "/debug/garmin/switch-bank",
            json={
                "operator": "tester",
                "reason": "invalid pgn",
                "profile": {
                    "bank_instance": 1,
                    "bank_label": "Invalid",
                    "status_pgn": 123,
                    "control_pgn": 127502,
                    "controls": [
                        {
                            "instance": 1,
                            "label": "Evening",
                            "description": "desc",
                            "shadow_commands": [
                                {"kind": "lighting.set_brightness", "zone": "cockpit", "level": 10}
                            ],
                        }
                    ],
                },
            },
        )

    assert response.status_code == 422


def _can_id_from_pgn(pgn: int, source: int = 1, dest: int = 32, priority: int = 6) -> int:
    data_page = (pgn >> 16) & 0x1
    pdu_format = (pgn >> 8) & 0xFF
    if pdu_format < 240:
        pdu_specific = dest & 0xFF
    else:
        pdu_specific = pgn & 0xFF
    return (
        ((priority & 0x7) << 26)
        | ((data_page & 0x1) << 24)
        | ((pdu_format & 0xFF) << 16)
        | ((pdu_specific & 0xFF) << 8)
        | (source & 0xFF)
    )


def test_capture_annotations_and_fusion_correlation(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    app = create_app(settings)

    session_id = "20260321T150000000000Z"
    capture_file = settings.capture_dir / f"capture_{session_id}.jsonl"
    capture_file.parent.mkdir(parents=True, exist_ok=True)

    action_at = datetime(2026, 3, 21, 15, 0, 0, tzinfo=timezone.utc)
    rows = []
    for idx, pgn in enumerate([126208, 59392, 130582]):
        rows.append(
            {
                "timestamp": (action_at + timedelta(seconds=idx)).isoformat(),
                "can_id": _can_id_from_pgn(pgn),
                "is_extended_id": True,
                "dlc": 8,
                "data_hex": "0102030405060708",
                "channel": "vcan0",
            }
        )
    capture_file.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    with TestClient(app) as client:
        create_response = client.post(
            f"/debug/captures/{session_id}/annotations",
            json={
                "action_label": "volume_up",
                "action_at": action_at.isoformat(),
                "note": "manual action",
                "operator": "tester",
            },
        )
        list_response = client.get(f"/debug/captures/{session_id}/annotations")
        report_response = client.get(f"/debug/fusion/correlation?session_id={session_id}&window_sec=5")

    assert create_response.status_code == 200
    assert len(create_response.json()) == 1
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert report_response.status_code == 200
    payload = report_response.json()
    assert payload["matches"] == 1
    assert payload["confidence"] == "low"
    assert payload["results"][0]["chain_matched"] is True
