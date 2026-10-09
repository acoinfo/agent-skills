# 限制、错误处理与排错

以下行为针对 [SKILL.md](../SKILL.md) 所列本机 3.0.0 基线。命令集没有统一非交互开关，须由调用方控制 stdin 与截止时间。

## 1. 非交互执行规范

```bash
# 总超时 + 关闭 stdin
timeout --kill-after=5s 1800 rl-build all --project=App </dev/null

# 原生命令需要有效非交互 sudo 权限；封装另支持密码预认证
sudo -n true || echo "当前阶段的特权操作不可执行；其他阶段可继续"

# 抑制 git/ssh 凭据交互
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new'
```

- 不要用 `cmd | tail` 后取 `$?`（那是 `tail` 的退出码）。取真实退出码：`cmd >out 2>&1; rc=$?`。
- 不要假定长任务具有总截止时间；原生命令用外层 `timeout --kill-after=5s`，保留日志以区分慢与挂起。若包含 sudo/脱离进程组的后台进程，超时后检查残留；本地超时不保证远端进程停止。

## 2. 避开不可靠的非交互接口

| 命令 | 触发条件 | 后果 / 替代 |
| --- | --- | --- |
| `rl-project update --platform` | 工作空间**平台数 ≥ 2** 且 stdin 为 EOF | `while true` + `read` 无 EOF 处理 → 无限自旋。在核对平台后原子更新 `.rlconfig` 的 `.platform`，再重跑构建配置（见下文） |
| `rl-tools exportcmake` | 任意（**无 `--platform` 参数**，强制 `select`） | Bash `select` 在 EOF 会退出循环，但后续代码可能在未选平台状态继续执行。改从 `.realevo/config.json` 与 `rl-build config` 日志读取 |

注：`rl-project update --platform` 在只有 1 个平台时自动选中。多平台替代方案：从当前 OS 的工作空间平台列表核对目标；备份工程 `.rlproject/.rlconfig` 到同目录受保护文件；用 `jq --arg platform "$P" '.platform = $platform'` 写临时文件，经 `jq -e` 检查且保留其他字段后原子替换，再运行 `rl-build config --project=<工程> --os=<OS>` 并核对产物。不要为选择工程平台改写工作空间的全部平台配置。

已获授权的卸载提供受控确认输入，不能再附加 `</dev/null`：

```bash
set -o pipefail
printf 'y\n' | timeout --kill-after=5s 300 rl-package uninstall --package=@namespace/package
# 同时检查退出码、未出现 Uninstall cancelled.，以及包记录/文件删除结果
```

## 3. 会等待输入（加参数消除）

| 命令 | 触发条件 | 消除方式 |
| --- | --- | --- |
| `rl-workspace init` | `--linux_toolchain`/`--openeuler_toolchain` 指向**目录**且扫出 ≥2 个前缀 | 优先传已核验 `.cmake`；自有可写目录才允许生成，多前缀勿盲选 |
| `rl-project create --source=<目录>` | 存在多个主 `CMakeLists.txt`/`configure` | 先确定正确主配置；确认自动第 1 个符合预期后才用 `--quiet` |
| `rl-project create --type=ros2` / `realevo_bsp` / `cmake_bsp` | 平台数 ≥2 且未指定平台 | 显式传 `--platform=<单一平台>`；**`--quiet` 无效** |
| `rl-tools update_lcsproxy` | 未传 `--type=` | 必须传 `--type=usbkey\|server\|http` |
| `rl-tools update` | `--revert` 默认 `true` 且目标版本 ≤ 当前版本 | 升级到更高版本；避免回退路径 |
| `rl-package uninstall` | 任意（无条件 `[y/N]`，无 `-y`） | `printf 'y\n' \| rl-package uninstall ...`，并**解析 stdout** |
| `rl-device upload` | `ftp -nv` + `mput *` 无 `prompt off` | **改用 `rl-upload`** |
| `git clone`（`rl-project --source=<git>`） | 私有仓库 / 未知主机键 | `GIT_TERMINAL_PROMPT=0` + 预置 known_hosts |
| `unzip`（`rl-project --source=<zip>`） | 目标已存在同名文件 | 使用新的空目标目录；已有数据需先核对删除授权 |

`--quiet` 分工：`rl-workspace` 消除工具链多前缀选择；`rl-project create` 只消除多主配置文件选择（不影响平台菜单）；`rl-project update/reconfig/show` **不接受** `--quiet`。

## 4. 可能永久挂起

