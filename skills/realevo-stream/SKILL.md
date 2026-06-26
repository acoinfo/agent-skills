---
name: realevo-stream
description: RealEvo-Stream 嵌入式开发工具 — 提供工作空间管理、工程管理、设备管理、构建、部署等功能的技能文档
version: 1.0.0
model: claude-sonnet-4-6
metadata:
  type: skill
  domain: embedded-development
  platform: 
    - SylixOS
    - Linux
    - OpenEuler
  tags:
    - realevo-stream
    - embedded-ide
    - workspace-management
    - device-management
    - build-deploy
    - sylixos
context: |
  本技能为 RealEvo-Stream IDE 的 AI 辅助开发工具，定义了 AI 与 IDE 交互的标准工具接口。
  
  适用场景：
  - 嵌入式开发工作空间的创建与管理
  - 多平台（SylixOS/Linux/OpenEuler）工程的创建与构建
  - 远程设备的注册、查看与配置管理
  - 工程/工作空间到目标设备的部署与更新
  
  前置条件：
  - 已安装 RealEvo-Stream IDE 并配置环境变量
  - 工具链目录位于 /opt/acoinfo/realevo-stream/ 下（可通过配置调整）
---

# RealEvo-Stream 嵌入式开发工具

## 工具概述

**RealEvo-Stream** 是一款面向嵌入式系统开发的综合性集成开发环境（IDE），提供从工作空间管理、代码编辑、编译构建、调试分析到固件部署的完整开发流程支持。

### 核心功能模块

| 模块名称       | 功能描述                                     |
| :--------- | :--------------------------------------- |
| **工作空间管理** | 支持 SylixOS、Linux、欧拉（Euler）等多平台工作空间的创建与管理 |
| **项目管理**   | 工程创建、配置、依赖管理                             |
| **代码编辑**   | 语法高亮、智能提示、代码导航                           |
| **编译构建**   | 支持多种编译器和构建系统                             |
| **调试分析**   | 硬件调试、性能分析、内存诊断                           |
| **固件部署**   | 烧录、更新、远程部署                               |

### 工具调用方式

所有功能通过 `scripts/cli.py` 命令行包装器调用，以子命令形式提供，无需编写 Python 脚本：

```bash
# 通用格式
python3 scripts/cli.py <command> --arg1=val1 --arg2=val2

# ── 无参数命令 ──
python3 scripts/cli.py get-product-series
python3 scripts/cli.py get-base-versions
python3 scripts/cli.py get-project-types

# ── 带参数命令 ──
python3 scripts/cli.py is-workspace --workspace-path=/path/to/ws
python3 scripts/cli.py get-project-params --project-type=Application
python3 scripts/cli.py build-all --workspace-path=/ws --project-name=myapp --os=sylixos

# ── 多参数命令 ──
python3 scripts/cli.py add-device --workspace-path=/ws --device-name=my-device \
    --device-address=192.168.1.100 --user-name=root --password=root \
    --os=SylixOS --platform=ARM_A9

# ── 列表参数（逗号分隔） ──
python3 scripts/cli.py init-workspace-by-base-version --workspace-path=/ws \
    --base-version=v2.0.0 --platforms=ARM_A9,X86_64

# ── 创建工程（kwargs 直接作为 --key=value 传入） ──
python3 scripts/cli.py create-project --workspace-path=/ws --project-type=Application \
    --project-name=my_app --debug-level=debug
```

**说明：**
- **参数**：通过 `--参数名=值` 传入，下划线可替换为连字符（如 `--project-type`）
- **返回值**：所有命令统一输出 JSON 格式到 stdout，形如 `{"status": "success"|"failed", "result": ..., "message": ...}`
- **错误处理**：调用失败时输出 `{"status": "error", "message": "..."}` 并返回非零退出码
- **帮助**：每个命令支持 `--help` 查看参数说明：`python3 scripts/cli.py <command> --help`
- **路径**：从工程根目录调用，或者用绝对路径指定 `scripts/cli.py`

