import os
import json
import tarfile
import os.path
import os as os_module
import asyncio

# 初始化工作空间部分
# 获取产品系列列表
def get_product_series():
    # 获取 /opt/acoinfo/realevo-stream/pkg/product 目录下的子文件目录
    product_root_dir = "/opt/acoinfo/realevo-stream/pkg/product"
    product_dir_list = []
    for item in os.listdir(product_root_dir):
        if os.path.isdir(os.path.join(product_root_dir, item)):
            product_dir_list.append(item)
    # 循环 product_dir_list
    product_series = []
    for product_dir in product_dir_list:
        # 读取 product_dir 下的 stream_config.json 文件
        stream_config_path = os.path.join(product_root_dir, product_dir, "stream_config.json")
        with open(stream_config_path, "r") as f:
            stream_config = json.load(f)
            # 遍历 product_mapping 数组, 如果没有 product_mapping 数组, 则跳过
            if "product_mapping" not in stream_config:
                continue
                
            for product_mapping in stream_config["product_mapping"]:
                # product_mapping 对象的 product_series 值为产品系列
                product_series.append(product_mapping["product_series"])
    # 去重
    product_series = list(set(product_series))
    
    # 排序
    product_series.sort()

    return {
        "status": "success",
        "result": product_series
    }

# 运行命令, 逐行打印输出到控制台
async def run_command(command, cwd=None):

    print(f"\n当前工作目录: {cwd}")
    print(f"\n执行命令: {command}")
    
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    async def read_stream(stream, prefix):
        output = []
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode('utf-8', errors='replace').rstrip('\n')
            print(f"[{prefix}] {decoded}")
            output.append(decoded)
        return '\n'.join(output)

    stdout, stderr = await asyncio.gather(
        read_stream(process.stdout, 'STDOUT'),
        read_stream(process.stderr, 'STDERR')
    )

    await process.wait()

    print(f"\n命令执行完成，返回码: {process.returncode}")
    return process.returncode, stdout, stderr

# 通过产品系列初始化工作空间
async def init_sylixos_workspace_by_product_series(workspace_path, product_series):
    # 在 workspace_path 目录下运行 rl-workspace init --product={product_series} 命令
    # asyncio.create_task(run_command(f"rl-workspace init --product={product_series}", workspace_path))
    
    # return {
    #     "status": "pending",
    #     "message": "工作空间初始化中....."
    # }

    return_code, stdout, stderr = await run_command(f"rl-workspace init --product={product_series}", workspace_path)
    if return_code != 0:
        return {
            "status": "failed",
            "message": f"工作空间初始化失败：{stderr}"
        }
    else:
        return {
            "status": "success",
            "message": f"工作空间初始化成功",
            "result": True
        }



# 查看 Base 工程支持的 platforms
def get_supported_platforms_by_base_project(base_project_path):
    platforms = []

    # 判断 base_project_path 是文件目录还是 tar.gz 文件
    if os.path.isdir(base_project_path):
        base_project_path = os.path.join(base_project_path, "platforms.mk")
        # 按行读取 base_project_path 内容，支持编码回退
        content = None
        for encoding in ['utf-8', 'gbk', 'latin-1']:
            try:
                with open(base_project_path, "r", encoding=encoding) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue
        if content is not None:
            for line in content.splitlines():
                if not line or line.startswith('#'):
                    continue
                if ':=' in line:
                    platform_name = line.split(':=')[0].strip()
                    platforms.append(platform_name)
    elif base_project_path.endswith(".tar.gz"):
        for line in read_lines_from_tar_gz(base_project_path, "platforms.mk"):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('#'):
                continue
            if ':=' in line_stripped:
                platform_name = line_stripped.split(':=')[0].strip()
                platforms.append(platform_name)
    else:
        return {
            "status": "error",
            "message": f"Base 工程路径 {base_project_path} 不是文件目录也不是 tar.gz 文件",
        }
    
    platforms = list(set(platforms))
    platforms.sort()
    return {
        "status": "success",
        "result": platforms
    }

