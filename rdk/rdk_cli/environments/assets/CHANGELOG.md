# 开发环境版本记录

## 1.0.0 — 2026-11-05

- ROS 2 Humble / Ubuntu 22.04 / Python 3.10 与 Jazzy / Ubuntu 24.04 / Python 3.12。
- CPU 配置及 NVIDIA GPU 配置；GPU 基线 CUDA 12.6.3、驱动至少 560.35.05。
- CLI 与测试依赖精确锁定；可选训练基线 torch 2.6.0 CPU / cu126。
- 基础镜像 digest、APT 完整事务版本、ROS 公钥 SHA256、CLI 源码 SHA256 写入环境锁。
- 构建后保存 dpkg/Python 清单和镜像 ID；更新锁需要显式 --update-lock，并记录历史。
- Isaac/Gazebo 不包含在基线中；GPU 配置需要目标硬件上的 env verify 验证。
