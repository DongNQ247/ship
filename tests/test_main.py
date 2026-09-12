import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as ship
from tools import paths, shell
from tools.templates import DEFAULT_ALLOWED, DEFAULT_PROTECTED


class ShipMainUnitTests(unittest.TestCase):
    def setUp(self):
        self.orig_cwd = Path.cwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name).resolve()
        self.ship_dir = self.test_root / ".ship"
        self.guardrail_dir = self.ship_dir / "guardrails"
        self.state_dir = self.ship_dir / "state"

        self.guardrail_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        (self.guardrail_dir / "allowed").write_text(DEFAULT_ALLOWED, encoding="utf-8")
        (self.guardrail_dir / "protected").write_text(DEFAULT_PROTECTED, encoding="utf-8")
        (self.guardrail_dir / "deny").write_text(".env\n", encoding="utf-8")
        (self.state_dir / "files").write_text("", encoding="utf-8")
        (self.test_root / "README.md").write_text("# Test", encoding="utf-8")

        os.chdir(self.test_root)
        self.ctx = paths.ShipContext(self.test_root)
        paths.set_context(self.ctx)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        paths.set_context(None)
        self.temp_dir.cleanup()

    def test_remote_dir_validation_rejects_traversal(self):
        with self.assertRaises(ship.DeployError):
            ship.validate_remote_dir("/home/app/../../etc")

    def test_remote_dir_validation_allows_project_path(self):
        ship.validate_remote_dir("/home/app/dongnq7")

    def test_host_validation_rejects_shell_characters(self):
        with self.assertRaises(ship.DeployError):
            ship.validate_server_host("example.com;id")

    def test_normalize_path_rejects_escape(self):
        with self.assertRaises(ship.DeployError):
            ship.normalize_path("../outside_project")

    def test_normalize_path_rejects_control_characters(self):
        with self.assertRaises(ship.DeployError):
            ship.normalize_path("README.md\n.env")

    def test_validate_staged_item_rejects_secret_path(self):
        with self.assertRaises(ship.DeployError):
            ship.validate_staged_item(".env")

    def test_validate_staged_item_allows_regular_project_file(self):
        self.assertEqual(ship.validate_staged_item("README.md"), "README.md")

    def test_expand_paths_rejects_ignored_path(self):
        (self.test_root / ".shipignore").write_text("temp_test_ignored.txt\n", encoding="utf-8")
        (self.test_root / "temp_test_ignored.txt").write_text("dummy", encoding="utf-8")

        with self.assertRaises(ship.DeployError) as cm:
            ship.expand_paths(["temp_test_ignored.txt"])
        self.assertIn("ignored by .shipignore", str(cm.exception))

        # Can force stage with force=True
        self.assertEqual(ship.expand_paths(["temp_test_ignored.txt"], force=True), ["temp_test_ignored.txt"])

    def test_expand_paths_recursively_expands_directory(self):
        sub = self.test_root / "src" / "components"
        sub.mkdir(parents=True)
        (sub / "Button.jsx").write_text("export default Button;", encoding="utf-8")
        (sub / "Header.jsx").write_text("export default Header;", encoding="utf-8")
        (self.test_root / ".shipignore").write_text("*.log\n", encoding="utf-8")
        (sub / "debug.log").write_text("log", encoding="utf-8")

        expanded = ship.expand_paths(["src"])
        self.assertEqual(expanded, ["src/components/Button.jsx", "src/components/Header.jsx"])

    def test_find_project_root_locates_ship_directory(self):
        sub_dir = self.test_root / "src" / "deep"
        sub_dir.mkdir(parents=True)
        self.assertEqual(paths.find_project_root(sub_dir), self.test_root)

    def test_ssh_exec_script_uses_remote_positional_separator(self):
        captured = {}

        def fake_run(argv, *, input_text=None, capture=False):
            captured["argv"] = argv
            captured["input_text"] = input_text
            captured["capture"] = capture
            return subprocess.CompletedProcess(argv, 0, "")

        with patch.object(shell, "run_command", side_effect=fake_run):
            config = ship.Config("example.com", 2222, "app", "/home/app/project")
            ship.ssh_exec_script(config, 'echo "$1"', "/home/app/project", capture=True)

        self.assertEqual(captured["argv"][:6], ["ssh", "-p", "2222", "-o", "ConnectTimeout=10", "app@example.com"])
        self.assertEqual(captured["argv"][6], "bash -se -- /home/app/project")
        self.assertEqual(captured["input_text"], 'echo "$1"')
        self.assertTrue(captured["capture"])


if __name__ == "__main__":
    unittest.main()
