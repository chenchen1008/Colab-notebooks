#!/usr/bin/env python3
"""生成 MiniMax-H3-Image Colab 笔记本 v2（明确命名的新版本）。

按 Qwen-Image-2.1 部署中已验证的工程修复点重写：
  官方 PyPI / 官方 HuggingFace、ComfyUI 新依赖校验、精选量化权重、
  下载完整性校验、ComfyUI 端口就绪轮询、cloudflared 重试与自检、Named Tunnel 可选。
v2 追加：CUDA 硬门禁 / 过滤 torch 家族防 CPU wheel / 8188 隧道精确匹配 /
  Named Tunnel 公网自检 / 逐条修订清单。
本次更新：隧道改为「有 Secret 用私有域名，没有走 trycloudflare」自动二选一（对齐 Qwen 版）。
"""
import json

# 原文件名与 v2 文件名都写同一份内容：git 上「原来的版本」已被 v2 覆盖，
# v2 链接继续保留可用，避免旧链接 404。
OUT = [
    '/Users/apple/WorkBuddy/2026-11-15-20-56-30/MiniMax-H3-Image_Colab.ipynb',
    '/Users/apple/WorkBuddy/2026-11-15-20-29-14/notebooks/MiniMax-H3-Image_Colab.ipynb',
    '/Users/apple/WorkBuddy/2026-11-15-20-56-30/MiniMax-H3-Image_Colab_v2.ipynb',
    '/Users/apple/WorkBuddy/2026-11-15-20-29-14/notebooks/MiniMax-H3-Image_Colab_v2.ipynb',
]

