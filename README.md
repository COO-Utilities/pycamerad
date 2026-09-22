# pycamerad

Typed Python access to a camerad camera, in process, with no camerad daemon and
no text protocol in between.

Every command on camerad's `Camera::Interface` is string in and string out, so
`exptime("0")` answers `"0.000"` and `power("on")` answers `"ON"`. Converting
that to and from Python types is the same work for every instrument, so
`pycamerad` does it once.

## Prerequisite

This wraps `camera_interface`, a pybind11 module built from
[camera-interface](https://github.com/CaltechOpticalObservatories/camera-interface).
It is a compiled extension built per instrument rather than a package on an
index, so it cannot be a dependency here and has to be installed separately:

```bash
pip install <camera-interface> \
  --config-settings=cmake.define.INSTRUMENT=hispec_tracking_camera
```

`import camera_interface` then works with no `PYTHONPATH`, and `camerad` is on
`PATH` whenever the environment is active. pybind11 is fetched into an isolated
build environment, so it never has to be installed by hand. A compiler and
camerad's own libraries do have to be present; camera-interface's README lists
them.

The instrument is fixed when the module is built, so two instruments mean two
builds. Build them under different names with camera-interface's
`-DCAMERAD_MODULE_NAME=` and they can be installed side by side; a subclass
then names the one it needs:

```python
class TrackingCamera(Camerad):
    MODULE_NAME = "camera_interface_tracking"
```

`MODULE_NAME` defaults to `camera_interface`, and the module is imported on
first use rather than when pycamerad is imported. `instrument_name()` reports
which build got loaded, and takes a module name for anything but the default.

Without the module, `Camerad.from_config()` raises `ModuleNotAvailable` naming
the module and the command to run, rather than an ImportError from somewhere
deeper.

## Usage

```python
from pycamerad import Camerad, instrument_name

print(instrument_name())              # which build got loaded

camera = Camerad.from_config("hispecatc.cfg")
camera.require_instrument("hispec_tracking_camera")

camera.initialize()                   # open, load firmware, power on
camera.exptime(0.5)                   # -> 0.5
camera.expose(4)

print(camera.power())                 # -> True
print(camera.basename("science"))     # -> 'science'
print(camera.output_status())         # -> [OutputStatus(name='fits', ...)]
```

A failed command raises `RuntimeError` carrying camerad's reason.

`output_status()` is a snapshot, never a barrier. The FITS writer queues and
drops frames by design, because disk is slower than acquisition can be, so a
caller that needs to see a file polls this rather than waiting on the writer.

## Instrument commands

Commands that exist for only one instrument are deliberately absent. Subclass
`Camerad` and wrap `instrument_cmd` for those, so an instrument's vocabulary
lives with the instrument:

```python
class TrackingCamera(Camerad):
    def set_guiding_roi(self, y0, y1, x0, x1):
        self.instrument_cmd("roi", f"{y0} {y1} {x0} {x1}")

    def initialize(self):
        super().initialize()
        self.instrument_cmd("h2rg_init")
```

`instrument_commands()` enumerates what the loaded build actually handles, and
`controller_cmd()` reaches controller-specific commands such as `mode`, `raw`
and `heater`.

## Tests

The suite runs against a stand-in camera, so neither the extension nor
hardware is needed:

```bash
python -m unittest discover -s tests
```
