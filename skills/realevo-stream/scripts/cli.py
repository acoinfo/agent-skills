#!/usr/bin/env python3
"""RealEvo-Stream 环境引导工具

只封装「适合 Agent 无人值守执行」的 4 类能力：
    check         检测命令集是否安装（含版本与 License 概览）
    install       下载并无人值守安装 RealEvo-Stream 命令集
    install-sdk   安装 SDK 产品（ACU SDK / 预编译 Base 等）
    license       配置（set）或查看（show）License

工作空间管理、工程管理、设备管理、构建、部署等操作**不在本工具范围内**，
请直接调用 /opt/acoinfo/realevo-stream/bin 下的原生命令，调用配方见 SKILL.md。

设计约束：
    * 所有外部命令一律使用 argv 数组（不经 shell），避免命令注入；
    * sudo 统一走「先 `sudo -S -v` 预认证，再 `sudo -n` 执行」，保证不会因等待
      密码而挂起；密码只经 stdin 传递，不出现在 argv 中；
    * 所有命令输出统一为 JSON：{"status": "success|failed", "result": ..., "message": ...}
      （参数错误也会输出 JSON，退出码 2）。
"""

import argparse
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

REALEVO_HOME = os.environ.get("REALEVO_HOME", "/opt/acoinfo/realevo-stream")
BIN_DIR = os.path.join(REALEVO_HOME, "bin")
ARMORY_BASE = os.environ.get("REALEVO_ARMORY_BASE", "https://armory.acoinfo.com/v1/packages")
DEFAULT_PACKAGE_SPEC = os.environ.get("REALEVO_PACKAGE_SPEC", "@realevo/realevo-stream")
PASSWORD_ENV = "REALEVO_SUDO_PASSWORD"

ARCH_ALIASES = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "x86-64", "amd64": "x86-64"}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


# ---------------------------------------------------------------------------
# 统一输出契约
# ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    """参数错误也输出 JSON，避免破坏调用方的解析约定。"""

    def error(self, message):
        _emit(_fail(f"参数错误：{message}"))
        raise SystemExit(2)


def _ok(result=None, message=None):
    payload = {"status": "success"}
    if result is not None:
        payload["result"] = result
    if message:
        payload["message"] = message
    return payload


def _fail(message, result=None):
    payload = {"status": "failed", "message": message}
    if result is not None:
        payload["result"] = result
    return payload


def _emit(payload):
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("status") == "success" else 1


# ---------------------------------------------------------------------------
# 通用执行helper
# ---------------------------------------------------------------------------


def _strip_ansi(text):
    return _ANSI_RE.sub("", text or "")


