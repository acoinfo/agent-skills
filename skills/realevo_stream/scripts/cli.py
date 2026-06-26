#!/usr/bin/env python3
"""
RealEvo-Stream CLI — tools.py 的命令行包装器

将所有功能包装为子命令，AI 可直接调用，无需每次生成调用脚本。

用法:
    python cli.py <command> [args...]

所有命令输出 JSON 格式结果，便于解析。
"""

import argparse
import asyncio
import json
import sys

import tools


# ========================================================================
# 命令定义
# 每条记录: (命令名, 对应函数, 是否异步, [参数定义列表])
# 参数定义: (参数名, help文本, 是否必填, [额外选项dict])
# ========================================================================

COMMANDS = [
    # ---- 工作空间 ----
    ("get-product-series", tools.get_product_series, False, []),
    ("get-base-versions", tools.get_base_versions, False, []),
    ("is-workspace", tools.is_workspace, False, [
        ("workspace-path", "工作空间路径", True),
    ]),

    # ---- 工作空间初始化 (同步查询) ----
    ("get-supported-platforms-by-base-project", tools.get_supported_platforms_by_base_project, False, [
        ("base-project-path", "Base 工程路径或 .tar.gz 文件路径", True),
    ]),
    ("get-supported-platforms-by-base-version", tools.get_supported_platforms_by_base_version, False, [
        ("base-version", "Base 版本名称", True),
    ]),
    ("get-available-toolchains", tools.get_available_toolchains, False, [
        ("toolchain-dir", "Toolchain 目录路径", True),
    ]),
    ("generate-toolchain-cmake", tools.generate_toolchain_cmake, False, [
        ("toolchain-dir", "Toolchain 目录路径", True),
        ("toolchain-name", "Toolchain 名称", True),
        ("platform", "平台名称", True),
        ("cmake-path", "CMake 文件输出路径", True),
    ]),

    # ---- 工作空间初始化 (异步) ----
    ("init-workspace-by-product-series", tools.init_sylixos_workspace_by_product_series, True, [
        ("workspace-path", "工作空间路径", True),
        ("product-series", "产品系列名称", True),
    ]),
    ("init-workspace-by-base-version", tools.init_sylixos_workspace_by_base_version, True, [
        ("workspace-path", "工作空间路径", True),
        ("base-version", "Base 版本名称", True),
        ("platforms", "平台列表，逗号分隔", True),
    ]),
    ("init-workspace-by-base-project", tools.init_sylixos_workspace_by_base_project, True, [
        ("workspace-path", "工作空间路径", True),
        ("base-project-path", "Base 工程路径", True),
        ("platforms", "平台列表，逗号分隔", True),
    ]),
    ("init-linux-workspace", tools.init_linux_workspace, True, [
        ("workspace-path", "工作空间路径", True),
        ("platform", "平台名称", True),
        ("toolchain-cmake-path", "Toolchain CMake 文件路径", True),
        ("rootfs-path", "RootFS 路径", True),
    ]),
    ("init-euler-workspace", tools.init_euler_workspace, True, [
        ("workspace-path", "工作空间路径", True),
        ("platform", "平台名称", True),
        ("toolchain-cmake-path", "Toolchain CMake 文件路径", True),
        ("rootfs-path", "RootFS 路径", True),
    ]),

    # ---- 工程管理 ----
    ("get-project-types", tools.get_project_types, False, []),
    ("get-project-params", tools.get_project_params, False, [
        ("project-type", "工程类型", True),
    ]),
    ("get-project-list", tools.get_project_list, False, [
        ("workspace-path", "工作空间路径", True),
    ]),
    ("create-project", tools.create_project, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-type", "工程类型", True),
        ("project-name", "工程名称", False),
        ("debug-level", "调试等级 (debug|release)", False),
        ("build-tool", "构建工具 (make|ninja)", False),
        ("source-path", "源码路径", False),
    ]),

    # ---- 设备管理 ----
    ("get-os-supported-platforms", tools.get_os_supported_platforms, False, [
        ("os", "操作系统 (Linux|OpenEuler|SylixOS)", True),
    ]),
    ("add-device", tools.add_device, False, [
        ("workspace-path", "工作空间路径", True),
        ("device-name", "设备名称", True),
        ("device-address", "设备地址/IP", True),
        ("user-name", "用户名", True),
        ("password", "密码", True),
        ("os", "操作系统", True),
        ("platform", "平台", True),
    ]),
    ("get-device-list", tools.get_device_list, False, [
        ("workspace-path", "工作空间路径", True),
    ]),
    ("see-device-info", tools.see_device_info, False, [
        ("workspace-path", "工作空间路径", True),
        ("device-name", "设备名称", True),
    ]),
    ("modify-device-info", tools.modify_device_info, False, [
        ("workspace-path", "工作空间路径", True),
        ("device-old-name", "原设备名称", True),
        ("device-new-name", "新设备名称（留空不修改）", False),
        ("device-address", "新地址（留空不修改）", False),
        ("user-name", "新用户名（留空不修改）", False),
        ("password", "新密码（留空不修改）", False),
        ("os", "新操作系统（留空不修改）", False),
        ("platform", "新平台（留空不修改）", False),
    ]),

    # ---- 构建 ----
    ("build-clean", tools.build_clean, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("os", "操作系统 (sylixos|linux|openeuler)", True),
    ]),
    ("build-config", tools.build_config, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("os", "操作系统 (sylixos|linux|openeuler)", True),
    ]),
    ("build-build", tools.build_build, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("os", "操作系统 (sylixos|linux|openeuler)", True),
    ]),
    ("build-install", tools.build_install, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("os", "操作系统 (sylixos|linux|openeuler)", True),
    ]),
    ("build-all", tools.build_all, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("os", "操作系统 (sylixos|linux|openeuler)", True),
    ]),
    ("build-uninstall", tools.build_uninstall, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("os", "操作系统 (sylixos|linux|openeuler)", True),
    ]),

    # ---- 部署 ----
    ("upload-project", tools.upload_project, True, [
        ("workspace-path", "工作空间路径", True),
        ("project-name", "工程名称", True),
        ("device-name", "目标设备名称", True),
    ]),
    ("upload-workspace", tools.upload_workspace, True, [
        ("workspace-path", "工作空间路径", True),
        ("device-name", "目标设备名称", True),
    ]),
]


