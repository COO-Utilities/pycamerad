"""Unit tests for the Camerad driver, needing neither the extension nor hardware."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camerad import Camerad, ModuleNotAvailable, OutputStatus  # noqa: E402


class FakeCamera:
    """Records calls and replays canned replies, standing in for the extension."""

    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}

    def _record(self, name, args=""):
        self.calls.append((name, args))
        return self.replies.get(name, "")

    def open(self):
        return self._record("open")

    def close(self):
        return self._record("close")

    def load(self, args=""):
        return self._record("load", args)

    def power(self, args=""):
        return self._record("power", args)

    def exptime(self, args=""):
        return self._record("exptime", args)

    def expose(self, args=""):
        return self._record("expose", args)

    def abort(self, args=""):
        return self._record("abort", args)

    def basename(self, args=""):
        return self._record("basename", args)

    def datacube(self, args=""):
        return self._record("datacube", args)

    def key(self, args=""):
        return self._record("key", args)

    def native(self, args=""):
        return self._record("native", args)

    def instrument_cmd(self, command, args=""):
        self.calls.append((command, args))
        return self.replies.get(command, "")

    def controller_cmd(self, command, args=""):
        self.calls.append((command, args))
        return self.replies.get(command, "")

    def output_status(self):
        return self.replies.get("output_status", [])


class TestLifecycle(unittest.TestCase):
    """Connect, load and power."""

    def test_initialize_runs_open_load_and_power_on(self):
        camera = FakeCamera({"power": "ON"})
        Camerad(camera).initialize()
        self.assertEqual(
            camera.calls,
            [("open", ""), ("load", ""), ("power", "on")],
        )

    def test_power_query_sends_no_argument(self):
        camera = FakeCamera({"power": "ON"})
        self.assertTrue(Camerad(camera).power())
        self.assertEqual(camera.calls, [("power", "")])

    def test_power_off_is_reported_as_false(self):
        camera = FakeCamera({"power": "OFF"})
        self.assertFalse(Camerad(camera).power(False))
        self.assertEqual(camera.calls, [("power", "off")])


class TestExposure(unittest.TestCase):
    """Exposure time and counted exposures."""

    def test_exptime_returns_a_float(self):
        camera = FakeCamera({"exptime": "0.250"})
        self.assertEqual(Camerad(camera).exptime(), 0.25)

    def test_setting_exptime_sends_seconds(self):
        camera = FakeCamera({"exptime": "1.5"})
        Camerad(camera).exptime(1.5)
        self.assertEqual(camera.calls, [("exptime", "1.5")])

    def test_expose_defaults_to_one_frame(self):
        camera = FakeCamera()
        Camerad(camera).expose()
        self.assertEqual(camera.calls, [("expose", "1")])

    def test_expose_sends_the_count(self):
        camera = FakeCamera()
        Camerad(camera).expose(4)
        self.assertEqual(camera.calls, [("expose", "4")])


class TestOutput(unittest.TestCase):
    """Filenames, datacube state, FITS keys and output status."""

    def test_basename_round_trips(self):
        camera = FakeCamera({"basename": "scripted"})
        self.assertEqual(Camerad(camera).basename("scripted"), "scripted")
        self.assertEqual(camera.calls, [("basename", "scripted")])

    def test_datacube_parses_the_reply(self):
        self.assertTrue(Camerad(FakeCamera({"datacube": "true"})).datacube())
        self.assertFalse(Camerad(FakeCamera({"datacube": "false"})).datacube())

    def test_fits_key_is_formatted_with_its_comment(self):
        camera = FakeCamera()
        Camerad(camera).set_fits_key("OBSERVER", "Mike", "who ran it")
        self.assertEqual(camera.calls, [("key", "OBSERVER=Mike//who ran it")])

    def test_output_status_becomes_dataclasses(self):
        camera = FakeCamera({"output_status": [
            {"name": "fits", "frames_written": 3, "frames_dropped": 1,
             "last_written": "/tmp/a.fits"},
        ]})
        self.assertEqual(
            Camerad(camera).output_status(),
            [OutputStatus(name="fits", frames_written=3, frames_dropped=1,
                          last_written="/tmp/a.fits")],
        )


class TestBuildIdentity(unittest.TestCase):
    """Asserting which build was loaded."""

    def test_require_instrument_accepts_a_match(self):
        with mock.patch("camerad.instrument_name", return_value="hispec_tracking_camera"):
            Camerad(FakeCamera()).require_instrument("hispec_tracking_camera")

    def test_require_instrument_rejects_a_mismatch(self):
        with mock.patch("camerad.instrument_name", return_value="cryoscope"):
            with self.assertRaises(ModuleNotAvailable):
                Camerad(FakeCamera()).require_instrument("hispec_tracking_camera")

    def test_from_config_explains_a_missing_extension(self):
        class Absent(Camerad):
            """Bound to a module name that is never installed."""

            MODULE_NAME = "camera_interface_absent"

        with self.assertRaises(ModuleNotAvailable) as raised:
            Absent.from_config("/tmp/nothing.cfg")
        self.assertIn("camera_interface_absent", str(raised.exception))
        self.assertIn("pip install", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