> ⚠️ 不要直接调用 `scripts/tools.py` 中的函数，统一通过 `cli.py` 包装器调用。

***

## 模块一：工作空间管理

### 1.1 功能概述

工作空间是嵌入式开发的基础环境，包含项目源码、工具链配置、编译输出等。RealEvo-Stream 支持多种操作系统平台的工作空间初始化：

- **SylixOS 工作空间**：通过产品系列、Base 版本或 Base 工程三种方式初始化
- **Linux 工作空间**：支持 ARM64 和 X86 架构
- **欧拉（Euler）工作空间**：面向国产操作系统的开发支持

### 1.2 工具定义

| 工具名称                                       | 功能描述                       | 参数                                                                                                                  | 返回值            |
| :----------------------------------------- | :------------------------- | :------------------------------------------------------------------------------------------------------------------ | :------------- |
| `get_product_series`                       | 获取当前所有产品系列列表               | 无                                                                                                                   | 产品系列列表数组       |
| `get_base_versions`                        | 获取当前可用的 Base 版本列表          | 无                                                                                                                   | Base 版本列表数组    |
| `get_supported_platforms_by_base_version`  | 查看指定 Base 版本支持的目标平台        | `base_version`: Base 版本号                                                                                            | 平台列表数组         |
| `get_supported_platforms_by_base_project`  | 查看指定 Base 工程支持的目标平台        | `base_project_path`: Base 工程路径                                                                                      | 平台列表数组         |
| `get_available_toolchains`                 | 查看指定目录下可用的 toolchain 列表    | `toolchain_dir`: toolchain 目录路径                                                                                     | toolchain 列表数组 |
| `generate_toolchain_cmake`                 | 生成 toolchain.cmake 配置文件    | `toolchain_dir`: toolchain 目录, `toolchain_name`: toolchain 名称, `platform`: 目标平台, `cmake_path`: 生成文件路径               | 生成结果           |
| `init_sylixos_workspace_by_product_series` | 通过产品系列初始化 SylixOS 工作空间     | `workspace_path`: 工作空间目录, `product_series`: 产品系列名称                                                                  | 初始化结果          |
| `init_sylixos_workspace_by_base_version`   | 通过 Base 版本初始化 SylixOS 工作空间 | `workspace_path`: 工作空间目录, `base_version`: Base 版本号, `platforms`: 目标平台列表                                             | 初始化结果          |
| `init_sylixos_workspace_by_base_project`   | 通过 Base 工程初始化 SylixOS 工作空间 | `workspace_path`: 工作空间目录, `base_project_path`: Base 工程路径, `platforms`: 目标平台列表                                       | 初始化结果          |
| `init_linux_workspace`                     | 初始化 Linux 工作空间             | `workspace_path`: 工作空间目录, `platform`: 目标平台, `toolchain_cmake_path`: toolchain.cmake 路径, `rootfs_path`: rootfs 压缩包路径 | 初始化结果          |
| `init_euler_workspace`                     | 初始化欧拉工作空间                  | `workspace_path`: 工作空间目录, `platform`: 目标平台, `toolchain_cmake_path`: toolchain.cmake 路径, `rootfs_path`: rootfs 压缩包路径 | 初始化结果          |
| `is_workspace`                             | 检查指定路径是否为有效工作空间            | `workspace_path`: 工作空间目录                                                                                            | 布尔值            |

### 1.3 工作流程

#### 1.3.1 通过产品系列初始化 SylixOS 工作空间

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 get_product_series() 获取产品系列列表           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 让用户选择目标产品系列                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 调用 init_sylixos_workspace_by_product_series()    │
│         参数: workspace_path, product_series               │
└─────────────────────────────────────────────────────────────┘
```

#### 1.3.2 通过 Base 版本初始化 SylixOS 工作空间

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 get_base_versions() 获取可用 Base 版本列表      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 让用户选择目标 Base 版本                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 调用 get_supported_platforms_by_base_version()     │
│         参数: base_version                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 让用户选择目标平台（支持多选）                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 调用 init_sylixos_workspace_by_base_version()      │
│         参数: workspace_path, base_version, platforms      │
└─────────────────────────────────────────────────────────────┘
```

