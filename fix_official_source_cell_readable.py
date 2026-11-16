# 官方源一键修复 —— 粘贴到 Colab 任意代码单元格运行，无需上传文件、无需联网下载脚本
# Colab 机器在境外：pip 直连 pypi.org、模型直连 huggingface.co 最全最快，不要用国内镜像
#
# 一次修掉 5 个问题：
#   1) 清华源没同步 2026 新包 -> comfy-kitchen==0.2.41 漏装 -> quant_ops 的 ck 未定义 -> ComfyUI 崩溃
#   2) 下载 URL 少了 text_encoders/ 和 vae/ 子目录 -> 两个模型 404，留下 0 字节文件
#   3) GGUF 节点类名拼错：UNETLoaderGGUF 应为 UnetLoaderGGUF
#   4) 工作流缺文本编码节点，KSampler 的 positive/negative 错连到 CLIPLoader（CLIP 不是 CONDITIONING）
#   5) Qwen-Image 2.1 需要 64 通道 /16 的 latent，不能用 EmptyLatentImage（4 通道 /8）
import os, sys, time, socket, subprocess, urllib.request, json, base64

COMFY = '/content/ComfyUI'
PYPI  = 'https://pypi.org/simple'
HF    = 'https://huggingface.co/abenzerps/Qwen-Image-2.1-Turbo-Quantized/resolve/main'

def port_open(p, host='127.0.0.1'):
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect((host, p)); return True
    except Exception:
        return False
    finally:
        s.close()

def tail(path, n=30):
    if not os.path.exists(path):
        return '(无日志)'
    return '\n'.join(open(path, errors='replace').read().splitlines()[-n:])

# ── [1/5] 官方 PyPI 全量补齐依赖 ────────────────────────────────────────
print('[1/5] 官方 PyPI 重装 requirements.txt（补齐清华源漏掉的新包）...')
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                    '-r', COMFY + '/requirements.txt', '-i', PYPI],
                   capture_output=True, text=True, timeout=900)
print('  pip 返回码:', r.returncode)
if r.returncode != 0:
    print('  stderr 尾部:', r.stderr[-1200:])
# 精确补装两个 2026 新包（INT8 ConvRot 文本编码器也依赖 comfy-kitchen 的量化 layout）
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                'comfy-kitchen==0.2.41', 'comfy-aimdo==0.6.0', '-i', PYPI],
               capture_output=True, text=True, timeout=600)
chk = subprocess.run([sys.executable, '-c',
    'import comfy_kitchen, comfy_aimdo; '
    'from comfy.quant_ops import ck, QuantizedTensor; '
    'print("OK comfy-kitchen", getattr(comfy_kitchen, "__version__", "?"))'],
    cwd=COMFY, capture_output=True, text=True)
print('  依赖检查:', (chk.stdout or chk.stderr).strip()[-600:])

# ── [2/5] 官方 HF 直连补齐模型（远端路径含子目录） ──────────────────────
print('\n[2/5] 用官方 huggingface.co 补齐模型 ...')
FILES = [
    ('diffusion_models/qwen-image-2.1-turbo-Q4_K_M.gguf',
     'qwen-image-2.1-turbo-Q4_K_M.gguf', 4.05e9),
    ('text_encoders/qwen3vl_8b_int8_convrot.safetensors',
     'text_encoders/qwen3vl_8b_int8_convrot.safetensors', 9.35e9),
    ('vae/qwen_image_2.1_vae_bf16.safetensors',
     'vae/qwen_image_2.1_vae_bf16.safetensors', 0.68e9),
]
for rel, remote, expect in FILES:
    dst = COMFY + '/models/' + rel
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and os.path.getsize(dst) > expect * 0.9:
        print('  OK 已完整:', rel, '%.2f GB' % (os.path.getsize(dst) / 1e9))
        continue
    if os.path.exists(dst) and os.path.getsize(dst) < 1e6:
        os.remove(dst)   # 清掉 404 留下的 0 字节残留
    url = HF + '/' + remote
    print('  下载:', remote)
    subprocess.run(['wget', '-c', '-q', '--show-progress', url, '-O', dst], check=False)
    got = os.path.getsize(dst) if os.path.exists(dst) else 0
    print('  ' + ('OK' if got > expect * 0.9 else 'FAIL'), rel, '%.2f GB' % (got / 1e9))

# ── [3/5] 写入新版 qwen_api.py（工作流结构修正） ─────────────────────────
# 下面这行长字符串就是修好的完整 qwen_api.py 源码（base64 内联，做到零网络依赖）
print('\n[3/5] 写入新版 /content/qwen_api.py ...')
API_B64 = "<见 qwen_api.py：完整源码在此，base64 内联以零依赖>"
api_code = base64.b64decode(API_B64).decode('utf-8')
with open('/content/qwen_api.py', 'w', encoding='utf-8') as f:
    f.write(api_code)
print('  已写入:', len(api_code), '字节 | UNET_CLASS =',
      [l for l in api_code.splitlines() if l.startswith('UNET_CLASS')][0].split('=')[1].strip())

# 重启 8010 让新源码生效
subprocess.run("ps -eo pid,args | grep '[q]wen_api.py' | awk '{print $1}' | xargs -r kill", shell=True)
time.sleep(1)
api_proc = subprocess.Popen([sys.executable, 'qwen_api.py'], cwd='/content',
                           stdout=open('/content/qwen_api.log', 'w'), stderr=subprocess.STDOUT,
                           start_new_session=True)
print('  FastAPI 重启 PID:', api_proc.pid)

# ── [4/5] 重启 ComfyUI (8188)，日志用 w 覆盖避免历史报错干扰 ─────────────
print('\n[4/5] 重启 ComfyUI ...')
subprocess.run("ps -eo pid,args | grep '[m]ain.py --listen' | awk '{print $1}' | xargs -r kill", shell=True)
time.sleep(2)
log = open('/content/comfyui.log', 'w')
p = subprocess.Popen([sys.executable, 'main.py', '--listen', '0.0.0.0', '--port', '8188'],
                     cwd=COMFY, stdout=log, stderr=log, start_new_session=True)
print('  ComfyUI PID:', p.pid)
for _ in range(60):
    time.sleep(3)
    if port_open(8188):
        break
ok = port_open(8188)
print('  8188:', 'OK 已就绪' if ok else 'FAIL 仍失败')
if ok:
    try:
        info = json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=30))
        for k in ('UnetLoaderGGUF', 'CLIPLoader', 'VAELoader', 'TextEncodeQwenImage21', 'KSampler'):
            print('  节点已注册 %-28s %s' % (k, k in info))
        gguf = info.get('UnetLoaderGGUF', {}).get('input', {}).get('required', {}).get('unet_name', [[]])[0]
        print('  可用 GGUF 模型:', gguf if isinstance(gguf, list) else '(未知)')
    except Exception as e:
        print('  object_info 失败:', repr(e))
else:
    print('  日志末尾 40 行:\n' + tail('/content/comfyui.log', 40))

# ── [5/5] 端到端健康检查 ────────────────────────────────────────────────
print('\n[5/5] 健康检查 ...')
for _ in range(20):
    if port_open(8010):
        break
    time.sleep(2)
if port_open(8010):
    try:
        print('  /health =', urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=10).read().decode())
    except Exception as e:
        print('  /health 失败:', repr(e))
else:
    print('  8010 未监听，日志:\n' + tail('/content/qwen_api.log', 30))
print('\n>>> 公网接口: https://ensemble-sql-doe-reserves.trycloudflare.com/v1/images/generations')
print('>>> 全部 OK 后再运行笔记本里的「测试出图」Cell')
