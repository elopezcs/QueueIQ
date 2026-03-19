import sys
from importlib import import_module
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

_api_main = import_module("API.main")
app = _api_main.app
create_app = _api_main.create_app



__all__ = ["app", "create_app"]