# 查看可用 Base 版本
def get_base_versions():
    # 读取 /opt/acoinfo/realevo-stream/pkg/base 目录下的 tar.gz 文件列表
    # 提取文件名，即去掉 .tar.gz 后缀
    base_root_dir = "/opt/acoinfo/realevo-stream/pkg/base"
    base_dir_list = []
    for item in os.listdir(base_root_dir):
        if item.endswith(".tar.gz"):
            base_dir_list.append(item.replace(".tar.gz", ""))
    # 去重
    base_dir_list = list(set(base_dir_list))
    # 排序
    base_dir_list.sort()
    return {
        "status": "success",
        "result": base_dir_list
    }

def read_lines_from_tar_gz(tar_gz_path, target_file_path):
    normalized_target = target_file_path.lstrip('./')
    with tarfile.open(tar_gz_path, 'r:gz') as tar:
        member = None
        try:
            member = tar.getmember(normalized_target)
        except KeyError:
            for m in tar.getmembers():
                if m.name.rstrip('/') == normalized_target or m.name.endswith(f"/{normalized_target}"):
                    member = m
                    break
        if member is None:
            raise FileNotFoundError(f"文件 {target_file_path} 不存在于压缩包中")
        with tar.extractfile(member) as f:
            for line in f:
                try:
                    decoded = line.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        decoded = line.decode('gbk')
                    except UnicodeDecodeError:
                        decoded = line.decode('latin-1', errors='replace')
                yield decoded.rstrip('\n')

# 查看 Base 版本支持的 platforms
def get_supported_platforms_by_base_version(base_version):
    platforms = []
    base_path_str = f"/opt/acoinfo/realevo-stream/pkg/base/{base_version}.tar.gz"
    for line in read_lines_from_tar_gz(base_path_str, "platforms.mk"):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith('#'):
            continue
        if ':=' in line_stripped:
            platform_name = line_stripped.split(':=')[0].strip()
            platforms.append(platform_name)
    platforms = list(set(platforms))
    platforms.sort()
    return {
        "status": "success",
        "result": platforms
    }

# 通过 Base 库中的 Base 版本初始化工作空间
async def init_sylixos_workspace_by_base_version(workspace_path, base_version, platforms):
    # rl-workspace init --version=<prepared_base> --platform=<platform_name> --createbase=true --build=true
    # 遍历 platforms 组合 platform 参数，以 : 分隔
    platform_str = ':'.join(platforms)
    command = f"rl-workspace init --version={base_version} --platform={platform_str} --createbase=true --build=true"
    # 执行命令
    rreturn_code, stdout, stderr = await run_command(command, workspace_path)
    if rreturn_code != 0:
        return {
            "status": "error",
            "message": f"rl-workspace init 命令执行失败: {stderr}"
        }
    else:
        return {
            "status": "success",
            "message": f"工作空间初始化成功",
            "result": True
        }



# 通过 Base 工程初始化工作空间
async def init_sylixos_workspace_by_base_project(workspace_path, base_project_path, platforms):
    # rl-workspace init --base=<base_path> --platform=<platform_name>
    # 遍历 platforms 组合 platform 参数，以 : 分隔
    platform_str = ':'.join(platforms)
    command = f"rl-workspace init --base={base_project_path} --platform={platform_str} "
    # 执行命令
    rreturn_code, stdout, stderr = await run_command(command, workspace_path)
    if rreturn_code != 0:
        return {
            "status": "error",
            "message": f"rl-workspace init 命令执行失败: {stderr}"
        }
    else:
        return {
            "status": "success",
            "message": f"工作空间初始化成功",
            "result": True
        }


