import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
reconfig_out = getattr(sys.stdout, 'reconfigure', None)
if callable(reconfig_out):
    reconfig_out(encoding='utf-8', line_buffering=True)
reconfig_err = getattr(sys.stderr, 'reconfigure', None)
if callable(reconfig_err):
    reconfig_err(encoding='utf-8', line_buffering=True)

from core.cli import handle_cli
from gui.app import run_app

if __name__ == "__main__":
    if not handle_cli(sys.argv):
        print("⚡ FalconDM Turbo Accelerator starting up...", flush=True)
        run_app()

