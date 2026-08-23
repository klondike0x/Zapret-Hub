"""Regression tests for WinDivert service state parsing (locale-independent)."""

from __future__ import annotations

import re
from types import SimpleNamespace

from zapret_hub.services.components import ProcessManager

# Fields in `sc query` output are localized on non-English Windows (e.g. Russian
# "СОСТОЯНИЕ" instead of "STATE"), but the numeric state code and the trailing
# English state word ("RUNNING"/"STOPPED"/...) stay constant. The parser must key
# off the numeric code, and must not confuse other "code + word" fields like
# "TYPE : 1  KERNEL_DRIVER".

_SERVICE_NAME = "WinDivert"

_STATE_FIELDS = {
    "RUNNING": "4  RUNNING",
    "STOPPED": "1  STOPPED",
    "START_PENDING": "2  START_PENDING",
    "STOP_PENDING": "3  STOP_PENDING",
    "CONTINUE_PENDING": "5  CONTINUE_PENDING",
    "PAUSE_PENDING": "6  PAUSE_PENDING",
    "PAUSED": "7  PAUSED",
}


def _service_status_from_output(stdout: str) -> str:
    """Run ProcessManager._service_status against a fake `sc query` output."""
    manager = ProcessManager.__new__(ProcessManager)

    def fake_run_quiet(command):
        return SimpleNamespace(returncode=0, stdout=stdout)

    manager._run_quiet = fake_run_quiet
    return manager._service_status(_SERVICE_NAME)


def _build_output(state_word: str, *, label: str = "STATE", with_type_field: bool = True) -> str:
    lines = [f"SERVICE_NAME: {_SERVICE_NAME}"]
    if with_type_field:
        lines.append("        TYPE               : 1  KERNEL_DRIVER")
    lines.append(f"        {label:<16}: {_STATE_FIELDS[state_word]}")
    lines.append("                        (NOT_STOPPABLE, NOT_PAUSABLE, IGNORES_SHUTDOWN)")
    lines.append("        WIN32_EXIT_CODE    : 0  (0x0)")
    lines.append("        SERVICE_EXIT_CODE  : 0  (0x0)")
    lines.append("        CHECKPOINT         : 0x0")
    lines.append("        WAIT_HINT          : 0x0")
    return "\n".join(lines) + "\n"


def test_service_status_parses_numeric_code_running() -> None:
    assert _service_status_from_output(_build_output("RUNNING")) == "RUNNING"


def test_service_status_parses_numeric_code_stopped() -> None:
    assert _service_status_from_output(_build_output("STOPPED")) == "STOPPED"


def test_service_status_ignores_localized_state_label() -> None:
    # Russian Windows localizes the label but keeps ": 4  RUNNING".
    assert _service_status_from_output(_build_output("RUNNING", label="СОСТОЯНИЕ")) == "RUNNING"


def test_service_status_does_not_confuse_type_field_with_state() -> None:
    # "TYPE : 1  KERNEL_DRIVER" must not make a RUNNING service look STOPPED.
    assert _service_status_from_output(_build_output("RUNNING", with_type_field=True)) == "RUNNING"


def test_service_status_absent_on_nonzero_exit() -> None:
    manager = ProcessManager.__new__(ProcessManager)

    def fake_run_quiet(command):
        return SimpleNamespace(returncode=1060, stdout="[SC] OpenService FAILED 1060")

    manager._run_quiet = fake_run_quiet
    assert manager._service_status(_SERVICE_NAME) == "ABSENT"


def test_service_status_unknown_without_recognized_state() -> None:
    assert _service_status_from_output("SERVICE_NAME: WinDivert\n") == "UNKNOWN"


def test_state_code_regex_does_not_match_hex_fields() -> None:
    # CHECKPOINT : 0x0 / WAIT_HINT : 0x0 are hex, not "code + state word".
    pattern = re.compile(r":\s*(\d+)\s+([A-Z_]+)")
    for line in ("CHECKPOINT         : 0x0", "WAIT_HINT          : 0x0"):
        assert pattern.search(line.upper()) is None
