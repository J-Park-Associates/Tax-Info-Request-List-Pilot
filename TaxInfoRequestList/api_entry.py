"""PyInstaller entry point for the portable demo's tracker API."""
import sys
from tracker.api import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