# 查看目标目录下可用 toolchain 列表
def get_available_toolchains(toolchain_dir):
    
    bin_path = os.path.join(toolchain_dir, 'bin')
    
    if not os.path.isdir(bin_path):
        print(f"\n可用 toolchain 列表")
        return {
            "status": "failed",
            "message": f"toolchain 目录不存在: {bin_path}"
        }
    
    toolchains_set = set()
    
    try:
        files = os.listdir(bin_path)
    except OSError:
        print(f"\n可用 toolchain 列表")
        return {
            "status": "failed",
            "message": f"读取 toolchain 目录 {bin_path} 失败"
        }
    
    for file in files:
        base_name = os.path.splitext(file)[0]
        
        gcc_index = base_name.rfind('-gcc')
        gpp_index = base_name.rfind('-g++')
        ld_index = base_name.rfind('-ld')
        
        marker_index = max(gcc_index, gpp_index, ld_index)
        
        if marker_index > 0:
            prefix = base_name[:marker_index]
            toolchains_set.add(prefix)
    
    toolchains = sorted(list(toolchains_set))
    
    print(f"\n可用 toolchain 列表")
    for tc in toolchains:
        print(f"  - {tc}")
    
    return {
        "status": "success",
        "result": toolchains
    }

# 生成 toolchain cmake 配置文件
def generate_toolchain_cmake(toolchain_dir, toolchain_name, platform, cmake_path):

    # 寻找 toolchain_dir 目录下 toolchain_name 对应的 gcc、g++、ld 路径
    gcc_path = os.path.join(toolchain_dir, "bin", f"{toolchain_name}-gcc")
    gpp_path = os.path.join(toolchain_dir, "bin", f"{toolchain_name}-g++")
    ld_path = os.path.join(toolchain_dir, "bin", f"{toolchain_name}-ld")

    if not os.path.exists(gcc_path) or not os.path.exists(gpp_path) or not os.path.exists(ld_path):
        return {
            "status": "failed",
            "message": f"toolchain {toolchain_name} 不存在: {gcc_path}, {gpp_path}, {ld_path}"
        }
    
    # platform 小写
    platform_lower = platform.lower()

    if platform_lower == "arm64":
        platform = "aarch64"
    elif platform_lower == "x86_64":
        platform = "x86_64"
    
    temp = """
# 指定目标系统的系统类型 Linux、SylisOS等
set(CMAKE_SYSTEM_NAME Linux)

# 目标系统的 CPU 架构，如 x86_64、aarch64 等
set(CMAKE_SYSTEM_PROCESSOR {platform})

# C 编译器路径
set(CMAKE_C_COMPILER {gcc_path})

# C++ 编译器路径
set(CMAKE_CXX_COMPILER {gpp_path})

# LD 编译器路径
set(CMAKE_LD_COMPILER {ld_path})
"""
    # 替换占位符
    temp = temp.format(platform=platform, gcc_path=gcc_path, gpp_path=gpp_path, ld_path=ld_path)
    
    # 写入文件
    with open(cmake_path, 'w') as f:
        f.write(temp)
    
    return {
        "status": "success",
        "message": f"cmake 配置文件 {cmake_path} 生成成功"
    }
    

# 初始化 Linux 工作空间
async def init_linux_workspace(workspace_path, platform, toolchain_cmake_path, rootfs_path):
    # rl-workspace init --os=linux --linux_platform=<ARM64|X86> --linux_toolchain=<toolchain_path> --linux_rootfs=<rootfs_path>
    command = f"rl-workspace init --os=linux --linux_platform={platform} --linux_toolchain={toolchain_cmake_path} --linux_rootfs={rootfs_path} "
    # 执行命令
    rreturn_code, stdout, stderr = await run_command(command, workspace_path)
    if rreturn_code != 0:
        return {
            "status": "error",
            "message": f"rl-workspace init 命令执行失败: {stderr}"
        }
    else:
        return {
            "status": "success",
            "message": f"工作空间初始化成功",
            "result": True
        }


