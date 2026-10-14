import ast
import unittest
from pathlib import Path


class M105DiagnosticsWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_path = (
            Path(__file__).resolve().parents[1]
            / "gui_creator_studio_m105_0_1.py"
        )
        cls.tree = ast.parse(
            cls.gui_path.read_text(encoding="utf-8"),
            filename=str(cls.gui_path),
        )
        cls.window = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "CreatorStudioWindow"
        )
        cls.methods = {
            node.name: node
            for node in cls.window.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_connect_provider_diagnostics_method_exists(self):
        self.assertIn("_connect_provider_diagnostics", self.methods)

    def test_init_calls_connect_provider_diagnostics(self):
        init = self.methods["__init__"]
        calls = [
            node.func.attr
            for node in ast.walk(init)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        ]
        self.assertIn("_connect_provider_diagnostics", calls)

    def test_diagnostics_signal_bindings_are_present(self):
        method = self.methods["_connect_provider_diagnostics"]
        source = ast.unparse(method)
        for expected in (
            "run_requested.connect",
            "action_requested.connect",
            "started.connect",
            "state_changed.connect",
            "fatal.connect",
            "finished.connect",
        ):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
