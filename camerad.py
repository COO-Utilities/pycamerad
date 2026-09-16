"""Typed access to a camerad camera through the camera_interface module.

Every command on ``Camera::Interface`` is string in and string out, so
``exptime("0")`` answers ``"0.000"`` and ``power("on")`` answers ``"ON"``.
Converting that to and from Python types is the same work for every
instrument, so it happens here once.

Instrument-specific commands are deliberately absent. Subclass ``Camerad`` and
wrap :meth:`Camerad.instrument_cmd` for those.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

try:
    import camera_interface
except ImportError as exc:
    camera_interface = None
    _IMPORT_ERROR: Optional[ImportError] = exc
else:
    _IMPORT_ERROR = None


class ModuleNotAvailable(RuntimeError):
    """Raised when the camera_interface extension cannot be imported."""


@dataclass(frozen=True)
class OutputStatus:
    """A snapshot of what one frame output has done so far."""

    name: str
    frames_written: int
    frames_dropped: int
    last_written: str


def _require_module() -> Any:
    """Return the camera_interface module, or explain why it is missing."""
    if camera_interface is None:
        raise ModuleNotAvailable(
            "camera_interface is not importable. Install it into this "
            "environment from a camera-interface checkout: pip install "
            "<camera-interface> "
            "--config-settings=cmake.define.INSTRUMENT=<instrument>"
        ) from _IMPORT_ERROR
    return camera_interface


def instrument_name() -> str:
    """Return the instrument the loaded module was built for."""
    return _require_module().instrument_name()


def controller_name() -> str:
    """Return the controller the loaded module was built for."""
    return _require_module().controller_name()


def _on_off(value: bool) -> str:
    return "on" if value else "off"


def _true_false(value: bool) -> str:
    return "true" if value else "false"


class Camerad:
    """A camerad camera, with its commands as typed methods.

    Construct with :meth:`from_config` for normal use. The constructor takes an
    already-built camera so a test can pass a stand-in.
    """

    def __init__(self, camera: Any) -> None:
        self._camera = camera

    @classmethod
    def from_config(cls, config_path: str,
                    log_to_stderr: Optional[bool] = None) -> "Camerad":
        """Build a camera from a camerad .cfg file.

        Reads the config, initialises logging, and runs the same configure
        steps camerad does at startup. It does not connect; call
        :meth:`open` or :meth:`initialize` for that.
        """
        module = _require_module()
        return cls(module.Camera(config_path, log_to_stderr=log_to_stderr))

    @property
    def camera(self) -> Any:
        """Return the underlying camera_interface.Camera."""
        return self._camera

    ### lifecycle

    def open(self) -> None:
        """Connect to the controller."""
        self._camera.open()

    def close(self) -> None:
        """Disconnect from the controller."""
        self._camera.close()

    def load(self, firmware: str = "") -> None:
        """Load firmware, defaulting to DEFAULT_FIRMWARE from the config."""
        self._camera.load(firmware)

    def power(self, on: Optional[bool] = None) -> bool:
        """Query whether power is on, or set it, returning the resulting state."""
        reply = self._camera.power("" if on is None else _on_off(on))
        return reply.strip().upper() == "ON"

    def initialize(self) -> None:
        """Connect, load firmware, and power on.

        Instruments needing more, such as a detector reset, extend this.
        """
        self.open()
        self.load()
        self.power(True)

    ### exposure

    def exptime(self, seconds: Optional[float] = None) -> float:
        """Query the exposure time in seconds, or set it."""
        reply = self._camera.exptime("" if seconds is None else f"{float(seconds)}")
        return float(reply)

    def expose(self, count: int = 1) -> None:
        """Take one exposure, or a counted series."""
        self._camera.expose(str(int(count)))

    def abort(self) -> None:
        """Abort the exposure in progress."""
        self._camera.abort()

    ### output

    def basename(self, name: Optional[str] = None) -> str:
        """Query the image base filename, or set it."""
        return self._camera.basename("" if name is None else name).strip()

    def datacube(self, enabled: Optional[bool] = None) -> bool:
        """Query whether frames are written as a datacube, or set it."""
        reply = self._camera.datacube("" if enabled is None else _true_false(enabled))
        return reply.strip().lower() == "true"

    def set_fits_key(self, name: str, value: str, comment: str = "") -> None:
        """Add or replace a user FITS header key."""
        self._camera.key(f"{name}={value}//{comment}")

    def output_status(self) -> List[OutputStatus]:
        """Return a snapshot of every configured frame output.

        A snapshot and not a barrier: the FITS writer queues and drops frames
        by design, so a caller wanting to see a file poll this rather than
        waiting on the writer.
        """
        return [OutputStatus(name=entry["name"],
                             frames_written=entry["frames_written"],
                             frames_dropped=entry["frames_dropped"],
                             last_written=entry["last_written"])
                for entry in self._camera.output_status()]

    ### escape hatches

    def native(self, command: str) -> str:
        """Send a raw command straight to the controller."""
        return self._camera.native(command)

    def instrument_cmd(self, command: str, args: str = "") -> str:
        """Run an instrument-specific command."""
        return self._camera.instrument_cmd(command, args)

    def controller_cmd(self, command: str, args: str = "") -> str:
        """Run a controller-specific command such as mode, raw or heater."""
        return self._camera.controller_cmd(command, args)

    ### introspection

    def instrument_commands(self) -> List[str]:
        """Return the instrument-specific command names this build supports."""
        return self._camera.instrument_commands()

    def is_instrument_command(self, command: str) -> bool:
        """Return True if this build's instrument handles the named command."""
        return self._camera.is_instrument_command(command)

    def exposure_modes(self) -> List[str]:
        """Return the exposure mode names this build supports."""
        return self._camera.exposure_modes()

    def require_instrument(self, expected: str) -> None:
        """Raise unless the loaded module was built for the expected instrument."""
        actual = instrument_name()
        if actual != expected:
            raise ModuleNotAvailable(
                f"camera_interface was built for instrument {actual!r}, "
                f"but {expected!r} is required"
            )
