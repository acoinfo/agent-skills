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
    * sudo 先探测免密权限，必要时使用环境变量中的密码经 stdin 预认证；
      不读取终端密码，不接受密码 argv 参数；
    * 默认关闭 stdin，超时终止进程组；输出落临时文件，保留错误摘要与日志尾部；
    * 业务结果及参数错误输出 JSON；--help 为文本，退出码 0。
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import urllib.parse
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
REQUIRED_TOOLS = ("rl-workspace", "rl-tools", "rl-project", "rl-build", "rl-device", "rl-upload", "rl-package")
# 核验过的本机 3.0.0 安装器；未知包需提供经可信渠道核验的安装器摘要。
VERIFIED_INSTALLERS = {"7957f9e910cebba2e065698afb2d6316478d5f2d17a79380fcf165394d3b92f5"}


class ParameterError(ValueError):
    """调用参数错误，区别于环境或业务失败。"""


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
    output = json.dumps(payload, ensure_ascii=False)
    password = os.environ.get(PASSWORD_ENV)
    if password:
        output = output.replace(json.dumps(password, ensure_ascii=False)[1:-1], "[REDACTED]")
    print(output)
    return 0 if payload.get("status") == "success" else 1


# ---------------------------------------------------------------------------
# 通用执行helper
# ---------------------------------------------------------------------------


def _strip_ansi(text):
    return _ANSI_RE.sub("", text or "")