nb = {
    'cells': [],
    'metadata': {
        'accelerator': 'GPU',
        'colab': {'gpuType': 'T4', 'name': '', 'version': ''},
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': '3.10'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}

def md(s):
    nb['cells'].append({'cell_type': 'markdown', 'metadata': {},
                        'source': [l + '\n' for l in s.strip('\n').split('\n')]})

def code(s):
    nb['cells'].append({'cell_type': 'code', 'execution_count': None, 'metadata': {},
                        'outputs': [], 'source': [l + '\n' for l in s.strip('\n').split('\n')]})

md(r'''
# MiniMax H3-Image · Google Colab（T4 16GB · v2 修订版）

**模型**：MiniMax H3-Image，33.1B 参数扩散 Transformer，6 步采样、无 CFG、不接受 negative prompt，
原生 4096×4096（16MP），最多 16 张参考图。ComfyUI **v0.45.0+** 已原生支持，
量化权重在 [`Comfy-Org/MiniMax-H3-Image`](https://huggingface.co/Comfy-Org/MiniMax-H3-Image)，
原始 BF16 在 `MiniMaxAI/MiniMax-H3-Image`。

## 显存现实（原笔记本最大的坑）
T4 16GB 只能用 **W4A8 量化 DiT ≈11.7 GB** + `qwen3.5-9B W4A8` 文本编码器 ≈6.8 GB（CPU offload）
+ VAE ≈1.1 GB，合计约 20 GB 下载。INT8 ConvRot DiT ≈19.5 GB、BF16 ≈37.5 GB 在 T4 上都跑不动。
**原生 4K / 16MP 在 16GB 显存必然 OOM**：先用 1024×1024 或 2048×2048 验证链路，4K 需要 24GB+ 显卡。

## 本版按已验证的踩坑经验修正
- pip 与模型一律走**官方源**（`pypi.org` / `huggingface.co`）；Colab 机器在境外，清华源 / hf-mirror 常未同步 2026 新包与新仓库。
- 全量安装官方 `requirements.txt`，并校验 `comfy-aimdo` / `comfy-kitchen` / `comfy.quant_ops.ck`——缺了 ComfyUI 直接崩。
- 权重**精选**下载：原逻辑用「文件名含 16」筛选，实际文件名没有 16，会退化成下载最大的 BF16（37 GB），
  并把 `text_encoders/` 里全部 46 GB 都拉下来。本版只下 T4 能用的组合，并校验文件大小防 0 字节 / 404。
- `HF_ENDPOINT` 原来被设成裸域名（少 `https://`），会让 `huggingface_hub` 拼错 URL；本版直接清掉，只用官方源。
- cloudflared 加 `--no-autoupdate`、域名抓取重试、DNS 未生效重试、`/` 与 `/system_stats` 自检；可选固定私有域名。
- 旧说明里的 `vyrekai/minimax-h3-image-comfyui-workflows` **GitHub 上不存在（404）**；改用 ComfyUI 内置模板。

## v2 逐条修复清单（对应审查时指出的问题）

| # | 原问题 | v2 处理 |
|---|---|---|
| 1 | 按「文件名含 16」挑权重，实际文件名没有 16，退化成下载 BF16 37 GB + `text_encoders/` 全部 46 GB | 运行时列 HF API 文件树，按 `w4a8` 优先精选 DiT + `qwen3.5-9B W4A8` 文本编码器 + VAE，约 20 GB |
| 2 | 清华 pip 源漏装 2026 新包，报 `cannot import name 'ck' from comfy.quant_ops` | 全量装官方 `pypi.org` 的 requirements，校验 `comfy_kitchen` / `comfy_aimdo` / `ck`，缺失自动补装 |
| 3 | `HF_ENDPOINT` 被设成裸域名（少 `https://`），镜像站常未同步新仓库 | 清掉 `HF_ENDPOINT`，只用 `huggingface.co` |
| 4 | 工作流仓库 `vyrekai/minimax-h3-image-comfyui-workflows` GitHub 404 | 改用 ComfyUI v0.45.0+ 内置模板 + `Export (API Format)` |
| 5 | 宣称 4K / 16MP 匹配 16G 显存，实测必然 OOM | 明确 T4 只跑 W4A8 组合，先 1024×1024 / 2048×2048，4K 需 24GB+ 显卡 |
| 6 | `local_dir_use_symlinks=False` 新版已弃用、下载不校验大小、0 字节当成功 | 用 `hf_hub_download(local_dir=...)`，比对 HF API 返回的 size，不完整删掉重下 |
| 7 | 启动只 `sleep(10)`、不轮询端口、重复运行会起多个实例 | 端口轮询 60×3s、日志覆盖写、检测到 8188 被占用时提示可能是另一个 Colab 会话 |
| 8 | cloudflared 缺 `--no-autoupdate`、域名只抓一次、不自检、DNS 未生效直接失败 | 40 次抓域名、`/` 与 `/system_stats` 各 3 次重试自检 |
| 9 | `TUNNEL_URL` 可能未定义导致下一格 `NameError`；`wait_completion` 不看 status、超时 300s 太短 | 安全取 `globals().get`、检查 `/prompt` 返回与 history status、超时 900s、自动保存输出图片 |
| 10 | Drive 备份 `cp -r` 整个 models、目标目录未创建、缺 import | 只拷本次 `WANTED` 清单、`os.makedirs`、独立 import |

**v2 追加（Qwen 侧实测经验）**
- 官方 `requirements.txt` 含无版本约束的 `torch / torchvision / torchsde`，从 PyPI 重装可能把 Colab 预装的 `torch+cu130` 换成 CPU wheel，导致 `AssertionError: Torch not compiled with CUDA enabled`。v2 过滤 torch 家族、装完用子进程实测 CUDA，并在环境检查与启动 ComfyUI 前加硬门禁。
- quick tunnel 按 `--url http://localhost:8188` 精确匹配，不会误复用 Qwen 笔记本 8010 那条隧道的域名。
- Named Tunnel 模式也会设置 `TUNNEL_URL` 并做公网自检，下一格健康检查走固定域名。

## 本次更新：公网隧道自动二选一（对齐 Qwen 版）

第 6 格不再需要手动设 `USE_NAMED_TUNNEL`，改为**以 Colab Secret 为准**：

| 情况 | 走哪条 | 打印 |
|---|---|---|
| Secret `CF_TUNNEL_TOKEN_MINIMAX` 或 `CF_TUNNEL_TOKEN` 存在、已授权、token 可解析且固定域名验证通过 | Named Tunnel | `https://comfy.gmhqyj.ccwu.cc`（固定域名） |
| 没配 Secret / 本笔记本未授权 / token 无效 / 固定域名验证失败 | quick tunnel | `trycloudflare.com` 临时域名 |

读 Secret 后先 base64 校验 `a/t/s` 字段防误配，起 Named Tunnel 前会清掉同 token 的旧连接，
随后 8×5s 轮询验证 `comfy.gmhqyj.ccwu.cc/system_stats`，失败自动回退 quick tunnel，不会卡死。

> ⚠️ **同一个 Named Tunnel token 只能被一个 Colab 会话连接。** 若 Qwen 笔记本也在跑并用同一个
> `CF_TUNNEL_TOKEN`，后跑的笔记本会接管固定域名、前一个会话的公网域名会断。推荐给 MiniMax
> 单独建一条 Named Tunnel + 独立域名，把 Secret 命名为 `CF_TUNNEL_TOKEN_MINIMAX` 并修改
> `PRIVATE_HOST`；或把 `ALLOW_SHARED_TOKEN` 设为 `False`，MiniMax 检测到共享 token 时直接走临时域名。

> 权重附带 MiniMax-H3-Image Community License，对部署地区与商用有限制，请自行确认。

## 内容
1. 环境 / GPU / 磁盘检查
2. 官方源安装 ComfyUI + 依赖校验 + cloudflared
3. 官方 HF 仓库连通性与文件清单
4. 按 16GB 显存精选下载权重
5. （可选）备份权重到 Google Drive
6. 启动 ComfyUI 8188 + 公网隧道
7. API 调用示例与节点自检
''')

code(r'''
import sys, os, subprocess

try:
    import torch
    print('Python:', sys.version.split()[0])
    print('torch:', torch.__version__, '| cuda:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('GPU:', torch.cuda.get_device_name(0))
        print('VRAM: %.1f GB' % (torch.cuda.get_device_properties(0).total_memory / 1024**3))
except Exception as e:
    print('torch 检查失败:', repr(e))

for cmd in (['nvidia-smi'], ['df', '-h', '/content']):
    try:
        print('\n$ ' + ' '.join(cmd))
        print(subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout[-1200:])
    except Exception as e:
        print('执行失败:', repr(e))

# 硬门禁：CPU 运行时不要继续往下跑，ComfyUI 会在 comfy/model_management.py 崩
import torch as _t
if _t.version.cuda is None or not _t.cuda.is_available():
    raise RuntimeError('当前 torch=%s 无 CUDA 支持（CPU 运行时，或 torch 被 pip 换成 CPU 版）。'
                       '先 Runtime → Change runtime type 选 T4 GPU 并重新连接；'
                       '若已选 GPU 仍报错，运行 notebooks/fix_cuda_torch_cell.py' % _t.__version__)
print('✅ CUDA 检查通过:', _t.__version__, '|', _t.cuda.get_device_name(0))

print('\n提示：先选 Runtime -> Change runtime type -> T4 GPU；本版需下载约 20 GB 权重，确认 /content 空间充足。')
''')

code(r'''
import os, sys, subprocess

PYPI = 'https://pypi.org/simple'          # 官方源：2026 新包最全，国内镜像常漏 comfy-kitchen
COMFY = '/content/ComfyUI'
CF = '/usr/local/bin/cloudflared'

def pip_install(*args):
    cmd = [sys.executable, '-m', 'pip', 'install', '-q', '-i', PYPI] + list(args)
    print('$', ' '.join(cmd))
    subprocess.run(cmd, check=True)

pip_install('huggingface_hub', 'requests', 'tqdm')

if not os.path.exists(COMFY):
    subprocess.run(['git', 'clone', '-q',
                    'https://github.com/comfyanonymous/ComfyUI.git', COMFY], check=True)
else:
    subprocess.run(['git', '-C', COMFY, 'pull', '-q', '--ff-only'], check=False)
head = subprocess.run(['git', '-C', COMFY, 'rev-parse', '--short', 'HEAD'],
                      capture_output=True, text=True).stdout.strip()
print('ComfyUI HEAD:', head, '（需 v0.45.0+ 才原生支持 MiniMax H3-Image）')

# 全量安装官方 requirements（不要只装几个包，也不要改用清华源）
# 但 torch / torchvision / torchsde 必须剔除：官方 requirements 里它们无版本约束，
# 从 PyPI 重装可能把 Colab 预装的 torch+cu130 换成 CPU wheel，
# 触发 AssertionError: Torch not compiled with CUDA enabled（Qwen 版实测踩过）
_src = open(COMFY + '/requirements.txt', encoding='utf-8').read().splitlines()
_keep = [l for l in _src if l.strip().lower().split('==')[0].split('>=')[0].split('<')[0]
         not in ('torch', 'torchvision', 'torchaudio', 'torchsde')]
open('/content/requirements_notorch.txt', 'w', encoding='utf-8').write('\n'.join(_keep))
print('已过滤 torch 家族 %d 行，保留 %d 行依赖' % (len(_src) - len(_keep), len(_keep)))
pip_install('-r', '/content/requirements_notorch.txt')

# 子进程实测 torch（当前 kernel 可能缓存旧模块，子进程才反映磁盘上的真实版本）
chk_t = subprocess.run([sys.executable, '-c',
    'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'],
    capture_output=True, text=True)
print('torch 实测:', (chk_t.stdout or chk_t.stderr).strip())
if 'True' not in chk_t.stdout:
    raise RuntimeError('torch 无 CUDA 支持：先切 T4 GPU，或运行 notebooks/fix_cuda_torch_cell.py')

# 依赖校验：缺 ck 会报 ImportError: cannot import name 'ck' from comfy.quant_ops
CHECK = [sys.executable, '-c',
         'import comfy_kitchen, comfy_aimdo; from comfy.quant_ops import ck; print("依赖 OK")']
chk = subprocess.run(CHECK, cwd=COMFY, capture_output=True, text=True)
if chk.returncode != 0:
    print('依赖缺失，补装官方源最新版 ...')
    pip_install('comfy-kitchen', 'comfy-aimdo')
    chk = subprocess.run(CHECK, cwd=COMFY, capture_output=True, text=True)
print('依赖校验:', (chk.stdout or chk.stderr).strip()[-400:])
if chk.returncode != 0:
    raise RuntimeError('ComfyUI 依赖不完整，先别启动 8188')

if not os.path.exists(CF):
    subprocess.run(['wget', '-q',
        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',
        '-O', CF], check=True)
    os.chmod(CF, 0o755)
print('cloudflared 就绪')
''')

code(r'''
import os, time, requests

REPO = 'Comfy-Org/MiniMax-H3-Image'       # ComfyUI 官方量化打包
HF_BASE = 'https://huggingface.co'        # Colab 在境外：官方源最全最快
os.environ.pop('HF_ENDPOINT', None)       # 清掉旧笔记本残留的镜像环境变量（裸域名会拼错 URL）
HEADERS = {'User-Agent': 'colab-minimax-h3/1.0'}

def probe(url, timeout=30):
    t0 = time.time()
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    return r, time.time() - t0

r, dt = probe(HF_BASE + '/api/models/' + REPO)
print('仓库探测: HTTP %s | %.2fs' % (r.status_code, dt))
r.raise_for_status()

def tree(folder):
    url = HF_BASE + '/api/models/' + REPO + '/tree/main/' + folder
    rr, _ = probe(url)
    rr.raise_for_status()
    files = [e for e in rr.json() if e.get('type') == 'file']
    print('\n%s/ （%d 个文件）' % (folder, len(files)))
    for e in files:
        print('  %-62s %8.2f GB' % (e['path'], e.get('size', 0) / 1e9))
    return files

DIFF = tree('diffusion_models')
TEXT = tree('text_encoders')
VAE = tree('vae')
print('\n>>> 官方源可用；下一步只挑 T4 16GB 能用的组合，不会下载整个仓库')
''')

code(r'''
import os, time
from huggingface_hub import hf_hub_download

BASE_DIR = '/content/ComfyUI/models'
NEED_EDITING = False   # True 才额外下载图生图/编辑用的大视觉编码器；T4 装不下，默认关

def pick(files, keywords, exclude=()):
    for kw in keywords:
        cand = [e for e in files
                if kw in e['path'].lower()
                and not any(x in e['path'].lower() for x in exclude)]
        if cand:
            return min(cand, key=lambda e: e.get('size', 0))
    return None

# 关键修正：旧逻辑找「文件名含 16」，实际文件名没有 16，会退化成下载最大的 BF16 37GB
WANTED = []
d = pick(DIFF, ['w4a8', 'int8_convrot'], exclude=('bf16',))
if d is None:
    d = min(DIFF, key=lambda e: e.get('size', 0))
if 'w4a8' not in d['path'].lower():
    print('⚠️ 未找到 W4A8 量化，选中 %s (%.2f GB)，T4 16GB 可能 OOM' % (d['path'], d.get('size', 0) / 1e9))
WANTED.append(d)

t = pick(TEXT, ['qwen3.5_9b_w4a8', 'qwen3.5'], exclude=('qwen3vl',))
if t is None:
    t = min(TEXT, key=lambda e: e.get('size', 0))
WANTED.append(t)

if NEED_EDITING:
    v = pick(TEXT, ['nvfp4'])
    if v:
        WANTED.append(v)
v = pick(VAE, ['vae_fp16', 'vae'])
if v:
    WANTED.append(v)

print('\n=== 本次下载清单 ===')
for e in WANTED:
    print('  %-70s %.2f GB' % (e['path'], e.get('size', 0) / 1e9))

def download(entry):
    remote = entry['path']                 # HF API 返回的 path 已含子目录，不能省
    dst = os.path.join(BASE_DIR, remote)
    expect = entry.get('size', 0)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) > 1e6 and (not expect or abs(os.path.getsize(dst) - expect) < expect * 0.02):
        print('✅ 已完整，跳过:', remote)
        return os.path.getsize(dst)
    if os.path.exists(dst):
        print('⚠️ 残留不完整，删除重下:', remote, os.path.getsize(dst))
        os.remove(dst)
    print('下载:', remote)
    t0 = time.time()
    path = hf_hub_download(repo_id=REPO, filename=remote, local_dir=BASE_DIR)
    got = os.path.getsize(path)
    ok = got > 1e6 and (not expect or abs(got - expect) < expect * 0.02)
    print(('✅' if ok else '❌'), remote, '%.2f GB | %.1f MB/s' % (
        got / 1e9, got / 1e6 / max(time.time() - t0, 1e-6)))
    if not ok:
        raise RuntimeError('下载不完整: ' + remote + '，检查网络与仓库路径')
    return got

total = sum(download(e) for e in WANTED)
print('\n>>> 下载完成，共 %.2f GB（T4 可用组合）' % (total / 1e9))
''')

code(r'''
# 可选：只把本次下载的权重拷到 Drive（约 20 GB，耗时且占 Drive 配额）
# 需先运行第 4 个单元格（依赖 WANTED 清单）
import os, shutil
from google.colab import drive

drive.mount('/content/drive')
dst = '/content/drive/MyDrive/MiniMax-H3-Image'
os.makedirs(dst, exist_ok=True)
for e in WANTED:
    src = os.path.join('/content/ComfyUI/models', e['path'])
    if os.path.exists(src):
        out = os.path.join(dst, os.path.basename(e['path']))
        shutil.copy2(src, out)
        print('已拷贝:', out, '%.2f GB' % (os.path.getsize(out) / 1e9))
print('完成:', dst)
''')

code(r'''
import os, sys, re, time, socket, subprocess, urllib.request, json, base64

COMFY, PORT = '/content/ComfyUI', 8188
LOG, TLOG, CF = '/content/comfyui.log', '/content/cloudflared.log', '/usr/local/bin/cloudflared'

# ---- 公网隧道自动二选一：有 Secret 用私有域名，没有走 trycloudflare ----
PRIVATE_HOST = 'https://comfy.gmhqyj.ccwu.cc'   # Public Hostname -> localhost:8188
SECRET_CANDIDATES = ['CF_TUNNEL_TOKEN_MINIMAX', 'CF_TUNNEL_TOKEN']  # 独立 Secret 优先
ALLOW_SHARED_TOKEN = True   # False：检测到共享的 CF_TUNNEL_TOKEN 时不抢 Qwen 会话，直接走临时域名

import torch as _t6
if _t6.version.cuda is None or not _t6.cuda.is_available():
    raise RuntimeError('torch 无 CUDA：先切 T4 GPU / 运行 fix_cuda_torch_cell.py，否则 ComfyUI 必崩')

def port_open(p):
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect(('127.0.0.1', p)); return True
    except Exception:
        return False
    finally:
        s.close()

def selfcheck(base):
    """公网地址自检：新 quick tunnel 域名 DNS 传播需要 30-60 秒，失败重试 3 次"""
    for path in ['/', '/system_stats']:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(base + path, timeout=45) as r:
                    print('  %-14s HTTP %s | %d bytes' % (path, r.status, len(r.read())))
                break
            except Exception as e:
                if attempt == 2:
                    print('  %-14s 自检失败: %r（DNS 未生效，等 30-60 秒重跑本 Cell）' % (path, e))
                else:
                    time.sleep(10)

if port_open(PORT):
    print('⚠️ 8188 已被占用：可能是另一个 Colab 会话的 ComfyUI。本 Cell 不重复启动，隧道指向现有服务。')
    print('   若那是 Qwen-Image 笔记本，权重与工作流不兼容，请先停掉它再重跑。')
else:
    log = open(LOG, 'w')
    p = subprocess.Popen([sys.executable, 'main.py', '--listen', '0.0.0.0', '--port', str(PORT)],
                         cwd=COMFY, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    print('ComfyUI PID:', p.pid)
    for _ in range(60):
        time.sleep(3)
        if port_open(PORT):
            break
    print('8188 监听:', port_open(PORT))
    if not port_open(PORT):
        print('❌ 启动失败，日志末尾:\n', open(LOG, errors='replace').read()[-2000:])
        raise RuntimeError('ComfyUI 未就绪，检查 /content/comfyui.log')

try:
    info = json.load(urllib.request.urlopen('http://127.0.0.1:%d/object_info' % PORT, timeout=60))
    hits = [k for k in info if 'minimax' in k.lower() or 'h3' in k.lower()]
    print('MiniMax/H3 相关节点:', hits[:20] or '（未发现，确认 ComfyUI >= 0.45.0）')
except Exception as e:
    print('object_info 读取失败:', repr(e))

# ---------------- 公网隧道：有 Secret 用私有域名，没有走 trycloudflare ----------------
TOKEN, SECRET_USED = None, None
try:
    from google.colab import userdata
    for _name in SECRET_CANDIDATES:
        try:
            _val = userdata.get(_name)
        except Exception:
            _val = None
        if _val:
            TOKEN, SECRET_USED = _val, _name
            break
except Exception as e:
    print('读取 Colab Secret 失败（%s）→ 走 quick tunnel' % type(e).__name__)

if TOKEN and SECRET_USED == 'CF_TUNNEL_TOKEN' and not ALLOW_SHARED_TOKEN:
    print('检测到共享 Secret CF_TUNNEL_TOKEN，ALLOW_SHARED_TOKEN=False → 不抢 Qwen 会话，走 quick tunnel')
    TOKEN = None
if not TOKEN:
    print('未配置可用的隧道 Secret %s → 走 quick tunnel' % SECRET_CANDIDATES)
else:
    try:
        meta = json.loads(base64.b64decode(TOKEN))
        assert meta.get('a') and meta.get('t') and meta.get('s'), 'token 缺字段'
        print('检测到 Secret %s | Tunnel ID: %s' % (SECRET_USED, meta['t']))
    except Exception as e:
        print('Secret 不是有效的隧道 token（%r）→ 走 quick tunnel' % e)
        TOKEN = None

def stop_named():
    subprocess.run("ps -eo pid,args | grep '[c]loudflared tunnel.*run --token' "
                   "| awk '{print $1}' | xargs -r kill", shell=True)

def private_tunnel():
    """有 Secret：接管 Named Tunnel，并验证固定域名真的可用"""
    stop_named()   # 同一 token 只能一个 Colab 会话连接，先清掉旧连接
    time.sleep(1)
    nlog = open('/content/cloudflared_named.log', 'w')
    p = subprocess.Popen([CF, 'tunnel', '--no-autoupdate', 'run', '--token', TOKEN],
                         stdout=nlog, stderr=subprocess.STDOUT, start_new_session=True)
    print('Named Tunnel PID:', p.pid, '| 等待云端下发 ingress / DNS ...')
    for attempt in range(8):
        time.sleep(5)
        try:
            with urllib.request.urlopen(PRIVATE_HOST + '/system_stats', timeout=20) as r:
                body = r.read()
            if b'comfyui_version' in body or b'devices' in body:
                print('✅ 私有域名验证通过:', PRIVATE_HOST + '/system_stats')
                return True
        except Exception as e:
            if attempt == 7:
                print('私有域名验证失败: %r' % e)
    print('⚠️ 检查 Zero Trust Public Hostname -> localhost:%d 与本地 ComfyUI；回退 quick tunnel' % PORT)
    return False

def quick_tunnel():
    """无 Secret 或固定域名不可用：开 quick tunnel，拿 trycloudflare.com 临时域名"""
    # 精确清理指向 8188 的旧隧道：绝不复用 Qwen 笔记本 8010 那条的域名
    subprocess.run("ps -eo pid,args | grep '[c]loudflared.*--url http://localhost:%d' "
                   "| awk '{print $1}' | xargs -r kill" % PORT, shell=True)
    time.sleep(1)
    tlog = open(TLOG, 'w')
    subprocess.Popen([CF, 'tunnel', '--no-autoupdate', '--url', 'http://localhost:%d' % PORT],
                     stdout=tlog, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(40):
        time.sleep(2)
        m = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',
                       open(TLOG, errors='replace').read())
        if m:
            return m[0]
    print('未取到临时域名，日志末尾:', open(TLOG, errors='replace').read()[-800:])
    return None

PRIVATE_OK = bool(TOKEN) and private_tunnel()
if PRIVATE_OK:
    TUNNEL_URL = PRIVATE_HOST
    print('>>> 私有域名模式（Secret %s 已启用）' % SECRET_USED)
    print('    ComfyUI Web UI: %s  |  原生 API: %s/system_stats' % (PRIVATE_HOST, PRIVATE_HOST))
else:
    if TOKEN:
        stop_named()   # 私有域名验证失败，停掉 named 再走临时域名
    TUNNEL_URL = quick_tunnel()
    print('>>> quick tunnel 模式（临时域名，每次重启会变）')

print('>>> ComfyUI 公网地址:', TUNNEL_URL or '未取到，等 30-60 秒重跑本 Cell')
if TUNNEL_URL:
    selfcheck(TUNNEL_URL)
''')

code(r'''
import json, os, time, requests

BASE_URL = globals().get('TUNNEL_URL') or 'http://127.0.0.1:8188'
print('使用地址:', BASE_URL)

try:
    st = requests.get(BASE_URL + '/system_stats', timeout=30).json()
    print('ComfyUI:', st['system']['comfyui_version'], '|', st['devices'][0]['name'])
    info = requests.get(BASE_URL + '/object_info', timeout=90).json()
    hits = [k for k in info if 'minimax' in k.lower() or 'h3' in k.lower()]
    print('MiniMax/H3 相关节点:', hits[:20] or '（无 -> 确认 ComfyUI >= 0.45.0）')
except Exception as e:
    print('健康检查失败:', repr(e))

def queue_prompt(workflow):
    r = requests.post(BASE_URL + '/prompt', json={'prompt': workflow}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError('/prompt 被拒绝: HTTP %s %s' % (r.status_code, r.text[:800]))
    return r.json()['prompt_id']

def wait_completion(pid, timeout=900):
    end = time.time() + timeout
    while time.time() < end:
        h = requests.get(BASE_URL + '/history/' + pid, timeout=20).json()
        if pid in h:
            item = h[pid]
            status = item.get('status', {})
            if status.get('completed') or status.get('status_str') == 'success' or item.get('outputs'):
                return item
            if status.get('status_str') == 'error':
                raise RuntimeError('ComfyUI 执行失败: ' + json.dumps(status.get('messages', []))[:1000])
        time.sleep(3)
    raise TimeoutError('生成超时；4K/16MP 在 T4 上会 OOM 或极慢，先用 1024x1024 验证')

wf_path = '/content/workflow_api.json'
if os.path.exists(wf_path):
    workflow = json.load(open(wf_path))
    # 按你的工作流节点 ID 改提示词，例如：workflow['6']['inputs']['text'] = '...'
    pid = queue_prompt(workflow)
    print('prompt_id:', pid)
    hist = wait_completion(pid)
    for node_id, out in hist.get('outputs', {}).items():
        for img in out.get('images', []):
            data = requests.get(BASE_URL + '/view', params={
                'filename': img['filename'], 'subfolder': img.get('subfolder', ''),
                'type': img.get('type', 'output')}, timeout=120).content
            fn = '/content/' + img['filename']
            open(fn, 'wb').write(data)
            print('已保存:', fn, len(data), 'bytes')
else:
    print('未找到 /content/workflow_api.json')
    print('ComfyUI v0.45.0+ 内置模板：Web UI -> Templates -> MiniMax H3 Image，选低显存/量化版，')
    print('再用 Workflow -> Export (API Format) 导出为 workflow_api.json 上传到 /content。')
    print('旧说明里的 https://github.com/vyrekai/minimax-h3-image-comfyui-workflows 并不存在（GitHub 404）。')
''')

md(r'''
## 使用说明与 FAQ

1. **先选 T4 GPU**（Runtime → Change runtime type → T4 GPU），再按顺序运行全部单元格。
2. 依赖与权重全部走**官方源**：`pypi.org/simple`、`huggingface.co`。Colab 机器在境外，
   清华源 / hf-mirror 常未同步 2026 新包（`comfy-kitchen`、`comfy-aimdo`）与新仓库，不要用。
3. 第 6 个单元格**自动二选一**：Colab Secret `CF_TUNNEL_TOKEN_MINIMAX` 或 `CF_TUNNEL_TOKEN`
   存在、已授权、token 有效且 `comfy.gmhqyj.ccwu.cc/system_stats` 验证通过 → 打印固定域名；
   否则打印 `trycloudflare.com` 临时域名（每次重启会变）。不需要再手动改 `USE_NAMED_TUNNEL`。
   Secret 是**按笔记本授权**的，用 GitHub 链接打开新笔记本要在左侧 Secrets 面板重新开启访问权限。
   ⚠️ **同一个 Named Tunnel token 只能一个 Colab 会话连接**：若 Qwen 笔记本也在用同一个
   `CF_TUNNEL_TOKEN`，后跑的会接管固定域名、前一个会话公网会断。两个会话并存时给 MiniMax
   单独建隧道 + 独立 Secret 名，或把 `ALLOW_SHARED_TOKEN` 设为 `False`。
4. **工作流**：ComfyUI v0.45.0+ 自带 MiniMax H3-Image 模板，不要去找
   `vyrekai/minimax-h3-image-comfyui-workflows`（该仓库 GitHub 返回 404）。
   模型是 6 步采样、无 CFG、不支持 negative prompt；提示词建议用详细的英文整段描述。
5. **显存**：T4 16GB 只跑 W4A8 组合，分辨率先用 1024×1024 / 2048×2048；
   原生 4096×4096（16MP）会 OOM，需要 24GB+ 显卡。
6. **公网域名 502 / 1033**：隧道活着但 8188 没监听，先重跑第 6 格；
   用 `curl http://127.0.0.1:8188/system_stats` 确认后端。
7. **新域名自检报 `gaierror(-2, Name or service not known)`**：quick tunnel 域名刚生成时 DNS 未传播，
   等 30–60 秒重跑即可，第 6 格已内置 3 次重试。
8. **下载到 0 字节 / 很小文件**：第 4 格会比对 HF API 返回的大小并删掉重下；
   若仍失败，确认 `/content` 磁盘空间与仓库路径（远端路径必须带 `diffusion_models/` 等子目录）。
9. **本机打不开固定域名**：部分网络会在 TLS 握手阶段阻断 `*.gmhqyj.ccwu.cc`，
   用临时 `trycloudflare.com` 域名或换网络；两个域名都无鉴权，建议加 Cloudflare Access。
10. **保存权重**：会话结束后 `/content` 会清空，需要长期保留就运行第 5 格（约 20 GB）。
11. **ComfyUI 报 `Torch not compiled with CUDA enabled`**：说明当前会话是 CPU 运行时，或 torch 被 pip 换成 CPU wheel，
    不是缺 `comfy-aimdo` / `comfy-kitchen`（日志里 `eager backend available` 反而说明它们已装好）。
    先 `Runtime → Change runtime type → T4 GPU` 并重连 VM；若已有 GPU 仍报错，运行仓库里的
    `notebooks/fix_cuda_torch_cell.py`。v2 已在环境检查、依赖安装、启动 ComfyUI 三处加 CUDA 硬门禁，
    不会再白跑 20 GB 下载。
12. **隧道域名串到 8010**：只按 `--url http://localhost:8188` 精确匹配清理/新建 quick tunnel；
    无论走私有域名还是临时域名，本格都会设置 `TUNNEL_URL` 并做 `/`、`/system_stats` 三次重试自检，
    下一格健康检查可直接用公网地址。
''')

for path in OUT:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print('写入', path, '|', len(nb['cells']), '个 Cell')
