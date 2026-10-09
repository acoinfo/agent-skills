#!/usr/bin/env python3
"""封装回归测试：只操作临时目录/本地子进程，不修改系统或真实设备。"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock
import zipfile

spec = importlib.util.spec_from_file_location("realevo_cli", Path(__file__).with_name("cli.py"))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CliTests(unittest.TestCase):
    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            try:
                rc = cli.main(argv)
            except SystemExit as exc:
                rc = exc.code
        return rc, output.getvalue()

    def test_parameter_errors_are_json_exit_2(self):
        cases = [[], ["install-sdk"], ["license"],
                 ["install", "--timeout=0"], ["install", "--timeout=-1"],
                 ["install", "--package-file=a", "--url=https://example.com"],
                 ["install", "--package-file=a", "--arch=x86-64"],
                 ["install", "--password=secret"],
                 ["install", "--installer-sha256=invalid"],
                 ["install-sdk", "--spec=@a/b", "--path=/tmp"],
                 ["install-sdk", "--spec=@a/.."],
                 ["install-sdk", "--spec=@@a/b"],
                 ["license", "show", "--dry-run"],
                 ["license", "set", "--type=server", "--server-ip=host", "--server-port=99999"],
                 ["license", "set", "--type=server", "--server-ip=host", "--server-port=0"],
                 ["license", "set", "--type=usbkey", "--server-port=80"],
                 ["license", "set", "--type=http"],
                 ["install", "--url=https://user:secret@example.com", "--dry-run"],
                 ["install", "--url=https://[invalid", "--dry-run"],
                 ["install", "--url=https://example.com/?token=secret", "--dry-run"]]
        for case in cases:
            with self.subTest(case=case):
                rc, output = self.invoke(case)
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(output)["status"], "failed")

    def test_help_is_text_exit_0(self):
        for case in [["--help"], ["license", "set", "--help"]]:
            rc, output = self.invoke(case)
            self.assertEqual(rc, 0)
            self.assertIn("usage:", output)

    def test_license_mapping_dry_run(self):
        rc, output = self.invoke(["license", "set", "--type=server", "--server-ip=host",
                                  "--server-port=65535", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("--server_port=65535", json.loads(output)["result"]["tool_command"])

    def test_default_stdin_closed_and_explicit_input_supported(self):
        command = [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"]
        self.assertEqual(cli._run(command, timeout=2), (0, "''"))
        self.assertEqual(cli._run(command, input_text="controlled", timeout=2), (0, "'controlled'"))

    def test_secret_not_in_child_environment(self):
        with mock.patch.dict(os.environ, {cli.PASSWORD_ENV: "test-secret"}):
            rc, output = cli._run([sys.executable, "-c",
                                  f"import os; print({cli.PASSWORD_ENV!r} in os.environ)"], timeout=2)
        self.assertEqual((rc, output), (0, "False"))

    def test_timeout_kills_descendants_even_ignoring_term(self):
        with tempfile.TemporaryDirectory() as root:
            marker = str(Path(root) / "survived")
            child = ("import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                     f"time.sleep(1); pathlib.Path({marker!r}).write_text('alive')")
            parent = ("import subprocess,time; "
                      f"subprocess.Popen([{sys.executable!r},'-c',{child!r}]); time.sleep(10)")
            rc, output = cli._run([sys.executable, "-c", parent], timeout=0.2)
            self.assertEqual(rc, 124)
            self.assertIn("部分变更", output)
            time.sleep(1)
            self.assertFalse(Path(marker).exists())

    def test_early_errors_survive_large_log(self):
        rc, output = cli._run([sys.executable, "-c",
                              "print('[ERROR] first'); print('x'*200000); print('end')"], timeout=2)
        self.assertEqual(rc, 0)
        self.assertTrue(cli._sdk_problems(output))
        self.assertLess(len(output), 70000)
        self.assertTrue(output.endswith("end"))

    def test_zero_failures_not_failure(self):
        self.assertEqual(cli._sdk_problems("Found 0 installation failures"), [])
        self.assertEqual(len(cli._sdk_problems("Found 0 installation failures\nFound 2 installation failures")), 1)

    def test_license_multitoken_time_and_status(self):
        result = cli._parse_license("LaunchTime: 2026-08-21 12:00:00\nStatus: VALID\nRemainingDays: 30")
        self.assertEqual(result["launch_time"], "2026-08-21 12:00:00")
        self.assertEqual(result["remaining_days"], 30)
        self.assertEqual(result["status"], "VALID")

    def tar(self, path, entries):
        with tarfile.open(path, "w:gz") as handle:
            for name, data in entries.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                handle.addfile(member, io.BytesIO(data))

    def test_tar_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "bad.tar.gz"
            self.tar(archive, {"../escape": b"bad"})
            with self.assertRaises(RuntimeError):
                cli._unpack(archive, Path(root) / "out")
            self.assertFalse((Path(root) / "escape").exists())

    def test_tar_external_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                member = tarfile.TarInfo("external")
                member.type = tarfile.SYMTYPE
                member.linkname = "../escape"
                handle.addfile(member)
            with self.assertRaises(tarfile.FilterError):
                cli._unpack(archive, Path(root) / "out")

    def test_no_unsafe_legacy_fallback(self):
        with mock.patch.dict(tarfile.__dict__):
            del tarfile.data_filter
            handle = mock.Mock()
            with self.assertRaises(RuntimeError):
                cli._extract_tar(handle, "/unused")
            handle.extractall.assert_not_called()

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../escape", b"bad")
            with self.assertRaises(RuntimeError):
                cli._unpack(archive, Path(root) / "out")
            self.assertFalse((Path(root) / "escape").exists())

    def test_ambiguous_archives_and_installers_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ["one", "two"]:
                folder = Path(root) / name
                folder.mkdir()
                (folder / "Install.sh").write_text("echo hi")
                (folder / "payload.tar.gz").write_bytes(b"test")
            with self.assertRaises(RuntimeError):
                cli._find_by_suffix(root, ".tar.gz")
            with self.assertRaises(RuntimeError):
                cli._locate_installer(root)

    def test_nested_zip_tar_supported(self):
        with tempfile.TemporaryDirectory() as root:
            tar = Path(root) / "payload.tar.gz"
            self.tar(tar, {"realevo-stream/Install.sh": b"echo test"})
            archive = Path(root) / "package.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.write(tar, "a/b/c/d/payload.tar.gz")
            out = cli._unpack(archive, Path(root) / "out")
            self.assertTrue(cli._locate_installer(out).endswith("realevo-stream/Install.sh"))

    def test_dry_run_does_not_create_requested_work_directory(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "package.tar.gz"
            self.tar(archive, {"realevo-stream/Install.sh": b"# --quiet is mentioned only"})
            work = Path(root) / "persistent"
            with mock.patch.object(cli, "_sudo") as sudo:
                rc, output = self.invoke(["install", "--package-file", str(archive),
                                          "--work-dir", str(work), "--dry-run"])
                sudo.assert_not_called()
            self.assertEqual(rc, 0)
            self.assertFalse(json.loads(output)["result"]["quiet_supported"])
            self.assertFalse(work.exists())

    def test_unknown_installer_not_executed(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "package.tar.gz"
            self.tar(archive, {"realevo-stream/Install.sh": b"# --quiet"})
            with mock.patch.object(cli, "_sudo") as sudo:
                rc, output = self.invoke(["install", "--package-file", str(archive)])
                sudo.assert_not_called()
            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(output)["status"], "failed")

    def test_install_checks_expected_version(self):
        script = b'case "$1" in\n --quiet)\n echo quiet\n ;;\nesac\n'
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "package.tar.gz"
            self.tar(archive, {"realevo-stream/Install.sh": script,
                               "realevo-stream/config/version.ini": b"RealEvo_Version=3.0.0\n"})
            for version, expected_rc in [("old", 1), ("3.0.0", 0)]:
                with mock.patch.object(cli, "_sudo", return_value=(0, "done")), mock.patch.object(
                    cli, "cmd_check", return_value=cli._ok({"installed": True, "usable": True,
                                                            "version_number": version})
                ):
                    rc, _ = self.invoke(["install", "--package-file", str(archive),
                                         "--installer-sha256", hashlib.sha256(script).hexdigest()])
                    self.assertEqual(rc, expected_rc)

    def test_download_local_file_and_length_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source"
            source.write_bytes(b"payload")
            target = Path(root) / "target"
            cli._download(source.as_uri(), str(target), timeout=3)
            self.assertEqual(target.read_bytes(), b"payload")
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.getcode.return_value = 200
            response.headers = {"Content-Length": "4"}
            response.read.side_effect = [b"abc", b""]
            with mock.patch.object(cli.urllib.request, "urlopen", return_value=response):
                with self.assertRaises(RuntimeError):
                    cli._download_stream("https://example.com", target)

    def test_sudo_password_only_through_stdin(self):
        args = cli._build_parser().parse_args(["install-sdk", "--spec=@a/b"])
        with mock.patch.dict(os.environ, {cli.PASSWORD_ENV: "test-secret"}), mock.patch.object(
            cli, "_run", side_effect=[(1, "authentication needed"), (0, ""), (0, "done")]
        ) as run:
            self.assertEqual(cli._sudo(["tool"], args, timeout=2), (0, "done"))
            self.assertEqual(run.call_args_list[1].kwargs["input_text"], "test-secret\n")
            self.assertNotIn("test-secret", str([call.args for call in run.call_args_list]))
            self.assertNotIn(cli.PASSWORD_ENV, run.call_args_list[-1].kwargs["env"])

    def test_sudo_missing_password_fails_without_prompt(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(cli, "_run", return_value=(1, "")):
            rc, output = cli._sudo(["tool"], object(), timeout=2)
        self.assertEqual(rc, 1)
        self.assertIn(cli.PASSWORD_ENV, output)

    def test_sdk_checks_manifest_and_components(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(cli, "REALEVO_HOME", root):
            folder = Path(root) / "pkg/product/test-sdk"
            folder.mkdir(parents=True)
            manifest = {"SDK": "test-sdk", "base": [{"name": "base"}]}
            path = folder / "stream_config.json"
            path.write_text(json.dumps(manifest))
            with self.assertRaises(RuntimeError):
                cli._verify_sdk(manifest, str(path))
            base = Path(root) / "pkg/base/base.tar.gz"
            base.parent.mkdir()
            base.write_bytes(b"test")
            self.assertEqual(len(cli._verify_sdk(manifest, str(path))), 2)
            with self.assertRaises(RuntimeError):
                cli._verify_sdk({"SDK": "test-sdk"}, str(path))

    def test_sdk_zero_exit_without_manifest_is_failure(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(cli, "REALEVO_HOME", root), \
                mock.patch.object(cli, "_sudo", return_value=(0, "done")):
            rc, output = self.invoke(["install-sdk", "--spec=@a/test-sdk"])
            self.assertEqual(rc, 1)
            self.assertIn("验收失败", json.loads(output)["message"])

    def test_license_retries_readback(self):
        with mock.patch.object(cli, "_sudo", return_value=(0, "configured")), \
                mock.patch.object(cli, "_tool", side_effect=[(0, "Status: INVALID"), (0, "Status: VALID")]), \
                mock.patch.object(cli.time, "sleep"):
            rc, output = self.invoke(["license", "set", "--type=usbkey"])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(output)["result"]["license"]["status"], "VALID")


if __name__ == "__main__":
    unittest.main()
