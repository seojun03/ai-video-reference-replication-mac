"""Include shipped pause regressions in the existing publisher and macOS CI suite."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "skills/capcut-cut-edit/tests/test_pause_audit.py"
spec = importlib.util.spec_from_file_location("shipped_pause_audit_tests", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PauseAuditTests = module.PauseAuditTests