# 初始化欧拉工作空间
async def init_euler_workspace(workspace_path, platform, toolchain_cmake_path, rootfs_path):
    # rl-workspace init --os=openeuler --openeuler_platform=<ARM64|X86> --openeuler_toolchain=<toolchain_path> --openeuler_rootfs=<rootfs_path>
    command = f"rl-workspace init --os=openeuler --openeuler_platform={platform} --openeuler_toolchain={toolchain_cmake_path} --openeuler_rootfs={rootfs_path} "
    # 执行命令
    rreturn_code, stdout, stderr = await run_command(command, workspace_path)
    if rreturn_code != 0:
        return {
            "status": "error",
            "message": f"rl-workspace init 命令执行失败: {stderr}"
        }
    else:
        return {
            "status": "success",
            "message": f"工作空间初始化成功",
            "result": True
        }


# 查看工作空间是否存在
def is_workspace(workspace_path):
    # 如果 workspace_path/.realevo/config.json 存在，则认为工作空间存在
    if os.path.exists(os.path.join(workspace_path, ".realevo/config.json")):
        return {
            "status": "success",
            "result": True
        }
    else:
        return {
            "status": "success",
            "result": False
        }


# 工程管理部分
def get_project_types():
    # 获取 RealEvo-Stream 支持创建的工程类型
    result = [
        {
            "project_type": "Application",
            "description": "C++ 语言应用工程",
            "category": "Template"
        },
        {
            "project_type": "Library",
            "description": "C++ 语言库工程",
            "category": "Template"
        },
        {
            "project_type": "Kernel_Module",
            "description": "内核模块工程",
            "category": "Template"
        },
        {
            "project_type": "Python",
            "description": "Python 语言工程",
            "category": "Template"
        },
        {
            "project_type": "JavaScript",
            "description": "JavaScript 语言工程",
            "category": "Template"
        },
        {
            "project_type": "Cython",
            "description": "Cython(C + Python) 混合工程",
            "category": "Template"
        },
        {
            "project_type": "Source_CMake",
            "description": "CMake 源码工程",
            "category": "Source"
        },
        {
            "project_type": "Source_Automake",
            "description": "Automake 源码工程",
            "category": "Source"
        },
        {
            "project_type": "Source_RealEvo_IDE",
            "description": "RealEvo IDE 源码工程",
            "category": "Source"
        }
    ]
    return {
        "status": "success",
        "result": result
    }

