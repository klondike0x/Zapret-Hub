"""Regression tests for the BackendWorkerClient shutdown handshake race.

A GUI-owned QTimer can fire _poll_results() concurrently with stop() running on
a shutdown thread. The shutdown ack must never be lost: whichever consumer
drains it, stop() must still converge and report the true result instead of
raising the alarming "cleanup failed" dialog.
"""

from __future__ import annotations

import queue
import threading
import time

import pytest

from zapret_hub.services.backend_worker import BackendWorkerClient

pytest.importorskip("PySide6")


class _FakeQueue:
    """Single-consumer-safe fake for the multiprocessing result queue."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[dict]" = queue.Queue()

    def put(self, item: dict) -> None:
        self._queue.put(item)

    def get_nowait(self) -> dict:
        return self._queue.get_nowait()

    def get(self, timeout: float) -> dict:
        return self._queue.get(timeout=timeout)


class _FakeProcess:
    def __init__(self, alive: bool = False) -> None:
        self._alive = alive
        self.terminated = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        # The worker "exits" as soon as shutdown is processed.
        self._alive = False

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False


def _make_client(*, alive: bool = True) -> BackendWorkerClient:
    client = BackendWorkerClient.__new__(BackendWorkerClient)
    # Bypass __init__: no real spawned process, no QTimer/QApplication needed.
    client._task_queue = _FakeQueue()
    client._result_queue = _FakeQueue()
    client._process = _FakeProcess(alive=alive)
    client._polling_enabled = True
    client._shutdown_lock = threading.Lock()
    client._seen_shutdown = {}
    client._stop_lock = threading.Lock()
    client._stop_result = None
    client._last_stop_error = ""
    client._pending_tasks = set()
    client._cancel_paths = {}
    client._poll_timer = None
    return client


def test_stop_sees_ack_drained_by_concurrent_poll() -> None:
    """If _poll_results beats stop() to the queue, stop() still reports success."""
    client = _make_client()

    def poll_on_gui_thread() -> None:
        for _ in range(50):
            try:
                message = client._result_queue.get_nowait()
            except queue.Empty:
                time.sleep(0.01)
                continue
            if message.get("action") == "shutdown":
                with client._shutdown_lock:
                    client._seen_shutdown[message["id"]] = bool(message.get("ok"))
                break

    gui_thread = threading.Thread(target=poll_on_gui_thread, daemon=True)

    def fake_put(item):
        def reply() -> None:
            time.sleep(0.05)
            client._result_queue.put(
                {
                    "id": item["id"],
                    "action": "shutdown",
                    "ok": True,
                    "error": "",
                    "payload": {"shutdown": {"ok": True}},
                }
            )

        threading.Thread(target=reply, daemon=True).start()

    client._task_queue.put = fake_put  # type: ignore[method-assign]

    import zapret_hub.services.backend_worker as mod

    orig = mod.QMetaObject.invokeMethod
    mod.QMetaObject.invokeMethod = lambda *args, **kwargs: True  # type: ignore[attr-defined]
    try:
        gui_thread.start()
        result = client.stop(timeout=15.0)
        gui_thread.join(timeout=2)
    finally:
        mod.QMetaObject.invokeMethod = orig  # type: ignore[attr-defined]

    assert result is True
    assert client._last_stop_error == ""


def test_stop_reuses_completed_result_without_second_handshake() -> None:
    client = _make_client()
    shutdown_requests = []

    def acknowledge(item):
        shutdown_requests.append(item)
        client._result_queue.put(
            {
                "id": item["id"],
                "action": "shutdown",
                "ok": True,
                "error": "",
                "payload": {"shutdown": {"ok": True}},
            }
        )

    client._task_queue.put = acknowledge  # type: ignore[method-assign]

    import zapret_hub.services.backend_worker as mod

    original = mod.QMetaObject.invokeMethod
    mod.QMetaObject.invokeMethod = lambda *args, **kwargs: True  # type: ignore[attr-defined]
    try:
        assert client.stop(timeout=15.0) is True
        assert client.stop(timeout=15.0) is True
    finally:
        mod.QMetaObject.invokeMethod = original  # type: ignore[attr-defined]

    assert len(shutdown_requests) == 1


def test_stop_reports_failure_when_worker_never_exits() -> None:
    client = _make_client(alive=True)
    client._process._alive = True
    client._process.join = lambda timeout=None: None  # type: ignore[assignment]
    result = client.stop(timeout=0.0)
    assert result is False
    assert "did not stop" in client._last_stop_error


def test_stop_returns_false_when_task_put_fails() -> None:
    client = _make_client()

    def failing_put(item):
        raise OSError("queue closed")

    client._task_queue.put = failing_put  # type: ignore[method-assign]
    assert client.stop(timeout=15.0) is False


def test_poll_results_records_shutdown_ack_without_emitting_tasks() -> None:
    client = _make_client()

    class _FakeSignal:
        def __init__(self) -> None:
            self.values = []

        def emit(self, value):
            self.values.append(value)

    class _FakeTimer:
        def __init__(self) -> None:
            self.active = False

        def isActive(self) -> bool:
            return self.active

        def stop(self) -> None:
            self.active = False

    client.task_finished = _FakeSignal()  # type: ignore[assignment]
    client.task_failed = _FakeSignal()  # type: ignore[assignment]
    client.task_progress = _FakeSignal()  # type: ignore[assignment]
    client._poll_timer = _FakeTimer()  # type: ignore[assignment]

    client._result_queue.put({"id": "shut1", "action": "shutdown", "ok": True, "error": ""})
    client._poll_results()

    assert client.task_finished.values == []  # type: ignore[attr-defined]
    assert client.task_failed.values == []  # type: ignore[attr-defined]
    assert client.task_progress.values == []  # type: ignore[attr-defined]
    with client._shutdown_lock:
        assert client._seen_shutdown.get("shut1") is True