def _run(argv, *, input_text=None, timeout=None, cwd=None, env=None):
    """Linux 宿主：关闭 stdin，日志落盘，超时回收同进程组后返回 124。"""
    env = dict(os.environ if env is None else env)
    env.pop(PASSWORD_ENV, None)
    with tempfile.TemporaryFile() as log:
        try:
            proc = subprocess.Popen(
                argv, stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, text=True, cwd=cwd, env=env,
                start_new_session=True,
            )
        except FileNotFoundError:
            return 127, f"命令不存在：{argv[0]}"
        timed_out = False
        try:
            proc.communicate(input=input_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _stop_group(proc, privileged=argv[0] == "sudo")
        except BaseException:
            _stop_group(proc, privileged=argv[0] == "sudo")
            raise
        log.seek(0)
        diagnostics = []
        # 有界扫描也保留日志前部的错误；最终输出不承载完整安装日志。
        while chunk := log.readline(65536):
            line = _strip_ansi(chunk.decode("utf-8", errors="replace"))
            if "[ERROR]" in line or re.search(r"Found [1-9][0-9]* installation failures", line):
                if len(diagnostics) < 100:
                    diagnostics.append(line.strip()[:2000])
        size = log.tell()
        log.seek(max(0, size - 65536))
        tail = _strip_ansi(log.read().decode("utf-8", errors="replace")).strip()
        out = "\n".join(diagnostics + (["[日志仅保留错误摘要与尾部]"] if size > 65536 else []) + [tail])
        if timed_out:
            return 124, f"命令超时（{timeout}s）；可能已有部分变更，请检查后再决定是否重试。\n{out}"
        return proc.returncode, out.strip()


def _stop_group(proc, privileged=False):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass  # sudo 启动的 root 进程需特权清理。
        if privileged:
            try:
                subprocess.run(
                    ["sudo", "-n", "kill", f"-{sig.value}", "--", f"-{proc.pid}"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5, env=_tool_env(),
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        if sig == signal.SIGTERM:
            time.sleep(0.2)
    proc.wait(timeout=5)


def _tool_env():
    env = os.environ.copy()
    env.pop(PASSWORD_ENV, None)
    env["PATH"] = BIN_DIR + os.pathsep + env.get("PATH", "")
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _tool(name, *args, timeout=300):
    """调用命令集自带工具：绝对路径 + 注入 PATH（原生命令之间会互相调用）。"""
    return _run([os.path.join(BIN_DIR, name), *args], timeout=timeout, env=_tool_env())


def _password(args):
    return os.environ.get(PASSWORD_ENV)


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
            return 1, f"sudo 需要密码但未提供（由运行环境提供 {PASSWORD_ENV}，不要写入命令行）"
        rc, out = _run(["sudo", "-S", "-p", "", "-v"], input_text=password + "\n", timeout=120)
        if rc != 0:
            return 1, "sudo 身份验证失败：" + (out or "密码错误或当前用户无 sudo 权限")
    # 密码无需传给安装器及其子进程。
    env.pop(PASSWORD_ENV, None)
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
        match = re.search(rf"^[ \t]*{re.escape(label)}:[ \t]*([^\r\n]+)", text or "", re.M)
        if match:
            info[key] = match.group(1).strip()
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
    """独立进程实现下载总截止时间；不接受 URL 中的凭据。"""
    worker = "import runpy,sys; runpy.run_path(sys.argv[1])['_download_stream'](sys.argv[2],sys.argv[3])"
    rc, out = _run([sys.executable, "-c", worker, os.path.abspath(__file__), url, dest], timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"下载失败（退出码 {rc}）：{out}")


def _download_stream(url, dest):
    with urllib.request.urlopen(url, timeout=30) as response:
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
    if total and done != total:
        raise RuntimeError(f"下载长度不符：期望 {total} 字节，实际 {done} 字节")
    if done == 0:
        raise RuntimeError(f"下载内容为空：{url}")


def _find_by_suffix(root, suffix):
    root = os.path.abspath(root)
    candidates = []
    for current, dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith(suffix):
                candidates.append(os.path.join(current, name))
    if len(candidates) > 1:
        raise RuntimeError(f"安装包包含多个 {suffix}，无法唯一选择")
    return candidates[0] if candidates else None


def _extract_tar(handle, dest):
    """拒绝没有安全解压过滤器的 Python，不作不安全降级。"""
    if not hasattr(tarfile, "data_filter"):
        raise RuntimeError("需要带 tarfile.data_filter 的 Python 3.10+ 安全补丁版本")
    members = handle.getmembers()
    for member in members:
        _archive_path(member.name, dest)
        tarfile.data_filter(member, dest)
    handle.extractall(dest, members=members, filter="data")


def _archive_path(name, dest):
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized) or ".." in normalized.split("/"):
        raise RuntimeError(f"安装包路径不安全：{name}")
    target = os.path.realpath(os.path.join(dest, normalized))
    if os.path.commonpath([os.path.realpath(dest), target]) != os.path.realpath(dest):
        raise RuntimeError(f"安装包路径越界：{name}")
    return target


def _unpack(archive, dest):
    """支持两种发布形态：zip 外壳（内含 tar.gz）或直接的 tar.gz。"""
    os.makedirs(dest, exist_ok=True)
    target = archive
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as handle:
            for member in handle.infolist():
                _archive_path(member.filename, dest)
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError("zip 安装包不接受符号链接")
            handle.extractall(dest)
        target = _find_by_suffix(dest, ".tar.gz")
        if target is None:
            return dest
    if tarfile.is_tarfile(target):
        with tarfile.open(target, "r:*") as handle:
            _extract_tar(handle, dest)
    else:
        raise RuntimeError("安装包不是支持的 zip 或 tar 归档")
    return dest


def _locate_installer(root):
    """仅接受唯一且位于解包目录内的普通安装脚本。"""
    candidates = []
    root = os.path.abspath(root)
    for current, dirs, files in os.walk(root):
        if "Install.sh" in files:
            path = os.path.join(current, "Install.sh")
            _archive_path(os.path.relpath(path, root), root)
            if os.path.islink(path):
                raise RuntimeError("Install.sh 不得是符号链接")
            candidates.append(path)
    if not candidates:
        return None
    if len(candidates) != 1:
        raise RuntimeError("存在多个 Install.sh，无法唯一选择安装器")
    return candidates[0]


def _supports_quiet(installer, expected_digest=None):
    with open(installer, "rb") as handle:
        content = handle.read()
    digest = hashlib.sha256(content).hexdigest()
    trusted = digest == expected_digest if expected_digest else digest in VERIFIED_INSTALLERS
    # 摘要固定人工核验的行为；静态分支检查不能独自证明无人值守能力。
    return trusted and bool(re.search(r"^\s*--quiet\)\s*$", content.decode("utf-8", errors="replace"), re.M))


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def cmd_check(args):
    """检测命令集是否安装，并给出版本与 License 概览。"""
    required = REQUIRED_TOOLS
    paths = {name: os.path.join(BIN_DIR, name) for name in required}
    missing = [
        name for name in required
        if not (os.path.isfile(paths[name]) and os.access(paths[name], os.X_OK))
    ]
    installed = not missing
    result = {
        "installed": installed,
        "usable": False,
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
    version = re.search(r"^RealEvo-Stream version:[ \t]*(\S+)[ \t]*$", out, re.M)
    result["version_number"] = version.group(1) if version else None
    result["usable"] = rc == 0 and version is not None and not _sdk_problems(out)

    rc, out = _tool("rl-tools", "show", "--license", timeout=60)
    result["license"] = _parse_license(out) if rc == 0 else {"raw": out, "error": True}
    return _ok(result, "命令入口检测完成；不代表所有 SDK、工具链或设备已就绪")


def cmd_install(args):
    """下载并无人值守安装 RealEvo-Stream 命令集。"""
    url = args.url or f"{ARMORY_BASE}/{DEFAULT_PACKAGE_SPEC}/v/latest/p/Linux/a/{args.arch or _arch()}"
    if args.dry_run and not args.package_file:
        return _ok({"dry_run": True, "url": url, "arch": args.arch or _arch(), "installer_verified": False},
                   "仅预览下载地址；未检查远程安装包或安装器")
    if args.work_dir and not args.dry_run:
        parent = os.path.abspath(args.work_dir)
        os.makedirs(parent, exist_ok=True)
        workdir = tempfile.mkdtemp(prefix="realevo-install-", dir=parent)
        cleanup = False
    else:
        workdir = tempfile.mkdtemp(prefix="realevo-install-")
        cleanup = True
    try:
        if args.package_file:
            archive = os.path.abspath(args.package_file)
            if not os.path.isfile(archive):
                return _fail(f"安装包不存在：{archive}")
        else:
            archive = os.path.join(workdir, "package.archive")
            try:
                _download(url, archive, timeout=args.timeout)
            except (urllib.error.URLError, OSError, RuntimeError) as exc:
                return _fail(f"下载安装包失败：{exc}")

        root = _unpack(archive, tempfile.mkdtemp(prefix="unpacked-", dir=workdir))
        installer = _locate_installer(root)
        if installer is None:
            return _fail("安装包中未找到 Install.sh，请确认包来源")

        quiet = _supports_quiet(installer, args.installer_sha256)
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
            return _fail(
                "安装器未匹配已核验摘要或不含受支持的 --quiet 分支；"
                "请核验包来源与无人值守行为后，用 --installer-sha256 指定可信摘要。"
            )

        version_path = os.path.join(os.path.dirname(installer), "config", "version.ini")
        with open(version_path, encoding="utf-8") as handle:
            expected_version = re.search(r"^RealEvo_Version=(\S+)[ \t]*$", handle.read(), re.M)
        if expected_version is None:
            return _fail("安装包 config/version.ini 缺少 RealEvo_Version，无法验收版本")

        rc, out = _sudo(install_argv, args, timeout=args.timeout)
        if rc != 0 or _sdk_problems(out):
            return _fail(f"命令集安装失败：{out}")
        check = cmd_check(args)["result"]
        if (not check["installed"] or not check.get("usable")
                or check.get("version_number") != expected_version.group(1)):
            return _fail("安装命令已结束，但必需命令或目标版本验收失败", check)
        return _ok({"output": out[-2000:], "check": check}, "命令入口与版本查询验收通过；仍需按阶段验收 SDK/License")
    finally:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)


def _sdk_problems(output):
    """`rl-tools update --plugin` 即使有失败项也会 exit 0，必须解析输出。"""
    problems = []
    if "[ERROR]" in output:
        problems.extend(line.strip() for line in output.splitlines() if "[ERROR]" in line)
    for count in re.findall(r"Found (\d+) installation failures", output):
        if int(count) > 0:
            problems.append(f"{count} 个组件安装失败")
    return problems


def _read_sdk_manifest(path):
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or not _safe_component(manifest.get("SDK")):
        raise RuntimeError("stream_config.json 缺少合法 SDK 名称")
    for kind in ("base", "rootfs", "tools"):
        entries = manifest.get(kind, [])
        if not isinstance(entries, list) or any(
            not isinstance(entry, dict) or not _safe_component(entry.get("name")) for entry in entries
        ):
            raise RuntimeError(f"stream_config.json 的 {kind} 清单无效")
    return manifest


def _safe_component(value):
    return isinstance(value, str) and value not in (".", "..") and bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))


