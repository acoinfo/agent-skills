# 各类型工程端到端流程

以下为阶段配方，需替换示例路径/名称，并核对授权、目标平台、真实凭据和产物；不是整份文档可顺序执行的脚本。命令参数含义见 [native-commands.md](native-commands.md)，阻塞点与排错见 [constraints.md](constraints.md)。

通用规则：每条原生命令执行时默认用 `timeout --kill-after=5s <秒> … </dev/null` 包裹；表内省略该包装以便阅读。受控确认输入例外见 [constraints.md](constraints.md#2-避开不可靠的非交互接口)。`--project` 在工程目录内可省略；每个阶段验收通过后再进入下一阶段。

## 0. 公共前置

```bash
export PATH=/opt/acoinfo/realevo-stream/bin:$PATH
sudo -n true || echo "当前原生特权步骤受阻；封装可用环境预置密码预认证"
python3 "<Skill目录>/scripts/cli.py" check          # result.installed 且 result.usable
python3 "<Skill目录>/scripts/cli.py" license show   # result.status == VALID
```

## 1. SylixOS C/C++ 应用（基线）

```bash
mkdir -p /path/to/ws && cd /path/to/ws
rl-workspace init --version=lts_3.6.5 --platform=ARM64_GENERIC --createbase=true
# 或 --product=ARC1000；或 --base=/path/to/base --platform=ARM64_GENERIC
rl-workspace show

rl-project create --name=Test_App --type=cmake --template=app --debug-level=release
# 编辑 Test_App/src/main.cpp

rl-build all --project=Test_App --parallel=4

# 由安全渠道预置设备 Test_Device：真实 IP/凭据，os=sylixos，platform=ARM64_GENERIC
# 缺少配置时停止部署/运行，仍可完成本地构建；不得使用默认 root/root
rl-upload project --device=Test_Device --project=Test_App

project-run-test --device=Test_Device --project=Test_App \
  --path=Test_App/install-sylixos/ARM64_GENERIC/apps/Test_App/Test_App
# 或 telnet 到设备执行 /apps/Test_App/Test_App

rl-build symbolcheck --project=Test_App                  # 可选
rl-package package --project=Test_App --type=target --upload=no   # 可选
```

**验收点**

| 阶段 | 验收 |
| --- | --- |
| 初始化 | `.realevo/config.json` 的 `base` 非空、`platforms` 含目标平台；`.realevo/arch/<P>/rootfs` 存在 |
| 创建工程 | `.rlproject/.rlconfig` 存在，`build_type`/`template` 正确 |
| 构建 | 退出码 0 **且** `install-sylixos/<P>/apps/<工程>/<工程>` 存在，日志含 `Copying files from .../install-sylixos/<P> to .../.realevo/arch/<P>/rootfs/` |
| 部署 | 日志含 `Successfully uploaded ... --> /apps/<工程>/<工程>` 且文件数 > 0，核对远端实际文件 |
| 运行 | 设备输出符合源码预期，核对远端退出状态；长期程序按明确的运行验收条件判定，超时后检查/停止残留远端进程 |

## 2. 动态库与内核模块

```bash
rl-project create --name=Test_Lib --type=cmake --template=lib
rl-build all --project=Test_Lib --parallel=4

rl-project create --name=Test_Ko --type=cmake --template=ko      # 用 sylixos.ko.cmake
rl-build all --project=Test_Ko --parallel=4

rl-project create --name=Test_Ide --type=realevo --template=app
rl-project create --name=Test_IdeLib --type=realevo --template=shared_lib
rl-project create --name=Test_IdeKo --type=realevo --template=ko
rl-build all --project=Test_Ide --parallel=4
```

- realevo 类型构建目录是 `build/<P>/<Release|Debug>`（**不是** `build-sylixos/<P>`），安装产物仍是 `install-sylixos/<P>`。
- `lib` 只适用于 `--type=cmake`；realevo 动态库用 `shared_lib`。

## 3. BSP

```bash
rl-project create --name=Test_BSP --type=realevo_bsp --template=arm64-none --platform=ARM64_GENERIC --debug-level=release
# 或 --type=cmake_bsp --template=arm64-none
rl-build all --project=Test_BSP --os=sylixos --parallel=4

# 使用已安全预置、平台匹配的 Test_Device
rl-upload project --device=Test_Device --project=Test_BSP
```

- `--template=<架构>-<板卡>`，架构必须与工作空间目标平台匹配；`--os` 固定 `sylixos`。
- 产物：`build/<P>/<Release|Debug>/{<工程>.elf,.bin,.siz}` 与 `install-sylixos/<P>/lib/<工程>/<工程>.elf` → rootfs 同路径。
- 上传路径由工程配置决定：`realevo_bsp` 用 `.reproject` 的 `<UploadPath>`；`cmake_bsp` 用 `CMakeLists.txt` 的 `install(TARGETS ... DESTINATION "lib")`。
- **上传仅完成文件拷贝，不会自动使 BSP 生效。**

## 4. Python / JavaScript

```bash
rl-device install --name=Test_Device --soft=python        # 设备默认不带运行时
rl-project create --name=Test_Python --type=python --template=common
rl-build install --project=Test_Python                    # 只 install
rl-upload project --device=Test_Device --project=Test_Python
# 设备端： python /apps/python/Test_Python/test_main.py

# 此步骤更新 startup.sh 并重启设备；仅在授权覆盖该影响时执行
rl-device install --name=Test_Device --soft=javascript
rl-project create --name=Test_JavaScript --type=javascript --template=common
rl-build install --project=Test_JavaScript
rl-upload project --device=Test_Device --project=Test_JavaScript
# 设备端： cd /apps/javascript/Test_JavaScript && ./main.js
```

- python/javascript 的 `config`/`build` 阶段跳过，用 `install` 或 `all`；cython/go 跳过 `config`，`build` 仍执行实际编译。
- 运行时安装仅支持 SylixOS；JavaScript 运行时安装会更新 `startup.sh` 并**重启设备**。

## 5. Cython

```bash
rl-tools install --soft=cpython-crossenv          # 交叉编译环境，不自带
rl-project create --name=Test_Cython --type=cython --template=common
rl-build all --project=Test_Cython                # 产出 whl
rl-upload project --device=Test_Device --project=Test_Cython
# 设备端：
#   python3 -m pip install /usr/dist/Test_Cython/<pkg>-<ver>-cp312-cp312-sylixos_aarch64.whl
#   python3 /usr/bin/<pkg>
rl-package install2device --package=@python/pip --device=Test_Device   # 设备无 pip 时
```

- 产物是 wheel：`install-sylixos/<P>/usr/dist/<工程>/*.whl`。
- **构建前必须确认 `sudo -n true` 通过**：cython 构建路径含无 `-n` 的 sudo 且吞错误，无免密时会静默挂起。
- 设备端以 root 运行 pip 有风险，建议虚拟环境。

## 6. Go

```bash
which go          # 期望指向 *-sylixos/bin/go；未装则 create 直接失败
rl-project create --name=Test_Go --type=go --template=common
rl-build all --project=Test_Go
rl-upload project --device=Test_Device --project=Test_Go
# 设备端： cd /apps/go/Test_Go && ./Test_Go
```

- **Go 工程不在工作空间根**，而在 `<ws>/go/src/<工程>`；`<ws>/go/bin` 不被使用。
- 由于工程位置特殊，`rl-build`/`rl-upload` 必须显式传 `--project=`。

## 7. ROS 2

```bash
# 三套环境，按顺序
rl-package install2device --device=Test_Device --package=@sylixos-middleware/ros2_jazzy
rl-tools install --soft=colcon
rl-package install --package=@sylixos-middleware/ros2_jazzy-devel

rl-project create --name=Test_ROS2 --type=ros2 --template=common --platform=ARM64_GENERIC

cd Test_ROS2/src
rl-ros create test_ros_package --build-type ament_cmake --dependencies rclcpp std_msgs
cd ..

rl-colcon build --merge-install
rl-upload project --device=Test_Device --project=Test_ROS2
# 设备端： /apps/ros2/lib/<包>/<节点>
```

- 环境未装好时 `rl-project create --type=ros2` 会打印 `Arch directory not found` **但仍返回 0**。
- 构建用 `rl-colcon`（不是 `rl-build`）；`all` 不可用。
- 设备要求 SylixOS ≥ 3.5.2，ARCH 仅 `ARM64_GENERIC`、`X86_64`；ROS 2 工程文件部署到设备 `/apps/ros2`。

## 8. 中间件移植（`--source`）

```bash
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new'

rl-project create --name=middleware_zlib --source=zlib.tar.gz --type=cmake
rl-build all --project=middleware_zlib --parallel=4
```

- `--source` 支持本地目录、压缩包（`zip/tar.gz/tgz/tar.bz2/tar.xz/tar.zst/tar`）、git 仓库（可配 `--branch`）；提供后被强制为 `app` 模板。
- 多个主配置文件时先确定要用的主配置。只有自动第 1 个确实符合预期才加 `--quiet`；否则提供明确选择或整理独立源目录，不能盲选。
- 目标目录需干净（`unzip` 未加 `-o`）。

## 9. Linux / OpenEuler

三种分支分别使用独立的新工作空间，不可在同一目录顺序重初始化。

**Linux cross**（已有匹配 ARM64 的工具链和 rootfs）：

```bash
mkdir -p /path/to/linux-cross-ws && cd /path/to/linux-cross-ws
rl-workspace init --os=linux --linux_platform=ARM64 \
  --linux_toolchain=/opt/toolchains/aarch64-linux.toolchain.cmake \
  --linux_rootfs=/opt/sysroots/linux-arm64.tar.gz
rl-project create --name=Linux_App --type=cmake --template=app
# 编辑 Linux_App/src/main.cpp，使用目标平台支持的接口
rl-build all --project=Linux_App --os=linux --platforms=ARM64
# 验收 Linux_App/install-linux/ARM64/apps/Linux_App/Linux_App
# 使用安全预置设备 LinuxDev：os=linux，platform=ARM64，真实 IP/凭据
rl-upload project --device=LinuxDev --project=Linux_App
# 在远端检查实际上传路径与文件，运行并验证输出和退出状态
```

**Linux native**（以下仅用于 X86_64 宿主；其他宿主须替换匹配平台和工具链）：

```bash
mkdir -p /path/to/linux-native-ws && cd /path/to/linux-native-ws
rl-workspace init --os=linux --linux_platform=X86_64 \
  --linux_toolchain=/opt/toolchains/x86_64-linux.toolchain.cmake --linux_rootfs=/
rl-project create --name=Native_App --type=cmake --template=app
rl-build all --project=Native_App --os=linux --platforms=X86_64
# 验收安装目录后，在宿主运行（不要执行原生远端启动命令）
timeout --kill-after=5s 30 ./Native_App/install-linux/X86_64/apps/Native_App/Native_App </dev/null
```

**OpenEuler cross**：

```bash
mkdir -p /path/to/openeuler-cross-ws && cd /path/to/openeuler-cross-ws
rl-workspace init --os=openeuler --openeuler_platform=ARM64 \
  --openeuler_toolchain=/opt/toolchains/aarch64-openeuler.toolchain.cmake \
  --openeuler_rootfs=/opt/sysroots/openeuler-arm64.tar.gz
rl-project create --name=Euler_App --type=cmake --template=app
rl-build all --project=Euler_App --os=openeuler --platforms=ARM64
# 验收 Euler_App/install-openeuler/ARM64/apps/Euler_App/Euler_App
# 使用安全预置设备 EulerDev：os=openeuler，platform=ARM64，真实 IP/凭据
rl-upload project --device=EulerDev --project=Euler_App
# 核对远端上传路径、运行输出及退出状态
```

- 平台值只能是 `ARM64|X86|X86_64|RISCV|LOONGARCH`，工具链必填。每个初始化后核对对应 `<os>_platforms`、工具链文件和 staging，再创建工程。
- native：rootfs 规范化为 `/`，staging 为空目录；仍传工具链文件，不覆盖文件中自设的 sysroot；`install` 不合并 workspace rootfs。
- cross：使用 staging 作为 `CMAKE_SYSROOT`，核对 rootfs 解包层级和 ABI；`install` 合并进 `.realevo/<os>/<P>/rootfs`。
- 部署 OS/platform 从设备配置读取；`project` 部署工程安装目录，`workspace` 部署 staging。native 的空 staging 不能用于整工作空间部署。
- 缺设备或安全凭据只停止部署，保留本地构建/验证结果。Linux/OpenEuler 不使用仅支持 SylixOS 的 `project-run-test`。

## 10. 打包与发布

```bash
# 由安全渠道预置受保护的 Armory 账号/仓库/组织配置；不要通过 argv 提交真实密码
# 缺少配置时停止依赖账号的下载/发布，离线打包按实际需求继续
rl-package package --project=Test_App --type=target --upload=no
rl-package search --package=@sylixos-middleware/openssl-devel
rl-package install --package=@sylixos-middleware/openssl-devel --dependent=no
rl-package install2device --package=@sylixos-middleware/ros2_jazzy --device=Test_Device
```

- `--type` 可取 `develop`（开发包）、`source`（源码包）、`target`（设备包）。
- 白名单取 `.rlconfig.package.allowlist`，README 取 `.rlproject/README.md`，默认输出工作空间 `rlpackage/`。
- `rl-package install` 仅适用于 SylixOS 工作空间（要求 `.realevo/arch`）。

## 11. ECS 容器

```bash
rl-tools install --soft=ecsc        # 需先装 Node.js + npm

rl-ecs create --platform=arm64 --bundlepath=./bundle
rl-ecs config --bundlepath=./bundle --components=<组件> --parameter="<启动参数>"
rl-ecs package --name=<镜像名> --tag=latest --bundlepath=./bundle \
  --targetpath=./out --targetname=<包名>.tar
rl-ecs upload --device=<设备名> --tarpath=./out/<包名>.tar --targetpath=/apps
rl-ecs load --device=<设备名> --tarpath=./out/<包名>.tar --targetpath=/apps --containerid=<ID>
rl-ecs systemcallgen --path=<符号文件> --name=<名> --startnumber=1200

# 使用安全预置的 ECSM 镜像源；本基线不得使用 set/update --active
# 需要设置源而无安全渠道时停止该阶段，不把密码放入 argv
rl-ecsm show                      # 取 imageid
rl-ecsm pull --id=<已配置源ID> --imageid=<ID> --path=<本地目录>
rl-ecsm push --id=<已配置源ID> --path=<镜像文件>
```

- `rl-ecs --platform` 用包架构标签（`arm64` 等），与工作空间 Platform 名不同。
- `rl-ecsm pull` 无总截止时间，必须 `timeout`；`rl-ecs save` 的 FTP 通路必然失败。