#### 1.3.3 通过 Base 工程初始化 SylixOS 工作空间

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 让用户确认 Base 工程路径                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 调用 get_supported_platforms_by_base_project()     │
│         参数: base_project_path                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 让用户选择目标平台（支持多选）                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 调用 init_sylixos_workspace_by_base_project()      │
│         参数: workspace_path, base_project_path, platforms │
└─────────────────────────────────────────────────────────────┘
```

#### 1.3.4 初始化 Linux 工作空间

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 让用户确认 toolchain 所在目录                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 调用 get_available_toolchains() 获取可用 toolchain  │
│         参数: toolchain_dir                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 让用户选择目标 toolchain                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 调用 generate_toolchain_cmake() 生成配置文件        │
│         参数: toolchain_dir, toolchain_name, platform,     │
│               cmake_path                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 让用户选择目标平台 (ARM64 | X86)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤7: 让用户确认 rootfs 压缩包路径                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤8: 调用 init_linux_workspace() 初始化工作空间           │
│         参数: workspace_path, platform, toolchain_cmake_path,│
│               rootfs_path                                  │
└─────────────────────────────────────────────────────────────┘
```

#### 1.3.5 初始化欧拉工作空间

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 让用户确认 toolchain 所在目录                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 调用 get_available_toolchains() 获取可用 toolchain  │
│         参数: toolchain_dir                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 让用户选择目标 toolchain                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 调用 generate_toolchain_cmake() 生成配置文件        │
│         参数: toolchain_dir, toolchain_name, platform,     │
│               cmake_path                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 让用户选择目标平台 (ARM64 | X86)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤7: 让用户确认 rootfs 压缩包路径                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤8: 调用 init_euler_workspace() 初始化工作空间           │
│         参数: workspace_path, platform, toolchain_cmake_path,│
│               rootfs_path                                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 使用示例

#### 示例1: 通过产品系列初始化 SylixOS 工作空间

```python
workspace_path = "/workspace/sylixos_project"
product_series_list = get_product_series()
# 用户选择: "product_A"
result = init_sylixos_workspace_by_product_series(workspace_path, "product_A")
```

#### 示例2: 通过 Base 版本初始化 SylixOS 工作空间

```python
workspace_path = "/workspace/sylixos_project"
base_versions = get_base_versions()
# 用户选择: "v2.0.0"
platforms = get_supported_platforms_by_base_version("v2.0.0")
# 用户选择: ["ARM_CORTEX_A9", "ARM_CORTEX_A53"]
result = init_sylixos_workspace_by_base_version(workspace_path, "v2.0.0", ["ARM_CORTEX_A9", "ARM_CORTEX_A53"])
```

#### 示例3: 通过 Base 工程初始化 SylixOS 工作空间

```python
workspace_path = "/workspace/sylixos_project"
base_project_path = "/projects/base_v2.0"
platforms = get_supported_platforms_by_base_project(base_project_path)
# 用户选择: ["ARM_CORTEX_A9"]
result = init_sylixos_workspace_by_base_project(workspace_path, base_project_path, ["ARM_CORTEX_A9"])
```

#### 示例4: 初始化 Linux 工作空间

```python
workspace_path = "/workspace/linux_project"
toolchain_dir = "/opt/toolchains"
toolchains = get_available_toolchains(toolchain_dir)
# 用户选择: "gcc-arm-8.3"
toolchain_cmake_path = f"{toolchain_dir}/toolchain.cmake"
generate_toolchain_cmake(toolchain_dir, "gcc-arm-8.3", "ARM64", toolchain_cmake_path)
platform = "ARM64"
rootfs_path = "/opt/rootfs/linux_rootfs.tar.gz"
result = init_linux_workspace(workspace_path, platform, toolchain_cmake_path, rootfs_path)
```

