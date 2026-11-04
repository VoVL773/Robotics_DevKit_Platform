#!/usr/bin/env bash
# 检测 Ubuntu 24.04 + ROS 2 Jazzy
echo "========== 环境检测 =========="
# 1. 检测 Ubuntu 版本
source /etc/os-release

if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "24.04" ]]; then
    echo "[通过] Ubuntu 版本：$PRETTY_NAME"
else
    echo "[失败] 当前系统不是 Ubuntu 24.04"
    echo "当前系统：$PRETTY_NAME"
fi

# 2. 检测 ROS 2 Jazzy 是否安装
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
    echo "[通过] 已安装 ROS 2 Jazzy"
else
    echo "[失败] 未找到 ROS 2 Jazzy 安装目录"
fi

# 3. 检测当前终端环境
if [[ "${ROS_DISTRO:-}" == "jazzy" ]]; then
    echo "[通过] 当前终端已配置 ROS 2 Jazzy"
else
    echo "[提示] 当前终端未配置 ROS 2 Jazzy"
    echo "可以执行:source /opt/ros/jazzy/setup.bash"
fi

# 4. 综合判断
echo
if [[ "$ID" == "ubuntu" &&
      "$VERSION_ID" == "24.04" &&
      -f /opt/ros/jazzy/setup.bash ]]; then
    echo "结果：系统满足 Ubuntu 24.04 + ROS 2 Jazzy可以使用RDP"
else
    echo "结果：系统环境不完全符合要求，请检查以上信息"
fi
