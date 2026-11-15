# -*- coding: utf-8 -*-
"""Colab 单格修复：Qwen 版 ComfyUI 启动报
    AssertionError: Torch not compiled with CUDA enabled
    (comfy/model_management.py -> torch.cuda.current_device())

用法：在出问题的 Colab 笔记本里新建一个 Cell，整段粘贴运行；或：
    import urllib.request
    src = urllib.request.urlopen(
        'https://raw.githubusercontent.com/chenchen1008/Colab-notebooks/main/notebooks/fix_cuda_torch_cell.py',
        timeout=30).read().decode('utf-8')
    exec(compile(src, 'fix_cuda_torch_cell.py', 'exec'))

本文件只用 subprocess 调 pip，不依赖 IPython 的 ! 魔法，可独立 exec。
"""
import sys, re, subprocess
from types import SimpleNamespace

PY = sys.executable
PROBE = [PY, '-c',
         'import torch; print(torch.__version__); '
         'print(torch.version.cuda); print(torch.cuda.is_available())']


def run(cmd, timeout=900):
    print('$', ' '.join(cmd), flush=True)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return SimpleNamespace(returncode=-1, stdout='', stderr=repr(e))


def torch_state():
    r = run(PROBE, 180)
    lines = (r.stdout or '').strip().splitlines()
    ver = lines[0].strip() if len(lines) > 0 else '?'
    tag = lines[1].strip() if len(lines) > 1 else 'None'
    ok = lines[2].strip() if len(lines) > 2 else 'False'
    return ver, tag, ok, (r.stderr or '').strip()[:300]


print('=== [1/4] 诊断 ===', flush=True)
smi = run(['bash', '-lc',
           'nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader'], 30)
gpu = smi.stdout.strip()
print('nvidia-smi:', gpu or ('❌ 不可用 ' + (smi.stderr.strip()[:180] or 'command not found')))

ver, tag, ok, err = torch_state()
print('torch(子进程): %s | torch.version.cuda=%s | cuda.is_available()=%s' % (ver, tag, ok))
if err:
    print('  stderr:', err)

if not gpu:
    print('\n=== [2/4] 结论：当前 Colab 运行时没有挂 GPU ===')
    print('这不是 ComfyUI / comfy-kitchen / 依赖的问题，torch 二进制本身就是 CPU 版，')
    print('ComfyUI 在 comfy/model_management.py 读取显存时必然崩。')
    print('\n操作顺序：')
    print('  1) 菜单 Runtime → Change runtime type → Hardware accelerator 选 T4 GPU → Save')
    print('  2) Runtime → Disconnect and delete runtime，再重新连接（让 VM 真正换成 GPU 机型）')
    print('  3) 从头重跑所有 Cell：切换运行时会重置 VM，/content 清空，')
    print('     ComfyUI 与约 14 GB 权重需要重新下载（无法保留）。')
    print('  4) 若已选 T4 仍看不到 nvidia-smi：多半是免费 GPU 配额用尽，稍后重试或换账号。')
    STATE = 'NEED_GPU'
elif tag not in ('None', '', '?') and ok == 'True':
    print('\n=== [2/4] torch 已支持 CUDA，无需修复 ===')
    print('直接重跑「启动 ComfyUI」Cell 即可；若仍失败，贴 /content/comfyui.log 末尾 40 行。')
    STATE = 'OK'
else:
    print('\n=== [2/4] 结论：有 GPU，但 torch 是 CPU 版 ===')
    print('常见原因：安装 Cell 从 pypi.org 全量装 requirements.txt，')
    print('其中的 torch / torchvision 被重装成不带 CUDA 的 wheel。')
    STATE = 'NEED_FIX'


def reinstall_cuda_torch(base_ver):
    nv = run(['bash', '-lc', 'nvidia-smi | grep -o "CUDA Version: [0-9.]*" | head -1'], 30)
    m = re.search(r'(\d+)\.(\d+)', nv.stdout)
    cu = 'cu%s%s' % (m.group(1), m.group(2)) if m else None  # 13.0 -> cu130
    indices = []
    if cu:
        indices.append('https://download.pytorch.org/whl/' + cu)
    for c in ('cu130', 'cu128', 'cu126', 'cu124', 'cu121'):
        u = 'https://download.pytorch.org/whl/' + c
        if u not in indices:
            indices.append(u)
    indices.append('https://pypi.org/simple')  # Linux 默认 torch wheel 自带 CUDA 运行时

    pkgs = (['torch==' + base_ver, 'torchvision']
            if re.match(r'^\d+\.\d+', base_ver) else ['torch', 'torchvision'])
    for idx in indices:
        print('\n--- 尝试索引:', idx, flush=True)
        r = run([PY, '-m', 'pip', 'install', '--force-reinstall', '--no-cache-dir',
                 '--index-url', idx] + pkgs, 1200)
        if r.returncode != 0:
            print('  安装失败:', (r.stderr or r.stdout).strip()[-300:])
            continue
        chk = run(PROBE, 180)
        first = (chk.stdout or '').strip().splitlines()
        print('  验证:', ' | '.join(first[:3]) or (chk.stderr or '')[:300])
        if first and 'True' in first[-1] and 'None' not in ' '.join(first):
            return idx
    return None


if STATE == 'NEED_FIX':
    print('\n=== [3/4] 自动重装 CUDA 版 torch ===', flush=True)
    hit = reinstall_cuda_torch(ver.split('+')[0])
    if hit:
        print('\n=== [4/4] ✅ 已装好 CUDA 版 torch（来源 %s）' % hit)
        print('必须执行：Runtime → Restart runtime（只重启内核，不清空 /content，模型不用重下）')
        print('然后只重跑「启动 ComfyUI」Cell。')
        print('⚠️ 重启后不要再跑旧的「安装依赖」Cell，用仓库里已加固的笔记本（会过滤 torch 家族）。')
        STATE = 'FIXED_RESTART_REQUIRED'
    else:
        print('\n=== [4/4] ❌ 自动重装失败，用最稳的兜底 ===')
        print('Runtime → Disconnect and delete runtime → 确认 T4 GPU → 重新连接 → 从头重跑全部 Cell')
        print('Colab 的 GPU 镜像自带 torch+cu130，全新会话不会再出现 CPU 版。')
        STATE = 'FIX_FAILED'

print('\nSTATE =', STATE)