#### 示例5: 初始化欧拉工作空间

```python
workspace_path = "/workspace/euler_project"
toolchain_dir = "/opt/toolchains"
toolchains = get_available_toolchains(toolchain_dir)
# 用户选择: "gcc-arm-8.3"
toolchain_cmake_path = f"{toolchain_dir}/toolchain.cmake"
generate_toolchain_cmake(toolchain_dir, "gcc-arm-8.3", "ARM64", toolchain_cmake_path)
platform = "ARM64"
rootfs_path = "/opt/rootfs/euler_rootfs.tar.gz"
result = init_euler_workspace(workspace_path, platform, toolchain_cmake_path, rootfs_path)
```

***

## 模块二：工程管理

### 2.1 功能概述

工程管理模块提供嵌入式工程的创建、配置和管理功能，支持多种类型的工程模板，包括应用程序、库、内核模块、Python、JavaScript、Cython 以及源码工程等。

### 2.2 工具定义

| 工具名称                 | 功能描述            | 参数                                                                              | 返回值      |
| :------------------- | :-------------- | :------------------------------------------------------------------------------ | :------- |
| `get_project_types`  | 获取支持创建的工程类型列表   | 无                                                                               | 工程类型列表数组 |
| `get_project_params` | 获取指定工程类型所需的参数列表 | `project_type`: 工程类型                                                            | 参数字典     |
| `create_project`     | 在指定工作空间下创建工程    | `workspace_path`: 工作空间目录, `project_type`: 工程类型, `create_project_params`: 工程参数对象 | 创建结果     |
| `get_project_list`   | 获取工作空间中的项目列表    | `workspace_path`: 工作空间目录                                                      | 项目名称列表数组  |

### 2.3 支持的工程类型

| 工程类型                 | 描述                      | 分类       |
| :------------------- | :---------------------- | :------- |
| `Application`        | C++ 语言应用工程              | Template |
| `Library`            | C++ 语言库工程               | Template |
| `Kernel_Module`      | 内核模块工程                  | Template |
| `Python`             | Python 语言工程             | Template |
| `JavaScript`         | JavaScript 语言工程         | Template |
| `Cython`             | Cython(C + Python) 混合工程 | Template |
| `Source_CMake`       | CMake 源码工程              | Source   |
| `Source_Automake`    | Automake 源码工程           | Source   |
| `Source_RealEvo_IDE` | RealEvo IDE 源码工程        | Source   |

### 2.4 工程参数说明

不同类型工程所需的参数有所不同：

| 参数名            | 类型     | 说明                             | 适用工程                                                     |
| :------------- | :----- | :----------------------------- | :------------------------------------------------------- |
| `project_name` | string | 工程名称（必填）                       | 所有类型                                                     |
| `debug_level`  | string | 调试等级：debug\|release（默认release） | Application, Library, Kernel\_Module, Cython, Source\_\* |
| `build_tool`   | string | 构建工具：make\|ninja（默认make）       | Application, Library, Kernel\_Module, Cython, Source\_\* |
| `source_path`  | string | 源码路径                           | Source\_\*                                               |

### 2.5 工作流程

