"""Make the project importable and stub the heavy ADK/GCP SDKs.

The pure-Python units we test (feed parsing, JSON extraction) do not need
google-adk or the Google Cloud SDKs installed. We import the modules under
test directly by file path so importing them never triggers the package
__init__ chain that pulls in those SDKs.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_module(relpath: str, name: str):
    """Import a single source file in isolation, bypassing package __init__."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
