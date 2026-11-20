import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load_script(name: str):
    """Import scripts/<name>.py, which is a plain file, not part of a package."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module