def _verify_sdk(manifest, installed_manifest):
    installed = _read_sdk_manifest(installed_manifest)
    if installed != manifest:
        raise RuntimeError("安装后的 SDK 清单与预期不一致")
    verified = [installed_manifest]
    for kind in ("base", "rootfs", "tools"):
        for entry in manifest.get(kind, []):
            if kind == "tools":
                path = os.path.join(REALEVO_HOME, "pkg", "product", manifest["SDK"], "tools", entry["name"])
                exists = os.path.isdir(path) and bool(os.listdir(path))
            else:
                path = os.path.join(REALEVO_HOME, "pkg", kind, entry["name"] + ".tar.gz")
                exists = os.path.isfile(path) and os.path.getsize(path) > 0
            if not exists:
                raise RuntimeError(f"SDK 组件验收失败：{path}")
            verified.append(path)
    return verified


def cmd_install_sdk(args):
    """安装 SDK 产品：在线（--spec）或离线目录（--path）。"""
    manifest = None
    if args.path:
        offline = os.path.abspath(args.path)
        if not os.path.isfile(os.path.join(offline, "stream_config.json")):
            return _fail(f"离线目录缺少 stream_config.json：{offline}")
        manifest = _read_sdk_manifest(os.path.join(offline, "stream_config.json"))
        tool_args = ["update", f"--path={offline}"]
        target = offline
    else:
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
    sdk_name = manifest["SDK"] if manifest else args.spec.split("/")[-1]
    installed_manifest = os.path.join(REALEVO_HOME, "pkg", "product", sdk_name, "stream_config.json")
    try:
        if manifest is None:
            manifest = _read_sdk_manifest(installed_manifest)
            if manifest["SDK"] != sdk_name:
                raise RuntimeError("在线包名与 SDK 名称不同，请用离线清单验收")
        verified = _verify_sdk(manifest, installed_manifest)
    except (OSError, ValueError, RuntimeError) as exc:
        return _fail(f"安装命令已结束，但 SDK 验收失败：{exc}", {"output": out[-2000:]})
    return _ok({"output": out[-2000:], "verified_paths": verified,
                "verification": "manifest_and_presence"},
               f"SDK 清单及组件存在性验收通过：{target}；不代表 ABI、内容版本或工具链功能已验证")