def _run(argv, *, input_text=None, timeout=None, cwd=None, env=None):
    """执行命令（argv 数组，不经 shell），返回 (returncode, 合并输出)。"""
    try:
        proc = subprocess.run(
            argv,
            input=input_text,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
    except FileNotFoundError:
        return 127, f"命令不存在：{argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"命令超时（{timeout}s）：{' '.join(argv)}"
    return proc.returncode, _strip_ansi((proc.stdout or "") + (proc.stderr or "")).strip()


def _tool_env():
    env = os.environ.copy()
    env["PATH"] = BIN_DIR + os.pathsep + env.get("PATH", "")
    return env


def _tool(name, *args, timeout=300):
    """调用命令集自带工具：绝对路径 + 注入 PATH（原生命令之间会互相调用）。"""
    return _run([os.path.join(BIN_DIR, name), *args], timeout=timeout, env=_tool_env())


def _password(args):
    pw = getattr(args, "password", None) or os.environ.get(PASSWORD_ENV)
    if pw:
        return pw
    if sys.stdin.isatty():
        return getpass.getpass("sudo 密码: ")
    return None


def _sudo(argv, args, *, timeout=None):
    """执行特权命令。

    优先尝试免密 sudo（NOPASSWD 或已缓存时间戳）：注意 `sudo -v` 即使配置了
    NOPASSWD 也会索要密码，因此必须用 `sudo -n true` 探测，不能一上来就 `-v`。
    免密不可用时才回退到「密码经 stdin 的 `sudo -S -v` 预认证」；
    实际执行阶段一律 `sudo -n`，绝不交互等待。
    """
    env = _tool_env()
    rc, out = _run(["sudo", "-n", "true"], timeout=30)
    if rc == 127:
        return 1, "未找到 sudo 命令：" + out
    if rc != 0:
        password = _password(args)
        if not password:
            return 1, f"sudo 需要密码但未提供（请用 --password 或环境变量 {PASSWORD_ENV}）"
        rc, out = _run(["sudo", "-S", "-p", "", "-v"], input_text=password + "\n", timeout=120)
        if rc != 0:
            return 1, "sudo 身份验证失败：" + (out or "密码错误或当前用户无 sudo 权限")
    return _run(["sudo", "-n", "env", f"PATH={env['PATH']}", *argv], timeout=timeout, env=env)


# ---------------------------------------------------------------------------
# License 解析
# ---------------------------------------------------------------------------


def _parse_license(text):
    fields = (
        ("version", "Version"),
        ("launch_time", "LaunchTime"),
        ("status", "Status"),
        ("remaining_days", "RemainingDays"),
    )
    info = {}
    for key, label in fields:
        match = re.search(rf"^\s*{re.escape(label)}:\s*(\S+)\s*$", text or "", re.M)
        if match:
            info[key] = match.group(1)
    if isinstance(info.get("remaining_days"), str) and info["remaining_days"].isdigit():
        info["remaining_days"] = int(info["remaining_days"])
    info["raw"] = (text or "").strip()
    return info


# ---------------------------------------------------------------------------
# 安装包处理
# ---------------------------------------------------------------------------


def _arch():
    machine = platform.machine().lower()
    return ARCH_ALIASES.get(machine, machine)


def _download(url, dest, timeout=1800):
    """下载安装包。进度写 stderr，stdout 只保留最终 JSON。

    注意：`file://` 等非 HTTP 协议的 `getcode()` 返回 None，不能被当成失败。
    """
    with urllib.request.urlopen(url, timeout=timeout) as response:
        status = response.getcode()
        if status is not None and status != 200:
            raise RuntimeError(f"下载失败，HTTP {status}：{url}")
        try:
            total = int(response.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            total = 0
        done = 0
        next_report = 0
        with open(dest, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if total and done >= next_report:
                    print(
                        f"[下载] {done * 100 // total}% ({done // 1048576}/{total // 1048576} MB)",
                        file=sys.stderr,
                        flush=True,
                    )
                    next_report = done + max(total // 10, 1)
    if os.path.getsize(dest) == 0:
        raise RuntimeError(f"下载内容为空：{url}")


def _find_by_suffix(root, suffix, max_depth=3):
    root = os.path.abspath(root)
    for current, dirs, files in os.walk(root):
        depth = current[len(root):].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
        for name in sorted(files):
            if name.endswith(suffix):
                return os.path.join(current, name)
    return None


def _extract_tar(handle, dest):
    """`filter="data"` 可防止路径穿越；旧版 Python 无该参数时回退。"""
    try:
        handle.extractall(dest, filter="data")
    except TypeError:
        handle.extractall(dest)


def _unpack(archive, dest):
    """支持两种发布形态：zip 外壳（内含 tar.gz）或直接的 tar.gz。"""
    os.makedirs(dest, exist_ok=True)
    target = archive
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(dest)
        target = _find_by_suffix(dest, ".tar.gz")
        if target is None:
            return dest
    if tarfile.is_tarfile(target):
        with tarfile.open(target, "r:*") as handle:
            _extract_tar(handle, dest)
    return dest


def _locate_installer(root):
    """在解包目录中定位最浅层的 Install.sh。"""
    candidates = []
    root = os.path.abspath(root)
    for current, dirs, files in os.walk(root):
        if "Install.sh" in files:
            rel = os.path.relpath(os.path.join(current, "Install.sh"), root)
            candidates.append((rel.count(os.sep), os.path.join(current, "Install.sh")))
    if not candidates:
        return None
    return sorted(candidates)[0][1]


def _supports_quiet(installer):
    try:
        with open(installer, "r", encoding="utf-8", errors="replace") as handle:
            return "--quiet" in handle.read()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def cmd_check(args):
    """检测命令集是否安装，并给出版本与 License 概览。"""
    required = ("rl-workspace", "rl-tools")
    paths = {name: os.path.join(BIN_DIR, name) for name in required}
    missing = [
        name for name in required
        if not (os.path.isfile(paths[name]) and os.access(paths[name], os.X_OK))
    ]
    installed = not missing
    result = {
        "installed": installed,
        "home": REALEVO_HOME,
        "rl_workspace": paths["rl-workspace"],
        "rl_tools": paths["rl-tools"],
    }
    if not installed:
        result["missing"] = missing
        result["hint"] = "未检测到完整的命令集，请先执行：cli.py install"
        return _ok(result, "RealEvo-Stream 命令集未安装或不完整")

    rc, out = _tool("rl-tools", "--version", timeout=60)
    result["version"] = out.splitlines()[-1] if rc == 0 and out else None

    rc, out = _tool("rl-tools", "show", "--license", timeout=60)
    result["license"] = _parse_license(out) if rc == 0 else {"raw": out, "error": True}
    return _ok(result, "RealEvo-Stream 命令集已安装")


def cmd_install(args):
    """下载并无人值守安装 RealEvo-Stream 命令集。"""
    if args.work_dir:
        workdir = os.path.abspath(args.work_dir)
        os.makedirs(workdir, exist_ok=True)
        cleanup = False
    else:
        workdir = tempfile.mkdtemp(prefix="realevo-install-")
        cleanup = True
    keep = False
    try:
        if args.package_file:
            archive = os.path.abspath(args.package_file)
            if not os.path.isfile(archive):
                return _fail(f"安装包不存在：{archive}")
        else:
            url = args.url or f"{ARMORY_BASE}/{DEFAULT_PACKAGE_SPEC}/v/latest/p/Linux/a/{args.arch or _arch()}"
            if args.dry_run:
                return _ok({"dry_run": True, "url": url, "arch": args.arch or _arch()})
            archive = os.path.join(workdir, "package.archive")
            try:
                _download(url, archive)
            except (urllib.error.URLError, OSError, RuntimeError) as exc:
                return _fail(f"下载安装包失败：{exc}")

        root = _unpack(archive, tempfile.mkdtemp(prefix="unpacked-", dir=workdir))
        installer = _locate_installer(root)
        if installer is None:
            return _fail("安装包中未找到 Install.sh，请确认包来源")

        quiet = _supports_quiet(installer)
        install_argv = ["bash", installer] + (["--quiet"] if quiet else [])
        if args.dry_run:
            return _ok(
                {
                    "dry_run": True,
                    "installer_in_package": os.path.relpath(installer, root),
                    "quiet_supported": quiet,
                    "sudo_command": ["sudo", "-n", "true"],
                    "install_command": install_argv,
                }
            )
        if not quiet:
            keep = True  # 保留解包目录，使提示中的路径仍可被人工执行
            return _fail(
                "该安装包不支持 --quiet，无法无人值守安装；"
                f"请人工执行：sudo bash {installer}"
            )

        rc, out = _sudo(install_argv, args, timeout=args.timeout)
        if rc != 0:
            return _fail(f"命令集安装失败：{out}")
        return _ok({"output": out[-2000:]}, "RealEvo-Stream 命令集安装完成")
    finally:
        if cleanup and not keep:
            shutil.rmtree(workdir, ignore_errors=True)


def _sdk_problems(output):
    """`rl-tools update --plugin` 即使有失败项也会 exit 0，必须解析输出。"""
    problems = []
    if "[ERROR]" in output:
        problems.extend(line.strip() for line in output.splitlines() if "[ERROR]" in line)
    match = re.search(r"Found (\d+) installation failures", output)
    if match:
        problems.append(f"{match.group(1)} 个组件安装失败")
    return problems


def cmd_install_sdk(args):
    """安装 SDK 产品：在线（--spec）或离线目录（--path）。"""
    if bool(args.spec) == bool(args.path):
        return _fail("--spec（在线包）与 --path（离线目录）必须且只能指定一个")

    if args.path:
        offline = os.path.abspath(args.path)
        if not os.path.isfile(os.path.join(offline, "stream_config.json")):
            return _fail(f"离线目录缺少 stream_config.json：{offline}")
        tool_args = ["update", f"--path={offline}"]
        target = offline
    else:
        if not re.fullmatch(r"@[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", args.spec):
            return _fail("--spec 需形如 @namespace/package-name，例如 @realevo/realevo-stream-sdk")
        tool_args = ["update", f"--plugin={args.spec}"]
        target = args.spec

    argv = [os.path.join(BIN_DIR, "rl-tools"), *tool_args]
    if args.dry_run:
        return _ok({"dry_run": True, "target": target, "sudo_command": ["sudo", "-n", "true"], "tool_command": argv})

    rc, out = _sudo(argv, args, timeout=args.timeout)
    if rc != 0:
        return _fail(f"SDK 安装失败：{out}")

    problems = _sdk_problems(out)
    if problems:
        return _fail(
            "SDK 安装存在失败项（注意 rl-tools 仍返回 0）：" + "；".join(problems),
            result={"output": out[-2000:]},
        )
    return _ok({"output": out[-2000:]}, f"SDK 安装完成：{target}")


def cmd_license(args):
    """配置或查看 License。"""
    if args.action == "show":
        rc, out = _tool("rl-tools", "show", "--license", timeout=60)
        if rc != 0:
            return _fail(f"读取 License 失败：{out}")
        return _ok(_parse_license(out), "License 信息")

    if not args.type:
        return _fail("license set 需要 --type=usbkey|server|http")

    extra = []
    if args.type == "usbkey":
        if args.server_ip or args.server_port or args.http_address:
            return _fail("usbkey 模式不接受 --server-ip/--server-port/--http-address")
    elif args.type == "server":
        if not args.server_ip:
            return _fail("server 模式需要 --server-ip")
        if args.http_address:
            return _fail("server 模式不接受 --http-address")
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", args.server_ip):
            return _fail(f"--server-ip 取值非法：{args.server_ip}")
        if args.server_port and not args.server_port.isdigit():
            return _fail(f"--server-port 必须为数字：{args.server_port}")
        extra.append(f"--server_ip={args.server_ip}")
        if args.server_port:
            extra.append(f"--server_port={args.server_port}")
    else:  # http
        if not args.http_address:
            return _fail("http 模式需要 --http-address")
        if args.server_ip or args.server_port:
            return _fail("http 模式不接受 --server-ip/--server-port")
        if not re.fullmatch(r"https?://[^\s]+", args.http_address):
            return _fail(f"--http-address 需为 http(s):// 形式：{args.http_address}")
        extra.append(f"--http_address={args.http_address}")

    argv = [os.path.join(BIN_DIR, "rl-tools"), "update_lcsproxy", f"--type={args.type}", *extra]
    if args.dry_run:
        return _ok({"dry_run": True, "sudo_command": ["sudo", "-n", "true"], "tool_command": argv})

    rc, out = _sudo(argv, args, timeout=args.timeout)
    if rc != 0:
        return _fail(f"License 配置失败：{out}")

    # 代理重启后状态可能短暂未就绪；配置成功不代表授权已经生效。
    for attempt in range(3):
        rc2, out2 = _tool("rl-tools", "show", "--license", timeout=60)
        license_info = _parse_license(out2) if rc2 == 0 else {"raw": out2, "error": True}
        result = {"config_output": out[-2000:], "license": license_info}
        if rc2 == 0 and license_info.get("status") == "VALID":
            return _ok(result, f"License 已配置为 {args.type} 模式，授权有效")
        if attempt < 2:
            time.sleep(1)

    if rc2 != 0:
        return _fail("License 配置已写入，但授权状态回读失败", result)
    return _fail("License 配置已写入，但授权未生效", result)


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------


def _add_privileged_options(parser, timeout_default):
    parser.add_argument("--password", help=f"sudo 密码（推荐改用环境变量 {PASSWORD_ENV}）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要执行的命令，不做任何变更")
    parser.add_argument("--timeout", type=int, default=timeout_default, help=f"超时秒数（默认 {timeout_default}）")


def _build_parser():
    parser = _Parser(
        prog="realevo-setup",
        description="RealEvo-Stream 环境引导工具（检测 / 安装 / SDK / License）",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    check = subparsers.add_parser("check", help="检测命令集是否安装，并输出版本与 License 概览")
    check.set_defaults(handler=cmd_check)

    install = subparsers.add_parser("install", help="下载并无人值守安装 RealEvo-Stream 命令集")
    install.add_argument("--package-file", help="使用本地安装包（zip 或 tar.gz），跳过下载")
    install.add_argument("--url", help="覆盖安装包下载地址")
    install.add_argument("--arch", help=f"覆盖架构标识（默认自动识别：{_arch()}）")
    install.add_argument(
        "--work-dir",
        help="指定解包工作目录（安装包约 1GB，/tmp 为 tmpfs 时建议指定磁盘目录；指定后不会自动清理）",
    )
    _add_privileged_options(install, 3600)
    install.set_defaults(handler=cmd_install)

    install_sdk = subparsers.add_parser("install-sdk", help="安装 SDK 产品（ACU SDK / 预编译 Base 等）")
    install_sdk.add_argument("--spec", help="在线包标识，例如 @realevo/realevo-stream-sdk")
    install_sdk.add_argument("--path", help="离线 SDK 目录（需含 stream_config.json）")
    _add_privileged_options(install_sdk, 2400)
    install_sdk.set_defaults(handler=cmd_install_sdk)

    license_parser = subparsers.add_parser("license", help="配置或查看 License")
    license_parser.add_argument("action", choices=["show", "set"], help="show 查看；set 配置")
    license_parser.add_argument("--type", choices=["usbkey", "server", "http"], help="授权代理模式（set 必填）")
    license_parser.add_argument("--server-ip", help="server 模式：服务器地址")
    license_parser.add_argument("--server-port", help="server 模式：服务器端口")
    license_parser.add_argument("--http-address", help="http 模式：HTTP 代理地址")
    _add_privileged_options(license_parser, 600)
    license_parser.set_defaults(handler=cmd_license)

    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        _build_parser().print_help()
        return 1
    try:
        return _emit(handler(args))
    except KeyboardInterrupt:
        return _emit(_fail("操作被中断"))
    except Exception as exc:  # noqa: BLE001 - 统一转为 JSON，避免调用方拿到堆栈
        return _emit(_fail(f"{type(exc).__name__}: {exc}"))


if __name__ == "__main__":
    sys.exit(main())
