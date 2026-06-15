from pathlib import Path
import py_compile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StaticSmokeTests(unittest.TestCase):
    def test_main_script_compiles(self) -> None:
        py_compile.compile(str(ROOT / "hal_acentauri_hceres_poc.py"), doraise=True)

    def test_console_entry_point_targets_main(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(
            'hal-acentauri-hceres-poc = "hal_acentauri_hceres_poc:main"',
            pyproject,
        )

    def test_example_csv_files_are_present(self) -> None:
        self.assertTrue((ROOT / "data" / "acentauri_members.example.csv").is_file())
        self.assertTrue((ROOT / "data" / "theme_mapping.example.csv").is_file())


if __name__ == "__main__":
    unittest.main()