def cmd_license(args):
    """配置或查看 License。"""
    if args.action == "show":
        rc, out = _tool("rl-tools", "show", "--license", timeout=60)
        if rc != 0:
            return _fail(f"读取 License 失败：{out}")
        return _ok(_parse_license(out), "License 信息")

    extra = []
    if args.type == "server":
        extra.append(f"--server_ip={args.server_ip}")
        if args.server_port:
            extra.append(f"--server_port={args.server_port}")
    elif args.type == "http":
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


def _positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("必须为正整数") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("必须为正整数")
    return number


def _url(value, schemes):
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        raise ParameterError("URL 格式无效") from None
    if parsed.scheme not in schemes or any(ch.isspace() for ch in value):
        raise ParameterError("URL 协议或格式无效")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ParameterError("URL 不接受凭据、查询参数或片段；使用不含秘密的下载地址")
    if parsed.scheme != "file" and not parsed.hostname:
        raise ParameterError("URL 缺少主机名")
    if parsed.scheme == "file" and (parsed.netloc not in ("", "localhost") or not parsed.path):
        raise ParameterError("file URL 必须指向本地文件")
    try:
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
    except ValueError:
        raise ParameterError("URL 端口无效") from None


def _validate_args(args):
    if args.command == "install":
        if args.package_file and args.arch:
            raise ParameterError("--package-file 不接受 --arch")
        if args.arch and not _safe_component(args.arch):
            raise ParameterError("--arch 标识无效")
        if args.installer_sha256 and not re.fullmatch(r"[a-f0-9]{64}", args.installer_sha256):
            raise ParameterError("--installer-sha256 必须为 64 位小写十六进制摘要")
        if not args.package_file:
            _url(args.url or f"{ARMORY_BASE}/{DEFAULT_PACKAGE_SPEC}/v/latest/p/Linux/a/{args.arch or _arch()}",
                 {"http", "https", "file"})
    elif args.command == "install-sdk" and args.spec:
        parts = args.spec[1:].split("/")
        if not args.spec.startswith("@") or len(parts) != 2 or not all(_safe_component(p) for p in parts):
            raise ParameterError("--spec 需形如 @namespace/package-name")
    elif args.command == "license" and args.action == "set":
        if args.type == "usbkey" and (args.server_ip or args.server_port or args.http_address):
            raise ParameterError("usbkey 模式不接受 server/http 参数")
        if args.type == "server":
            if not args.server_ip or not re.fullmatch(r"[A-Za-z0-9._:-]+", args.server_ip):
                raise ParameterError("server 模式需要合法 --server-ip")
            if args.http_address:
                raise ParameterError("server 模式不接受 --http-address")
            if args.server_port and (not args.server_port.isascii() or not args.server_port.isdigit()
                                     or not 1 <= int(args.server_port) <= 65535):
                raise ParameterError("--server-port 必须为 1..65535 的整数")
        elif args.type == "http":
            if not args.http_address or args.server_ip or args.server_port:
                raise ParameterError("http 模式需要 --http-address，且不接受 server 参数")
            _url(args.http_address, {"http", "https"})