def get_project_params(project_type):
    # 获取 RealEvo-Stream 支持创建的工程类型的参数

    project_name = "工程名。"
    debug_level = "调试等级。可选值：debug|release。默认值：release"
    build_tool = "构建工具。可选值：make|ninja。默认值：make"
    source_path = "源码路径。"

    result = None

    if project_type == "Application":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Library":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Kernel_Module":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool,
            "source_path": source_path
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Python":
        result = {    
            "project_name": project_name
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "JavaScript":
        result = {
            "project_name": project_name
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Cython":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Source_CMake":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool,
            "source_path": source_path
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Source_Automake":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool,
            "source_path": source_path
        }
        return {
            "status": "success",
            "result": result
        }
    elif project_type == "Source_RealEvo_IDE":
        result = {
            "project_name": project_name,
            "debug_level": debug_level,
            "build_tool": build_tool,
            "source_path": source_path
        }
        return {
            "status": "success",
            "result": result
        }
    else:
        return {
            "status": "failed",
            "message": "不支持的工程类型"
        }

async def create_project(workspace_path, project_type, **params):
    # 创建 RealEvo-Stream 工程
    if project_type == "Application":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        # 执行 rl-project create --name=<project_name> --type=cmake --template=app --make-tool=make 命令
        rturn_code, stdout, stderr = await run_command(f"rl-project create --name={project_name} --type=cmake --template=app --make-tool={build_tool}", workspace_path)
        if rturn_code != 0:
            return {
                "status": "failed",
                "message": f"创建应用工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建应用工程：{project_name}",
                "result": True
            }

    elif project_type == "Library":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        # rl-project create --name=<project_name> --type=cmake --template=lib --make-tool=make
        command = f"rl-project create --name={project_name} --type=cmake --template=lib --make-tool={build_tool}"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建库工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建库工程：{project_name}",
                "result": True
            }

    elif project_type == "Kernel_Module":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        # rl-project create --name=<project_name> --type=cmake --template=ko --make-tool=make
        command = f"rl-project create --name={project_name} --type=cmake --template=ko --make-tool={build_tool}"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建内核模块工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建内核模块工程：{project_name}",
                "result": True
            }
    elif project_type == "Python":
        project_name = params.get("project_name")
        # rl-project create --name=<project_name> --type=python --template=common
        command = f"rl-project create --name={project_name} --type=python --template=common"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建Python工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建Python工程：{project_name}",
                "result": True
            }

    elif project_type == "JavaScript":
        project_name = params.get("project_name")
        # rl-project create --name=<project_name> --type=javascript --template=common
        command = f"rl-project create --name={project_name} --type=javascript --template=common"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建JavaScript工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建JavaScript工程：{project_name}",
                "result": True
            }

    elif project_type == "Cython":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        # rl-project create --name=<project_name> --type=cython --template=common
        command = f"rl-project create --name={project_name} --type=cython --template=common"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建Cython工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建Cython工程：{project_name}",
                "result": True
            }

    elif project_type == "Source_CMake":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        source_path = params.get("source_path")
        # rl-project create --name=<project_name> --source=<project_source_path> [--branch=<git_branch>] --make-tool=make --quiet
        command = f"rl-project create --name={project_name} --source={source_path} --make-tool={build_tool} --quiet"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建CMake源码工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建CMake源码工程：{project_name}",
                "result": True
            }


    elif project_type == "Source_Automake":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        source_path = params.get("source_path")
        # rl-project create --name=<project_name> --source=<project_source_path> [--branch=<git_branch>] --make-tool=make
        command = f"rl-project create --name={project_name} --source={source_path} --make-tool={build_tool}"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建Automake源码工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建Automake源码工程：{project_name}",
                "result": True
            }
    elif project_type == "Source_RealEvo_IDE":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        source_path = params.get("source_path")
        # 创建工程伪实现
        command = f"rl-project create --name={project_name} --source={source_path} --make-tool={build_tool}"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建RealEvo IDE源码工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建RealEvo IDE源码工程：{project_name}",
                "result": True
            }
    elif project_type == "Source_RealEvo_IDE":
        project_name = params.get("project_name")
        debug_level = params.get("debug_level", "release")
        build_tool = params.get("build_tool", "make")
        source_path = params.get("source_path")
        # 创建工程伪实现
        command = f"rl-project create --name={project_name} --source={source_path} --make-tool={build_tool}"
        return_code, stdout, stderr = await run_command(command, workspace_path)
        if return_code != 0:
            return {
                "status": "failed",
                "message": f"创建RealEvo IDE源码工程失败：{stderr}"
            }
        else:
            return {
                "status": "success",
                "message": f"\n创建RealEvo IDE源码工程：{project_name}",
                "result": True
            }
    else:
        return {
            "status": "failed",
            "message": f"不支持的项目类型：{project_type}"
        }

# 获取项目列表
def get_project_list(workspace_path):
    # 工作空间下文件目录中包含 .rlproject 目录的为项目
    project_list = []
    for item in os_module.listdir(workspace_path):
        if os_module.path.isdir(os_module.path.join(workspace_path, item)) and os_module.path.exists(os_module.path.join(workspace_path, item, ".rlproject", ".rlconfig")):
            project_list.append(item)

    return {
        "status": "success",
        "result": project_list
    }

# 设备管理

