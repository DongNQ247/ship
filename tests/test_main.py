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

        # Un-ignore via ! pattern in .shipignore
        (self.test_root / ".shipignore").write_text("temp_test_ignored.txt\n!temp_test_ignored.txt\n", encoding="utf-8")
        self.assertEqual(ship.expand_paths(["temp_test_ignored.txt"]), ["temp_test_ignored.txt"])

    def test_expand_paths_recursively_expands_directory(self):
        sub = self.test_root / "src" / "components"
        sub.mkdir(parents=True)
        (sub / "Button.jsx").write_text("export default Button;", encoding="utf-8")
        (sub / "Header.jsx").write_text("export default Header;", encoding="utf-8")
        (self.test_root / ".shipignore").write_text("*.log\n", encoding="utf-8")
        (sub / "debug.log").write_text("log", encoding="utf-8")

        expanded = ship.expand_paths(["src"])
        self.assertEqual(expanded, ["src/components/Button.jsx", "src/components/Header.jsx"])

    def test_expand_paths_ignores_folder_patterns(self):
        # Create nested folders
        (self.test_root / "folder").mkdir()
        (self.test_root / "folder" / "a.txt").write_text("a", encoding="utf-8")

        (self.test_root / "sub" / "nested_folder").mkdir(parents=True)
        (self.test_root / "sub" / "nested_folder" / "b.txt").write_text("b", encoding="utf-8")

        (self.test_root / "valid").mkdir()
        (self.test_root / "valid" / "c.txt").write_text("c", encoding="utf-8")

        (self.test_root / ".shipignore").write_text("folder/\n*/nested_folder/\n", encoding="utf-8")

        expanded = ship.expand_paths(["."])
        self.assertIn("valid/c.txt", expanded)
        self.assertNotIn("folder/a.txt", expanded)
        self.assertNotIn("sub/nested_folder/b.txt", expanded)

    def test_push_auto_skips_ignored_items(self):
        (self.test_root / "app.py").write_text("print(1)", encoding="utf-8")
        (self.test_root / "debug.log").write_text("log", encoding="utf-8")

        # Stage both items
        ship.write_staging(["app.py", "debug.log"])

        # Add debug.log to ignore AFTER staging
        (self.test_root / ".shipignore").write_text("*.log\n", encoding="utf-8")

        tmp, count = ship.validated_staging_tempfile()
        try:
            content = Path(tmp.name).read_text(encoding="utf-8").splitlines()
            self.assertEqual(content, ["app.py"])
            self.assertEqual(count, 1)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_gitignore_negation_and_advanced_wildcards(self):
        # Create files
        (self.test_root / "app.log").write_text("log1", encoding="utf-8")
        (self.test_root / "important.log").write_text("log2", encoding="utf-8")
        sub = self.test_root / "deep" / "nested" / "pkg"
        sub.mkdir(parents=True)
        (sub / "code.ts").write_text("ts", encoding="utf-8")
        (sub / "code.js").write_text("js", encoding="utf-8")

        # shipignore with negation & double asterisk
        (self.test_root / ".shipignore").write_text("*.log\n!important.log\n**/*.ts\n", encoding="utf-8")

        expanded = ship.expand_paths(["."])
        self.assertIn("important.log", expanded)
        self.assertNotIn("app.log", expanded)
        self.assertNotIn("deep/nested/pkg/code.ts", expanded)
        self.assertIn("deep/nested/pkg/code.js", expanded)

    def test_expand_paths_ignores_nested_node_modules_and_venv(self):
        # Create nested client/node_modules and server/.venv
        pkg = self.test_root / "client" / "node_modules" / "commander"
        pkg.mkdir(parents=True)
        (pkg / "CHANGELOG.md").write_text("changelog", encoding="utf-8")
        (pkg / "LICENSE").write_text("license", encoding="utf-8")

        venv = self.test_root / "server" / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "activate").write_text("source", encoding="utf-8")

        src = self.test_root / "client" / "src"
        src.mkdir(parents=True)
        (src / "App.tsx").write_text("export default App;", encoding="utf-8")

        from tools.templates import DEFAULT_SHIPIGNORE
        (self.test_root / ".shipignore").write_text(DEFAULT_SHIPIGNORE, encoding="utf-8")

        expanded = ship.expand_paths(["."])
        self.assertIn("client/src/App.tsx", expanded)
        self.assertNotIn("client/node_modules/commander/CHANGELOG.md", expanded)
        self.assertNotIn("client/node_modules/commander/LICENSE", expanded)
        self.assertNotIn("server/.venv/bin/activate", expanded)

    def test_command_reset_clears_all_or_specific_paths(self):
        import argparse
        (self.test_root / "a.py").write_text("a", encoding="utf-8")
        (self.test_root / "b.py").write_text("b", encoding="utf-8")
        (self.test_root / "c.py").write_text("c", encoding="utf-8")
        ship.write_staging(["a.py", "b.py", "c.py"])

        # Unstage specific file
        ship.command_reset(argparse.Namespace(paths=["b.py"]))
        self.assertEqual(ship.read_staged_items(), ["a.py", "c.py"])

        # Reset all staging
        ship.command_reset(argparse.Namespace(paths=[]))
        self.assertEqual(ship.read_staged_items(), [])

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
