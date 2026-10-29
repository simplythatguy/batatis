"""Run with Python's standard-library unittest; no app or open ports needed."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "local-app.sh"
BASH = shutil.which("bash") or (
    "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "/bin/bash"
)


class DispatchTests(unittest.TestCase):
    def run_launcher(self, ostype, *args):
        with tempfile.TemporaryDirectory(prefix="local app dispatch ") as directory:
            root = Path(directory)
            (root / "local-app.sh").write_bytes(SCRIPT.read_bytes())
            (root / "local-app.ps1").touch()
            capture = root / "arguments.txt"
            for name, body in {
                "powershell.exe": 'printf "%s\\n" "$@" > "$CAPTURE"; exit 17',
                "cygpath": 'shift; printf "%s\\n" "$1"',
                "dirname": 'printf "%s\\n" "${1%/*}"',
            }.items():
                stub = root / name
                stub.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
                stub.chmod(0o755)
            env = dict(os.environ, CAPTURE=str(capture))
            result = subprocess.run(
                [BASH, "-c", 'PATH="$(cd "$1" && pwd)"; OSTYPE=$2; shift 2; source "$@"',
                 "dispatch-test", root.as_posix(), ostype,
                 (root / "local-app.sh").as_posix(), *args],
                env=env, text=True, capture_output=True, timeout=15,
            )
            forwarded = capture.read_text().splitlines() if capture.exists() else []
            return result, forwarded

    def test_windows_dispatches_before_unix_prerequisites_and_forwards_arguments(self):
        for platform in ("msys", "cygwin", "win32"):
            with self.subTest(platform=platform):
                result, args = self.run_launcher(platform, "wait", "0", "path with spaces")
                self.assertEqual(result.returncode, 17, result.stderr)
                self.assertEqual(args[-3:], ["wait", "0", "path with spaces"])
                self.assertIn("-File", args)
                self.assertTrue(args[args.index("-File") + 1].endswith("local-app.ps1"))
                self.assertNotIn("lsof", result.stderr)

    def test_unix_keeps_the_existing_prerequisite_check(self):
        # No Unix utilities are on PATH, even if the host has them installed.
        result, args = self.run_launcher("linux-gnu", "not-a-command")
        self.assertEqual(args, [])
        self.assertEqual(result.returncode, 2)
        self.assertIn("lsof is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