def get_os_supported_platforms(os):
    # 获取操作系统支持的平台
    result = None
    if os == "Linux":
        result = ["ARM64", "X86"]
    elif os == "OpenEuler":
        result = ["ARM64", "X86"]
    elif os == "SylixOS":
        result = ["ARM_926H","ARM_926S","ARM_920T","ARM_A5",
                "ARM_A5_SOFT","ARM_A7","ARM_A7_SOFT","ARM_A8",
                "ARM_A8_SOFT","ARM_A9","ARM_A9_SOFT","ARM_A15",
                "ARM_A15_SOFT","ARM_V7A","ARM_V7A_SOFT","ARM64_A53",
                "ARM64_A55","ARM64_A57","ARM64_A72","ARM64_GENERIC",
                "MIPS32","MIPS32_SOFT","MIPS32_R2","MIPS32_R2_SOFT",
                "MIPS64_R2","MIPS64_R2_SOFT","MIPS64_LS3A",
                "MIPS64_LS3A_SOFT","x86_PENTIUM","x86_PENTIUM_SOFT",
                "X86_64","PPC_750","PPC_750_SOFT","PPC_464FP",
                "PPC_464FP_SOFT","PPC_E500V1","PPC_E500V1_SOFT",
                "PPC_E500V2","PPC_E500V2_SOFT","PPC_E500MC",
                "PPC_E500MC_SOFT","PPC_E5500","PPC_E5500_SOFT",
                "PPC_E6500","PPC_E6500_SOFT","SPARC_LEON3",
                "SPARC_LEON3_SOFT","SPARC_V8","SPARC_V8_SOFT",
                "RISCV_GC32","RISCV_GC32_SOFT","RISCV_GC64",
                "RISCV_GC64_SOFT","LOONGARCH64","LOONGARCH64_SOFT",
                "CSKY_CK807","CSKY_CK807_SOFT","CSKY_CK810",
                "CSKY_CK810_SOFT","CSKY_CK860","CSKY_CK860_SOFT",
                "SW6B","SW6B_SOFT"]
    if result is None:
        return {
            "status": "failed",
            "message": f"不支持的操作系统：{os}"
        }
    return {
        "status": "success",
        "result": result
    }