def _add_privileged_options(parser, timeout_default):
    parser.add_argument("--dry-run", action="store_true", help="不执行系统安装/配置；本地包检查会创建并清理临时文件")
    parser.add_argument("--timeout", type=_positive_int, default=timeout_default,
                        help=f"单个安装命令或下载的截止秒数（默认 {timeout_default}；认证/验收另计）")


def _build_parser():
    parser = _Parser(
        prog="realevo-setup",
        description="RealEvo-Stream 环境引导工具（检测 / 安装 / SDK / License）",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    check = subparsers.add_parser("check", help="检测命令集是否安装，并输出版本与 License 概览")
    check.set_defaults(handler=cmd_check)

    install = subparsers.add_parser("install", help="下载并无人值守安装 RealEvo-Stream 命令集")
    source = install.add_mutually_exclusive_group()
    source.add_argument("--package-file", help="使用本地安装包（zip 或 tar.gz），跳过下载")
    source.add_argument("--url", help="覆盖安装包下载地址（不接受 URL 凭据或查询参数）")
    install.add_argument("--arch", help=f"覆盖架构标识（默认自动识别：{_arch()}）")
    install.add_argument("--installer-sha256", help="已核验来源与 --quiet 行为的 Install.sh SHA-256；未知安装器必需")
    install.add_argument(
        "--work-dir",
        help="指定磁盘父目录，在其下创建独立工作目录并保留；dry-run 总会清理临时文件",
    )
    _add_privileged_options(install, 3600)
    install.set_defaults(handler=cmd_install)

    install_sdk = subparsers.add_parser("install-sdk", help="安装 SDK 产品（ACU SDK / 预编译 Base 等）")
    sdk_source = install_sdk.add_mutually_exclusive_group(required=True)
    sdk_source.add_argument("--spec", help="在线包标识，例如 @realevo/realevo-stream-sdk；包名需与 SDK 名一致")
    sdk_source.add_argument("--path", help="离线 SDK 目录（需含 stream_config.json）")
    _add_privileged_options(install_sdk, 2400)
    install_sdk.set_defaults(handler=cmd_install_sdk)

    license_parser = subparsers.add_parser("license", help="配置或查看 License")
    actions = license_parser.add_subparsers(dest="action", required=True)
    actions.add_parser("show", help="读取 License")
    license_set = actions.add_parser("set", help="配置并回读 License")
    license_set.add_argument("--type", choices=["usbkey", "server", "http"], required=True, help="授权代理模式")
    license_set.add_argument("--server-ip", help="server 模式：服务器地址")
    license_set.add_argument("--server-port", help="server 模式：服务器端口，1..65535")
    license_set.add_argument("--http-address", help="http 模式：HTTP 代理地址（不含凭据或查询参数）")
    _add_privileged_options(license_set, 600)
    license_parser.set_defaults(handler=cmd_license)

    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_args(args)
        if sys.platform != "linux" or sys.version_info < (3, 10):
            return _emit(_fail("本封装需要 Linux 宿主及 Python 3.10+"))
        return _emit(args.handler(args))
    except ParameterError as exc:
        _emit(_fail(f"参数错误：{exc}"))
        return 2
    except KeyboardInterrupt:
        return _emit(_fail("操作被中断"))
    except Exception as exc:  # noqa: BLE001 - 统一转为 JSON，避免调用方拿到堆栈
        return _emit(_fail(f"{type(exc).__name__}: {exc}"))


if __name__ == "__main__":
    sys.exit(main())
