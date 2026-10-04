"""Tests run against a throw-away data directory and never call the network."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="investigator-tests-")
os.environ["LLM_MODE"] = "mock"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