> **重要前置条件**：在创建工程之前，必须确保工作空间目录有效。

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 is_workspace(workspace_path) 检查工作空间有效性 │
└─────────────────────────────────────────────────────────────┘
                            ↓
               ┌────────────────────────────┐
               │  is_workspace 返回结果？   │
               └────────────────────────────┘
                     ↓是              ↓否
        ┌──────────────────┐  ┌─────────────────────────────────┐
        │  继续步骤3       │  │  提示用户：工作空间无效，需要先  │
        │                 │  │  初始化工作空间                  │
        └──────────────────┘  └─────────────────────────────────┘
                                       ↓
                        ┌──────────────────────────────────────┐
                        │  参考"模块一：工作空间管理"章节，     │
                        │  选择合适的方式初始化工作空间：        │
                        │  • 通过产品系列初始化 SylixOS 工作空间│
                        │  • 通过 Base 版本初始化 SylixOS 工作空间│
                        │  • 通过 Base 工程初始化 SylixOS 工作空间│
                        │  • 初始化 Linux 工作空间               │
                        │  • 初始化欧拉工作空间                 │
                        └──────────────────────────────────────┘
                                       ↓
                        ┌──────────────────────────────────────┐
                        │  工作空间初始化完成后，               │
                        │  重新调用 is_workspace() 验证        │
                        └──────────────────────────────────────┘
                                       ↓
                              验证通过，继续步骤3
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 调用 get_project_types() 获取工程类型列表           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 让用户选择目标工程类型                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 调用 get_project_params(project_type) 获取参数模板  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 让用户填写工程参数                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤7: 调用 create_project() 创建工程                      │
│         参数: workspace_path, project_type,                │
│               create_project_params                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.6 使用示例

#### 示例1: 创建应用工程

```python
workspace_path = "/workspace/sylixos_project"
project_types = get_project_types()
# 用户选择: "Application"
params = get_project_params("Application")
# 用户填写: {"project_name": "my_app", "debug_level": "debug", "build_tool": "make"}
result = create_project(workspace_path, "Application", **{"project_name": "my_app", "debug_level": "debug", "build_tool": "make"})
```

#### 示例2: 创建 Python 工程

```python
workspace_path = "/workspace/sylixos_project"
# 用户选择: "Python"
params = get_project_params("Python")
# 用户填写: {"project_name": "my_python_app"}
result = create_project(workspace_path, "Python", **{"project_name": "my_python_app"})
```

#### 示例3: 创建 CMake 源码工程

```python
workspace_path = "/workspace/sylixos_project"
# 用户选择: "Source_CMake"
params = get_project_params("Source_CMake")
# 用户填写: {"project_name": "my_source", "debug_level": "release", "build_tool": "ninja", "source_path": "/src/my_code"}
result = create_project(workspace_path, "Source_CMake", **{"project_name": "my_source", "debug_level": "release", "build_tool": "ninja", "source_path": "/src/my_code"})
```

***

## 模块三：设备管理

> 用于管理嵌入式开发环境中的设备配置，包括设备添加、信息查询和修改等功能

### 3.1 工具定义

| 工具名称                         | 功能描述            | 参数                                                                                                                                                                  |
| :--------------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `get_os_supported_platforms` | 获取指定操作系统支持的平台列表 | `os`（必填）：操作系统名称，如 Linux、OpenEuler、SylixOS                                                                                                                           |
| `add_device`                 | 添加设备到工作空间       | `workspace_path`（必填）：工作空间目录；`device_name`（必填）：设备名称；`device_address`（必填）：设备IP地址；`user_name`（必填）：登录用户名；`password`（必填）：登录密码；`os`（必填）：操作系统；`platform`（必填）：平台类型          |
| `get_device_list`            | 获取工作空间中的设备列表    | `workspace_path`（必填）：工作空间目录                                                                                                                                         |
| `see_device_info`            | 查看指定设备的详细信息     | `workspace_path`（必填）：工作空间目录；`device_name`（必填）：设备名称                                                                                                                  |
| `modify_device_info`         | 修改指定设备的信息       | `workspace_path`（必填）：工作空间目录；`device_old_name`（必填）：设备原名称；`device_new_name`：设备新名称；`device_address`：设备IP地址；`user_name`：登录用户名；`password`：登录密码；`os`：操作系统；`platform`：平台类型 |

### 3.2 工作流程

#### 添加设备流程

