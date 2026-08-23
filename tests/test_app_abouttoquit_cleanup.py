import unittest
from pathlib import Path

APP_SOURCE = Path(__file__).parents[1] / "src" / "zapret_hub" / "app.py"


class AppShutdownBoundTests(unittest.TestCase):
    def test_about_to_quit_direct_cleanup_is_bounded_and_async(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")
        cleanup = source.split("def _cleanup_before_quit() -> None:", 1)[1].split("app.aboutToQuit.connect", 1)[0]

        # The direct (backend-not-attached) path must not run stop_all() on the
        # GUI thread synchronously; it delegates to the bounded helper.
        self.assertIn("_start_bounded_direct_cleanup(context)", cleanup)

    def test_direct_cleanup_runs_on_background_thread_with_deadline(self) -> None:
        source = APP_SOURCE.read_text(encoding="utf-8")
        helper = source.split("def _start_bounded_direct_cleanup(context) -> None:", 1)[1].split("app.aboutToQuit.connect", 1)[0]

        # stop_all() is executed off the GUI thread...
        self.assertIn("threading.Thread(target=_bounded_stop", helper)
        self.assertIn('name="zapret-hub-abouttoquit-cleanup"', helper)
        # ...and a Qt-independent hard deadline force-exits if it stalls.
        self.assertIn("threading.Timer(30.0, _force_exit_if_stalled)", helper)
        self.assertIn("os._exit(0)", helper)
        self.assertIn("stop_cleanup_done.is_set()", helper)


if __name__ == "__main__":
    unittest.main()