def _make_parser():
    """构建 argparse 解析器"""
    parser = argparse.ArgumentParser(
        prog="realevo",
        description="RealEvo-Stream 命令行工具",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    for name, func, is_async, arg_defs in COMMANDS:
        sp = subparsers.add_parser(
            name,
            help=func.__doc__ and func.__doc__.strip().split("\n")[0] or "",
            description=func.__doc__ and func.__doc__.strip() or "",
        )
        for arg_name, arg_help, required, *_ in arg_defs:
            cli_name = "--" + arg_name.replace("_", "-")
            sp.add_argument(
                cli_name,
                dest=arg_name.replace("-", "_"),
                help=arg_help,
                required=required,
                default=None if required else "",
            )
        sp.set_defaults(_func=func, _is_async=is_async)

    return parser


def _run_async(coro):
    """运行异步函数并返回结果"""
    return asyncio.run(coro)


def main():
    parser = _make_parser()
    args = parser.parse_args()

    func = getattr(args, "_func", None)
    is_async = getattr(args, "_is_async", False)
    if not func:
        parser.print_help()
        sys.exit(1)

    # 收集参数，跳过内部字段
    func_args = {}
    for key, value in vars(args).items():
        if key in ("_func", "_is_async", "command"):
            continue
        func_args[key] = value

    # 过滤掉值为 None / 空字符串的参数（给函数传递默认值）
    filtered = {}
    for k, v in func_args.items():
        if v is None or v == "":
            # 对于 create_project，需要传 None 而不是跳过
            if func == tools.create_project and k in ("project_name", "debug_level", "build_tool", "source_path"):
                continue  # create_project 内部用 .get() 取，不传就行
            continue
        # 处理 platforms 参数：逗号分隔的字符串转列表
        if k == "platforms" and isinstance(v, str):
            v = [p.strip() for p in v.split(",") if p.strip()]
        filtered[k] = v

    # 执行
    try:
        if is_async:
            result = _run_async(func(**filtered))
        else:
            result = func(**filtered)

        # 输出 JSON
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        error_result = {
            "status": "error",
            "message": str(e),
        }
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