```
用户确认工作空间目录
    ↓
用户选择操作系统（Linux、OpenEuler、SylixOS）
    ↓
调用 get_os_supported_platforms(os) 获取该操作系统支持的平台列表
    ↓
用户提供设备信息（名称、IP、平台类型、用户名、密码等）
    ↓
调用 add_device() 添加设备
```

#### 查看设备信息流程

```
用户确认工作空间目录
    ↓
调用 get_device_list() 获取设备列表
    ↓
用户选择要查看的设备
    ↓
调用 see_device_info() 查看详细信息
```

#### 修改设备信息流程

```
用户确认工作空间目录
    ↓
调用 get_device_list() 获取设备列表
    ↓
用户选择要修改的设备（目标设备）
    ↓
调用 see_device_info() 查看当前信息
    ↓
用户确定目标操作系统（如需修改）
    ↓
调用 get_os_supported_platforms(os) 获取该操作系统支持的平台列表
    ↓
用户提供新的设备信息（名称、IP、平台类型、用户名、密码等，可选部分修改）
    ↓
调用 modify_device_info() 修改设备信息
```

### 3.3 使用示例

#### 示例1：添加设备

```
# 用户请求: 添加一个设备
# 对话历史: 用户已经在工作空间 /home/test/workspace 下

# Step 1: 用户选择操作系统为 SylixOS

# Step 2: 获取该操作系统支持的平台列表
result = get_os_supported_platforms("SylixOS")
# 返回: ["ARM_926H", "ARM_926S", "ARM_A5", "ARM64_GENERIC", ...]

# Step 3: 用户选择平台为 ARM64_GENERIC，并提供设备信息
# 用户填写: {"device_name": "10.5.0.117", "device_address": "10.99.99.3", "user_name": "root", "password": "root", "os": "SylixOS", "platform": "ARM64_GENERIC"}
result = add_device("/home/test/workspace", "10.5.0.117", "10.99.99.3", "root", "root", "SylixOS", "ARM64_GENERIC")
```

#### 示例2：查看设备列表

```
# 用户请求: 查看工作空间中的设备列表
# 对话历史: 用户已经在工作空间 /home/test/workspace 下

result = get_device_list("/home/test/workspace")
# 返回: ["10.5.0.117", "10.14.1.28"]
```

#### 示例3：查看设备详细信息

```
# 用户请求: 查看设备 10.5.0.117 的详细信息
# 对话历史: 用户已经在工作空间 /home/test/workspace 下

result = see_device_info("/home/test/workspace", "10.5.0.117")
# 返回: {"name": "10.5.0.117", "ip": "10.99.99.3", "platform": "ARM64_GENERIC", "os": "SylixOS", "telnet": 23, "ssh": 22, "ftp": 21, "gdb": 1234, "user": "root", "password": "root"}
```

#### 示例4：修改设备信息

```
# 用户请求: 修改设备 10.5.0.117 的IP地址和平台
# 对话历史: 用户已经在工作空间 /home/test/workspace 下

# Step 1: 获取设备列表
result = get_device_list("/home/test/workspace")
# 返回: ["10.5.0.117", "10.14.1.28"]

# Step 2: 用户选择要修改的设备 10.5.0.117，查看当前信息
result = see_device_info("/home/test/workspace", "10.5.0.117")
# 返回: {"name": "10.5.0.117", "ip": "10.99.99.3", "platform": "ARM64_GENERIC", "os": "SylixOS", ...}

# Step 3: 用户确定目标操作系统为 SylixOS（保持不变），获取平台列表
result = get_os_supported_platforms("SylixOS")
# 返回: ["ARM_926H", "ARM_926S", "ARM_A5", "ARM64_GENERIC", "ARM64_A55", ...]

# Step 4: 用户提供新的设备信息（修改名称、IP和平台）
# 用户填写: {"device_new_name": "Device_A", "device_address": "10.99.99.10", "platform": "ARM64_A55"}
result = modify_device_info("/home/test/workspace", "10.5.0.117", "Device_A", "10.99.99.10", None, None, None, "ARM64_A55")
```