| 命令 | 风险 | 处理 |
| --- | --- | --- |
| `project-run-tools`（SSH 路径） | 发送 `"<cmd> &"` 不带 `exit`，可能永不返回 | 外层 `timeout`；优先 Telnet 或 `project-run-test` |
| `project-run-test` / `project-run-tools`（Telnet） | 轮询至远程程序结束 | 外层 `timeout` + 备用 `SIGINT` |
| cython 构建（`rl-build build/all`） | 内部 `sudo rm -rf`/`ln -s` 无 `-n` 且 `2>/dev/null` 吞错误 | **构建前 `sudo -n true` 必须通过** |
| `rl-package install/search/package`、`rl-tools getarmory` | 底层 `armory` 无超时 | 外层 `timeout`；先由安全渠道提供已受保护的 Armory 配置 |
| `rl-ecsm pull` | 下载循环无总截止时间 | 外层 `timeout` |
| `rl-tools install`（colcon/go/ecsc/fastddsgen） | `apt`/`npm`/`pip`/`git clone` 无超时，apt 锁无上限 | 外层 `timeout`；预装依赖避免联网 |

## 5. 成功判定：不要只看退出码

对创建/构建/安装，检查退出码、预期产物与业务错误；查询按结果字段验收，卸载按删除结果验收，运行按远端输出与退出状态验收。已有旧产物不能证明本次成功。

| 情形 | 现象 | 判定 |
| --- | --- | --- |
| `rl-project create --type=ros2` 环境缺失 | 打印 `Arch directory not found`，**退出码 0** | 查 stdout + 产物 |
| `rl-package uninstall` 非交互 | 打印 `Uninstall cancelled.`，**退出码 0** | 解析 stdout |
| `rl-tools install` / `update` 部分失败 | **退出码 0**，输出含 `[ERROR]` / `Found N installation failures`（N > 0） | 解析输出（`cli.py install-sdk` 已处理） |
| `rl-build symbolcheck` 有未解析符号 | **不改变退出码** | 读报告文本 |
| `rl-device add --os=linux` 平台非法 | **退出码 255**（非 1） | 读 `ERROR:` 行 |

## 6. 常见错误 → 处理

| 错误信息 | 原因 / 处理 |
| --- | --- |
| `'--platform=' parameter is required.` | `rl-workspace init` 非产品模式缺 SylixOS 平台 → 补 `--platform=`；产品模式核对 SDK 映射 |
| `--toolchain parameter is required when --os=linux.` | 缺工具链 → 补 `--linux_toolchain=`/`--openeuler_toolchain=` |
| `--linux_rootfs parameter '<X>' is not a valid file or directory.` | rootfs 路径不存在 → 给存在的目录/tar.gz，native 用 `/` |
| `Platform <X> is not supported.` | 平台不在 63 项白名单 → 用 [白名单](native-commands.md) 中的名字 |
| `The linux device platform must be one of 'ARM64\|X86\|X86_64\|RISCV\|LOONGARCH'` | `rl-device --os=linux` 传了 SylixOS 平台名 |
| `No SDK found for product <X>` | `--product` 系列不存在 → 查 `pkg/product/` |
| `Missing required keys (base, mularch) in config.json.` | `rl-build` 读不到有效工作空间配置 → SylixOS 核对工作空间、`base` 和 `mularch`；Linux/OpenEuler 不要求 SylixOS Base |
| `does not support common template` | `--type=cmake --template=common` → cmake 用 `app\|lib\|ko\|...` |
| `Either '--source' or '--template' parameters is required.` | `rl-project create` 两者都缺 → 二选一 |
| `Go is not installed. Please install Go first.` | 未装 SylixOS Go 环境 |
| `Arch directory not found: <ws>/.realevo/arch` | 工作空间未初始化 SylixOS 平台，或 ROS 2 环境未装 |
| `Not find device: <名>` | `rl-upload` 目标设备未登记 → 先 `rl-device add` |
| `Device '<名>' does not exist in divicelist.json` | `rl-device update/delete` 设备不存在 |
| `Invalid IP address format.` / `'platform' parameter is required.` | `rl-device add` 缺/错 `--ip`、`--platform` |
| `Unrecognized subcommand 'all'.` | `rl-colcon all` 未实现 → 用 `clean`/`build`/`list` |
| `Unsupported parameter: --quiet` | 对 `rl-project update/reconfig/show` 传了 `--quiet` |
| `The current directory is not a workspace directory, nothing to clean.` | `init` 在非工作空间执行（**正常**，init 先 clean）；后面还有 `ERROR` 才是问题 |
| `Missing or invalid ... toolchain` | 工具链路径无效 / 目录型未生成 `.toolchain.cmake` → 检查 `*-gcc`/`*-g++`/`*-ld` 前缀与目录可写 |
| `Missing ... rootfs staging directory` | `.realevo/<os>/<P>/rootfs` 被删 → 重新初始化（native 也**不能删**该空目录） |
| CMake 找不到头文件/库 | cross：查 `CMAKE_SYSROOT`/rootfs ABI/层级；native：查宿主开发包与工具链自设变量。**不要**改用统一 `--rootfs` |
| `pkg-config` 找错包 | 命令集不设置 `PKG_CONFIG_SYSROOT_DIR`/`PKG_CONFIG_LIBDIR` → 自行设置 |
| `Running 'ninja' '--version'` 报错 | 默认不含 ninja → `sudo apt update && sudo apt install ninja-build` |