# 添加设备
def add_device(workspace_path, device_name, device_address, user_name, password, os, platform):
    
    device_config_path = f"{workspace_path}/.realevo/devicelist.json"
    
    config_dir = os_module.path.dirname(device_config_path)
    if not os_module.path.exists(config_dir):
        os_module.makedirs(config_dir, exist_ok=True)
    
    if os_module.path.exists(device_config_path) and os_module.path.getsize(device_config_path) > 0:
        with open(device_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {"devices": []}
    
    new_device = {
        "name": device_name,
        "ip": device_address,
        "platform": platform,
        "os": os,
        "telnet": 23,
        "ssh": 22,
        "ftp": 21,
        "gdb": 1234,
        "user": user_name,
        "password": password
    }
    
    config["devices"].append(new_device)
    
    try:
        with open(device_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"\n添加设备成功：{device_name}")
        return {
            "status": "success",
            "message": f"\n添加设备成功：{device_name}"
        }
    except Exception as e:
        print(f"\n添加设备失败：{e}")
        return {
            "status": "error",
            "message": f"\n添加设备失败：{e}"
        }

def get_device_list(workspace_path):
    device_config_path = f"{workspace_path}/.realevo/devicelist.json"
    if os_module.path.exists(device_config_path):
        try:
            with open(device_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            devices = config.get("devices", [])
            device_list = [device.get("name") for device in devices]
        except Exception as e:
            print(f"\n获取设备列表失败：{e}")
            return {
                "status": "error",
                "message": f"\n获取设备列表失败：{e}"
            }
    else:
        return {
            "status": "failed",
            "message": f"\n设备配置文件不存在：{device_config_path}"
        }
    return {
        "status": "success",
        "result": device_list
    }

def see_device_info(workspace_path, device_name):
    device_config_path = f"{workspace_path}/.realevo/devicelist.json"
    if os_module.path.exists(device_config_path):
        try:
            with open(device_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            devices = config.get("devices", [])
            device = next((d for d in devices if d.get("name") == device_name), None)
            if device:
                return {
                    "status": "success",
                    "result": device
                }
            else:
                return {
                    "status": "failed",
                    "message": f"\n未找到设备：{device_name}"
                }
        except Exception as e:
            print(f"\n获取设备信息失败：{e}")
            return {
                "status": "failed",
                "message": f"\n获取设备信息失败：{e}"
            }
    else:
        return {
            "status": "failed",
            "message": f"\n设备配置文件不存在：{device_config_path}"
        }

def modify_device_info(workspace_path, device_old_name, device_new_name, device_address, user_name, password, os, platform):
    device_config_path = f"{workspace_path}/.realevo/devicelist.json"
    
    if not os_module.path.exists(device_config_path):
        print(f"\n设备配置文件不存在：{device_config_path}")
        return {
            "status": "failed",
            "message": f"\n设备配置文件不存在：{device_config_path}"
        }
    
    try:
        with open(device_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        devices = config.get("devices", [])
        found = False
        
        for device in devices:
            if device.get("name") == device_old_name:
                if device_new_name:
                    device["name"] = device_new_name
                if device_address:
                    device["ip"] = device_address
                if user_name:
                    device["user"] = user_name
                if password:
                    device["password"] = password
                if os:
                    device["os"] = os
                if platform:
                    device["platform"] = platform
                found = True
                break
        
        if not found:
            print(f"\n未找到设备：{device_old_name}")
            return {
                "status": "failed",
                "message": f"\n未找到设备：{device_old_name}"
            }
        
        with open(device_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"\n修改设备信息成功：{device_old_name}")
        return {
            "status": "success",
            "result": True
        }
    except Exception as e:
        print(f"\n修改设备信息失败：{e}")
        return {
            "status": "error",
            "message": f"\n修改设备信息错误：{e}"
        }

# 工程构建
# 清理工程
async def build_clean(workspace_path, project_name, os):
    # os 转换为小写
    os = os.lower()

    # 执行 rl-build clean --project=<project_name> --os=<sylixos|linux|openeuler> 命令
    command = f"rl-build clean --project={project_name} --os={os}"

    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n清理工程成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }


# 配置工程
async def build_config(workspace_path, project_name, os):
    # os 转换为小写
    os = os.lower()
    # 执行 rl-build config --project=<project_name> --os=<sylixos|linux|openeuler> 命令
    command = f"rl-build config --project={project_name} --os={os}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n配置工程成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }

# 构建工程
async def build_build(workspace_path, project_name, os):
    # os 转换为小写
    os = os.lower()
    # 执行 rl-build build --project=<project_name> --os=<sylixos|linux|openeuler> 命令
    command = f"rl-build build --project={project_name} --os={os}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n构建工程成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }

# 安装工程
async def build_install(workspace_path, project_name, os):
    # os 转换为小写
    os = os.lower()
    # 执行 rl-build install --project=<project_name> --os=<sylixos|linux|openeuler> 命令
    command = f"rl-build install --project={project_name} --os={os}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n安装工程成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }

# 依次执行构建步骤
async def build_all(workspace_path, project_name, os):
    # os 转换为小写
    os = os.lower()
    # 执行 rl-build all --project=<project_name> --os=<sylixos|linux|openeuler> 命令
    command = f"rl-build all --project={project_name} --os={os}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n依次执行构建步骤成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }

# 卸载安装
async def build_uninstall(workspace_path, project_name, os):
    # os 转换为小写
    os = os.lower()
    # 执行 rl-build uninstall --project=<project_name> --os=<sylixos|linux|openeuler> 命令
    command = f"rl-build uninstall --project={project_name} --os={os}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n卸载安装成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }

# 部署
# 部署工程到设备
async def upload_project(workspace_path, project_name, device_name):
    # 执行 rl-upload project --device=<device_name> --project=<project_name> 命令
    command = f"rl-upload project --device={device_name} --project={project_name}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n部署工程到设备成功：{project_name}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }

# 部署工作空间到设备
async def upload_workspace(workspace_path, device_name):
    # 执行 rl-upload workspace --device=<device_name> 命令
    command = f"rl-upload workspace --device={device_name}"
    
    # 执行命令
    returncode, ouput, stderr = await run_command(command, workspace_path)
    if returncode == 0:
        return {
            "status": "success",
            "result": f"\n部署工作空间到设备成功：{workspace_path}"
        }
    else:
        return {
            "status": "failed",
            "message": f"\n错误信息：{stderr.strip()}"
        }