***

## 模块四：构建

### 4.1 功能概述

构建模块提供工程的编译构建功能，支持清理、配置、构建、安装等完整的构建流程，支持 SylixOS、Linux、欧拉（Euler）等多种操作系统平台。

### 4.2 工具定义

| 工具名称         | 功能描述              | 参数                                                                                                              | 返回值    |
| :----------- | :---------------- | :-------------------------------------------------------------------------------------------------------------- | :------ |
| `build_clean`   | 清理工程构建产物          | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `os`: 操作系统（sylixos\|linux\|openeuler）                          | 清理结果    |
| `build_config`  | 配置工程构建选项          | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `os`: 操作系统（sylixos\|linux\|openeuler）                          | 配置结果    |
| `build_build`   | 构建工程              | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `os`: 操作系统（sylixos\|linux\|openeuler）                          | 构建结果    |
| `build_install` | 安装工程到目标系统        | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `os`: 操作系统（sylixos\|linux\|openeuler）                          | 安装结果    |
| `build_all`     | 依次执行构建步骤（clean->config->build->install） | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `os`: 操作系统（sylixos\|linux\|openeuler）                          | 构建结果    |
| `build_uninstall` | 卸载已安装的工程         | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `os`: 操作系统（sylixos\|linux\|openeuler）                          | 卸载结果    |

### 4.3 工作流程

#### 4.3.1 完整构建流程

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 get_project_list(workspace_path) 获取项目列表   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 让用户选择目标工程                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 让用户选择操作系统 (sylixos | linux | openeuler)   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 调用 build_all() 执行完整构建流程                    │
│         参数: workspace_path, project_name, os             │
│         内部依次执行: clean → config → build → install      │
└─────────────────────────────────────────────────────────────┘
```

#### 4.3.2 分步构建流程

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 get_project_list(workspace_path) 获取项目列表   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 让用户选择目标工程                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 让用户选择操作系统 (sylixos | linux | openeuler)   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 让用户选择构建步骤（支持多选）                        │
│         可选步骤: clean, config, build, install             │
│         用户选择示例: ["clean", "build", "install"]         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 根据用户选择依次执行构建步骤                          │
│         按顺序执行: clean → config → build → install        │
│         只执行用户选中的步骤                                 │
│                                                             │
│         示例(用户选择了 clean, build, install):              │
│         ① 调用 build_clean() 清理构建产物                    │
│            参数: workspace_path, project_name, os           │
│         ② 调用 build_build() 构建工程                       │
│            参数: workspace_path, project_name, os           │
│         ③ 调用 build_install() 安装工程                      │
│            参数: workspace_path, project_name, os           │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 使用示例

#### 示例1: 执行完整构建

```python
workspace_path = "/workspace/sylixos_project"
project_name = "my_app"
os_name = "sylixos"
result = build_all(workspace_path, project_name, os_name)
```

#### 示例2: 分步构建

```python
workspace_path = "/workspace/linux_project"
project_name = "my_lib"
os_name = "linux"

