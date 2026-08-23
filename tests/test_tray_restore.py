import unittest
from pathlib import Path


WINDOW_SOURCE = Path(__file__).parents[1] / "src" / "zapret_hub" / "ui" / "web_window.py"


class TrayRestoreTests(unittest.TestCase):
    def test_restore_shows_an_opaque_window_before_waking_webengine(self) -> None:
        source = WINDOW_SOURCE.read_text(encoding="utf-8")
        restore = source.split("    def restore_from_external_launch", 1)[1].split(
            "    def _resume_web_view_after_tray", 1
        )[0]

        self.assertIn("self.setWindowOpacity(1.0)", restore)
        self.assertNotIn("self.setWindowOpacity(0.0)", restore)
        self.assertLess(restore.index("self.setWindowOpacity(1.0)"), restore.index("self.show()"))
        self.assertIn("self._resume_web_view_after_tray()", restore)
        self.assertNotIn("emit_state(force=True)", restore)

    def test_restore_wakes_the_existing_webengine_page(self) -> None:
        source = WINDOW_SOURCE.read_text(encoding="utf-8")
        helper = source.split("    def _resume_web_view_after_tray", 1)[1].split("    def showEvent", 1)[0]

        self.assertIn("page.setLifecycleState(active)", helper)
        self.assertIn("requestAnimationFrame", helper)
        self.assertIn("QTimer.singleShot(80, _refresh_compositor)", helper)

    def test_exit_from_tray_keeps_a_bounded_shutdown_deadline(self) -> None:
        source = WINDOW_SOURCE.read_text(encoding="utf-8")
        exit_fn = source.split("    def _exit_from_tray", 1)[1].split("    def _dismantle_ui_immediately", 1)[0]
        force_exit_fn = source.split("    def _force_exit_on_stalled_shutdown", 1)[1].split("    def _dismantle_ui_immediately", 1)[0]

        # Graceful cleanup is preserved (non-daemon wait for WinDivert/backend).
        self.assertIn("threading.Thread(target=shutdown, daemon=False", exit_fn)
        self.assertIn('name="zapret-hub-shutdown"', exit_fn)
        # ...but a hang in untimed cleanup subprocesses must not strand the app.
        self.assertIn("self._shutdown_watchdog = QTimer(self)", exit_fn)
        self.assertIn("os._exit(0)", force_exit_fn)
        self.assertIn("shutdown_done.is_set()", force_exit_fn)


if __name__ == "__main__":
    unittest.main()