## 7. 受保护路径与破坏性操作

**禁止手工修改以绕过命令层错误**：`compiler/**`、`config/cmake/**`、`config/automake/**`、`pkg/**`，以及任何工具链、编译器、链接器、sysroot、预编译库。

正常授权的安装/更新可写厂商目录；工作空间 staging 可按流程生成。目录型工具链生成只用于自有可写目录，厂商目录使用已有 `.cmake`。

**其他禁止项**

- 不得把 `/` 复制或软链进工作空间，不得把宿主根当作可上传 rootfs。
- Skill 自身验证使用隔离临时目录；实际工程按用户指定路径开发，不把临时测试产物写入 Skill 仓库。
- 不得把密码、令牌、私钥写入 argv、源码或日志。
- 不得把 `project-run-tools`/`project-run-test` 当作本地调试器。
- 设备/网络/凭据缺失时如实报告 `BLOCKED`，**不得放宽校验或伪造产物**。

**破坏性操作（核对已有授权；未覆盖删除已有数据时再确认）**

| 命令 | 影响 |
| --- | --- |
| `rl-workspace init` | 完成参数/产品解析后、平台初始化前执行 clean，删除 `.realevo/{arch,linux,openeuler,package_list}` |
| `rl-workspace clean` | 删除上述目录（保留 `base`、`config.json`、`devicelist.json`、`depend_armory.json`） |
| `rl-build clean` / `uninstall` | 删构建/安装目录；`uninstall` 还从 rootfs 删文件 |
| `rl-package uninstall` | 从 rootfs 删包（非交互会静默取消） |
| `rl-tools modifycmake` / `modifygcc` | **替换系统 CMake 模块与 `gcc/g++/ld`**；用对应 `restore*` 还原 |

## 8. 凭据、权限与封装验收

- 需要系统权限时：本 Skill 的 `cli.py` 先试免密 `sudo -n`，否则用 `REALEVO_SUDO_PASSWORD` 预认证，密码只经 stdin。**不要**把密码写进命令行。
- 原生工具内部使用 sudo；必须有当前有效非交互权限，可能来自 NOPASSWD 或缓存认证。无权限时只停止相关阶段。`cli.py` 将写入命令整体经 sudo 执行，不依赖内部再次提示密码。
- 原生 `rl-device`、`rl-package set`、`rl-ecsm set` 的密码接口是 argv，不能直接用于秘密凭据。使用由用户/环境安全预置的配置并限制权限；没有安全配置渠道时停止该阶段。不得用默认 `root/root` 代替真实凭据。
- `.realevo/devicelist.json`、`~/.armory/rl-config.json` 与 ECSM 用户配置可能含明文密码，限制为所属用户可读写，不纳入版本控制或日志；原生 show/list 不保证所有输出均脱敏，避免回显秘密。

封装行为与验收边界：

- `check.result.installed` 检查标准流程必需入口，`usable` 检查版本查询；具体 SDK、编译器、ROS 2/ECS 依赖仍按阶段验证。
- `install` 只执行匹配已核验安装器 SHA-256 的 `--quiet` 分支。内置本机安装器摘要为 `7957f9e910cebba2e065698afb2d6316478d5f2d17a79380fcf165394d3b92f5`。未知安装器须先核验可信来源和无人值守行为，再提供 `--installer-sha256`；不得为了通过检查直接信任下载包自报的摘要。摘要仅约束 Install.sh，整个包仍须来自可信渠道。
- 安装成功要求日志无已知业务错误、必要命令可执行、查询版本与安装包 config/version.ini 一致；License 另行配置和验收。
- `install-sdk` 检查安装后的 `stream_config.json` 与其中 base/rootfs/tools 的存在性。离线模式还核对清单一致性；在线模式要求包名与 SDK 名一致，否则使用离线目录。这不证明组件内容版本、ABI、功能或确由本次安装生成，使用前仍需构建验证。
- `--timeout` 是单个下载/写入命令的总截止时间；sudo 认证、验收回读使用独立短截止时间，整个调用可能更长。日志落临时文件，仅返回错误摘要与尾部，需保证临时磁盘空间。
- 超时/中断时终止同组进程，并对 sudo 进程尝试特权清理；无法保证已脱离组、失去清理权限或远端的进程终止。失败可能已有部分系统变更，检查实际状态后决定是否重试，不自动重试安装。
- `--dry-run` 不安装/配置；本地包检查会临时解包并清理，远程包只预览地址。`--work-dir` 实际安装在该父目录下创建独立目录并保留，避免重用旧解包产物。
- 下载 URL 不接受内嵌凭据、查询参数或片段；有查询签名的包先由安全渠道下载为本地包。下载有总截止时间并检查非空及声明长度。