result_clean = build_clean(workspace_path, project_name, os_name)
result_config = build_config(workspace_path, project_name, os_name)
result_build = build_build(workspace_path, project_name, os_name)
result_install = build_install(workspace_path, project_name, os_name)
```

#### 示例3: 卸载工程

```python
workspace_path = "/workspace/sylixos_project"
project_name = "my_app"
os_name = "sylixos"
result = build_uninstall(workspace_path, project_name, os_name)
```

***

## 模块五：部署

### 5.1 功能概述

部署模块提供将工程或工作空间部署到目标设备的功能，支持将编译好的固件、应用程序等上传到嵌入式设备，实现远程部署和更新。

### 5.2 工具定义

| 工具名称            | 功能描述          | 参数                                                                                | 返回值    |
| :-------------- | :------------ | :-------------------------------------------------------------------------------- | :------ |
| `upload_project`  | 部署工程到设备       | `workspace_path`: 工作空间目录, `project_name`: 工程名称, `device_name`: 设备名称             | 部署结果    |
| `upload_workspace` | 部署工作空间到设备    | `workspace_path`: 工作空间目录, `device_name`: 设备名称                                   | 部署结果    |

### 5.3 工作流程

#### 5.3.1 部署工程到设备

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 get_project_list(workspace_path) 获取项目列表   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 让用户选择要部署的工程                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 调用 get_device_list(workspace_path) 获取设备列表    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 让用户选择目标设备                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 调用 upload_project() 部署工程到设备                  │
│         参数: workspace_path, project_name, device_name    │
└─────────────────────────────────────────────────────────────┘
```

#### 5.3.2 部署工作空间到设备

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 让用户确认工作空间目录                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 调用 get_device_list(workspace_path) 获取设备列表    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 让用户选择目标设备                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 调用 upload_workspace() 部署工作空间到设备             │
│         参数: workspace_path, device_name                  │
└─────────────────────────────────────────────────────────────┘
```

### 5.4 使用示例

#### 示例1: 部署工程到设备

```python
workspace_path = "/workspace/sylixos_project"
project_name = "my_app"
device_name = "Device_A"
result = upload_project(workspace_path, project_name, device_name)
```

#### 示例2: 部署工作空间到设备

```python
workspace_path = "/workspace/linux_project"
device_name = "Device_B"
result = upload_workspace(workspace_path, device_name)
```

***

## 附录

### 支持的操作系统平台

| 操作系统          | 支持的平台                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| :------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Linux**     | ARM64, X86                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **OpenEuler** | ARM64, X86                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **SylixOS**   | ARM\_926H, ARM\_926S, ARM\_920T, ARM\_A5, ARM\_A5\_SOFT, ARM\_A7, ARM\_A7\_SOFT, ARM\_A8, ARM\_A8\_SOFT, ARM\_A9, ARM\_A9\_SOFT, ARM\_A15, ARM\_A15\_SOFT, ARM\_V7A, ARM\_V7A\_SOFT, ARM64\_A53, ARM64\_A55, ARM64\_A57, ARM64\_A72, ARM64\_GENERIC, MIPS32, MIPS32\_SOFT, MIPS32\_R2, MIPS32\_R2\_SOFT, MIPS64\_R2, MIPS64\_R2\_SOFT, MIPS64\_LS3A, MIPS64\_LS3A\_SOFT, x86\_PENTIUM, x86\_PENTIUM\_SOFT, X86\_64, PPC\_750, PPC\_750\_SOFT, PPC\_464FP, PPC\_464FP\_SOFT, PPC\_E500V1, PPC\_E500V1\_SOFT, PPC\_E500V2, PPC\_E500V2\_SOFT, PPC\_E500MC, PPC\_E500MC\_SOFT, PPC\_E5500, PPC\_E5500\_SOFT, PPC\_E6500, PPC\_E6500\_SOFT, SPARC\_LEON3, SPARC\_LEON3\_SOFT, SPARC\_V8, SPARC\_V8\_SOFT, RISCV\_GC32, RISCV\_GC32\_SOFT, RISCV\_GC64, RISCV\_GC64\_SOFT, LOONGARCH64, LOONGARCH64\_SOFT, CSKY\_CK807, CSKY\_CK807\_SOFT, CSKY\_CK810, CSKY\_CK810\_SOFT, CSKY\_CK860, CSKY\_CK860\_SOFT, SW6B, SW6B\_SOFT |

### 工具链支持

- ARM GCC (arm-none-eabi-gcc)
- ARM64 GCC (aarch64-linux-gnu-gcc)
- X86 GCC (x86\_64-linux-gnu-gcc)
- 其他自定义工具链

