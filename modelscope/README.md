# ModelScope / PAI-DSW · MiniMax H3

在魔搭 ModelScope（阿里云 PAI-DSW）与 AMD GPU 实例上部署 MiniMax H3 的笔记本集合。

Kaggle / Colab 版本请见仓库根目录下的 `kaggle_notebooks/` 与 `notebooks/`，本目录只收录 ModelScope / AMD 相关版本。

## 文件一览

| 文件 | 定位 | 单元数 |
| --- | --- | --- |
| `minimax_h3_modelscope.ipynb` | 可 Run All 的一站式部署脚本：ModelScope SDK 单文件下载 → ComfyUI 0.45.3 + 节点包安装 → 显存判档 → 启动出片 | 18 |
| `AMD_MiniMax_H3_workflow_fixed.ipynb` | 魔搭 AMD 部署文章的配套实验记录（含环境、参数、踩坑、出片结果），供阅读与复现参考，**不是**可直接 Run All 的部署脚本 | 19 |
| `AMD_MiniMax_H3_workflow_cloudflare.ipynb` | 上一份 + Cloudflare 命名隧道固定域名访问，启动端口统一到 8180 | 21 |

## 两套权重口径，不要混用

| | `minimax_h3_modelscope.ipynb` | `AMD_MiniMax_H3_workflow_*.ipynb` |
| --- | --- | --- |
| 精度 | 全 BF16 / FP16 / FP32，AMD 原生兼容 | INT8 ConvRot 主模型 + NVFP4 AWQ 编码器 + Turbo LoRA，AMD 上靠软件模拟 |
| 体积 | ≈ 97.6 GB（含 51.5 GB 官方 BF16 编码器） | ≈ 50.9 GiB（5 个文件） |
| 适合 | MI300X 192GB 这类大显存、要原生精度与稳定 | 复现魔搭 AMD 投稿工作流、Turbo 加速出片 |

两份笔记本的模型文件名与目录结构不同，**不要交叉引用彼此的 `ComfyUI/models` 软链**。

## 快速开始

1. 在 ModelScope / PAI-DSW 实例中打开 `minimax_h3_modelscope.ipynb`，工作目录用持久 NAS（`/mnt/workspace`）。
2. 配置区按需设置 `PLAN`（`minimal` → `full` 渐进验证）、`GPU_VENDOR`（`amd` / `nvidia`）、`TEXT_ENCODER`、`COMFY_PORT`。只想搬模型就把 `INSTALL_COMFYUI` / `START_COMFYUI` 设为 `False`。
3. 逐单元运行；下载层只走 `modelscope.snapshot_download` 单文件通道，已存在的文件自动复用。
4. 启动后从 `JupyterLab` 的 `/proxy/<COMFY_PORT>/` 入口访问 ComfyUI；出片后再用 `tools/h3_check_generate.py`（本仓库其它目录）做节点与服务自检。

## 端口与公网访问

- `minimax_h3_modelscope.ipynb` 默认 `COMFY_PORT = 8188`、`START_TUNNEL = True`。
- `AMD_MiniMax_H3_workflow_cloudflare.ipynb` 用 `--port 8180` 启动，配合 Cloudflare **命名隧道 + 面板路由**的固定域名：
  - 二进制复用实例上已上传的 `/mnt/workspace/cloudflared`，启动单元只定位、不重新下载。
  - 凭据通过环境变量 `CF_TUNNEL_TOKEN` 或 `/mnt/workspace/.h3_tunnel_token` 提供，**切勿写进公开笔记本**。
  - `cloudflared` 参数顺序：`tunnel --no-autoupdate --protocol http2 run --token <TOKEN>`；云环境 UDP/QUIC 常被限，需显式 http2。
  - 面板回源端口必须与笔记本启动端口一致，否则域名返回 502。
  - 同一条隧道只在一台实例上运行；多实例同时在线会被负载均衡打到没有 ComfyUI 的机器，表现为间歇性 502。

## 已知坑

- 参考笔记本原始版本的 `source` 数组每个元素缺 `\n`，Jupyter 用 `''.join()` 拼接后代码会挤成一行、Python 直接语法错误。本目录的 `_fixed` / `_cloudflare` 版已逐行补回换行并升到 nbformat 4.5（带 cell id），`nbformat.validate` 通过。
- ModelScope SDK 下载完会读回整文件校验，tqdm 进度条的瞬时速度不等于有效吞吐（实测 45–76 MiB/s），评估下载性能要按总耗时算。
- AMD / ROCm 不要加 CUDA 专用的 `--enable-triton-backend`；`H3SLAAttention` 等 CUDA + Triton 节点在 AMD 上不注册属正常。
- ComfyUI `main.py` 单进程只用 GPU0，多卡合计显存不能当单卡显存参与判档。
- 通过 API 修改笔记本后，若 JupyterLab 里还开着同一个文件，autosave 可能把内容覆盖回去；写入前先关闭对应标签页。

## 环境口径

- ROCm / PyTorch+rocm，MI300X 192GB 验证；Python 3.12 + torch 2.12+
- ComfyUI v0.45.3 + ComfyUI-KJNodes / ComfyUI-MAINodes / PlagueKind-only-sparse
- `modelscope >= 1.26`（`snapshot_download` 单文件 `allow_patterns` + `local_dir`）