## 9. 已知缺陷（排障时勿误判为用法错误）

| 位置 | 现象 |
| --- | --- |
| `rl-build package` | 空实现，仅打印提示 → 打包用 `rl-package package` |
| `rl-build symbolcheck --path` | 使用未定义变量，无法只检测单个 ELF |
| `rl-colcon` | `VALID_COMMANDS` 含 `all` 但未实现；`list` 已实现却未列入校验数组 |
| `rl-project run/debug` | 包装函数被整段注释 → 命令集内无 run/debug 链路 |
| `rl-project update --platform` | EOF 下无限自旋（见 §2） |
| `rl-tools exportcmake` | 无 `--platform`，强制 `select`（见 §2） |
| `rl-device` | `add` 写 `host_name`，读取方用 `hostName`；`update --hostname` 不写入 → ECS 容器别名读不到 |
| `rl-workspace show` / `rl-package` | 读 `mini_kernel_version`，写入键是 `sylixos_min_kernel_version` → 该字段读不到 |
| `rl-ecs save` | FTP 通路使用未定义变量 → 必然失败 |
| `rl-ecsm` | `--active` 的 `.lower` 缺 `()` → `set/update --active` 不可用 |
| `rl-utils` | 部分错误分支 `error_print(..., file=...)` 与签名不符 → 抛 `TypeError` |
| `rl-project create --make-tool=ninja` | 非 meson 工程会被覆盖为 `make` |
| `sylixos-linux-tools` | Linux/OpenEuler 分支用未定义下标 → 多平台时可能只处理第一个 |

## 10. BLOCKED 判定

缺少当前阶段必要条件时，仅停止依赖该条件的阶段并报告 `BLOCKED`（说明缺什么）；继续独立的本地工作：

1. 当前操作需要授权，而 License 非 `VALID` 且无法配置。
2. 特权阶段无有效非交互 sudo 权限，且封装无法通过运行环境提供的密码预认证。cython 原生构建先检查当前 `sudo -n true`。
3. 设备阶段缺少真实设备、可达网络（FTP/SFTP/Telnet/SSH）或正确凭据。
4. 缺少必需的目标 rootfs 或工具链（Linux/OpenEuler 构建）。
5. 缺少 SylixOS Base 且无法从 `pkg/` 解压或下载。
6. 当前包下载或发布需要 Armory 凭据/组织而没有安全预置配置。

```bash
# 环境自检
sudo -n true && echo "sudo OK" || echo "sudo BLOCKED"
python3 "$CLI" check          # installed?
python3 "$CLI" license show   # VALID?
timeout --kill-after=5s 30 rl-device list </dev/null  # 仅登记状态，不代表网络/凭据就绪
```

## 11. 核验基线源码指纹

这些 SHA-256 用于判定文档中的实现细节是否适用，不能作为其他包的可信来源证明：

| 文件（bin/ 下） | SHA-256 |
| --- | --- |
| rl-tools | `0a0cb0f27d77d3f3030c0f12a23aaf42514ab04a47ce432dde8563a80eca030d` |
| rl-project | `0ff5db8333f1bf74b2ab14437a60fadf7c0ca850cf5f51c97aab7e3ff0c9508a` |
| rl-workspace | `0bba0a19038d4fe58b4b4d5161aadcc84f615646ba7a4476819449acbe61db4b` |
| rl-ecsm | `999fe4b2ceebb105802b1885f055049a5a1d4a03a1f11116460a2fc5754211f3` |

封装回归验证：在 Skill 目录执行 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'`，测试仅使用临时目录、本地子进程和模拟上游返回，不执行真实 sudo 安装/设备操作。
