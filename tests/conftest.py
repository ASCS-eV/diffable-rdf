import os
import pathlib

# Several tests assert determinism across *processes* and therefore spawn a
# fresh interpreter with subprocess.run(). pytest's `pythonpath` ini option
# only extends sys.path in this process, so those children would not find
# diffable_rdf unless the package happens to be installed. Exporting it here
# is what lets `pytest` work from a clean checkout with no install; when the
# package *is* installed, or PYTHONPATH already covers src/, this is a no-op.
_SRC = str(pathlib.Path(__file__).resolve().parent.parent / "src")
_existing = os.environ.get("PYTHONPATH", "")
if _SRC not in _existing.split(os.pathsep):
    os.environ["PYTHONPATH"] = os.pathsep.join([_SRC, _existing]) if _existing else _SRC
