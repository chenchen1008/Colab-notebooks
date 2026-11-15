# 修复 ComfyUI 启动失败：ModuleNotFoundError: No module named 'comfy_aimdo'
# comfy-aimdo 是 ComfyUI 新版核心依赖（DynamicVRAM），requirements.txt 装漏多半是清华源没同步
# 502 已解决（8010 已监听），这一格只负责让 8188 活过来
import os, sys, time, socket, subprocess, urllib.request, json

def port_open(p, host='127.0.0.1'):
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect((host, p))
        return True
    except Exception:
        return False
    finally:
        s.close()

def tail(path, n=30):
    if not os.path.exists(path):
        return '(无日志)'
    return '\n'.join(open(path, errors='replace').read().splitlines()[-n:])

# 1) 装 comfy-aimdo（优先跟随 requirements.txt 锁的版本，走官方 PyPI）
pkg = 'comfy-aimdo'
req = '/content/ComfyUI/requirements.txt'
if os.path.exists(req):
    for line in open(req, errors='replace'):
        s = line.strip()
        if s.lower().replace('_', '-').startswith('comfy-aimdo'):
            pkg = s
            break
print('安装目标:', pkg)
r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg,
                    '-i', 'https://pypi.org/simple'], capture_output=True, text=True)
print('pip 返回码:', r.returncode)
if r.returncode != 0:
    print('pip stderr:', r.stderr[-1000:])
    print('改用默认源重试 ...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'comfy-aimdo'], check=False)
chk = subprocess.run([sys.executable, '-c', 'import comfy_aimdo.control; print("comfy_aimdo OK")'],
                     cwd='/content/ComfyUI', capture_output=True, text=True)
print('导入检查:', (chk.stdout or chk.stderr).strip()[-500:])

# 2) 重启 ComfyUI (8188)
subprocess.run("ps -eo pid,args | grep '[m]ain.py --listen' | awk '{print $1}' | xargs -r kill", shell=True)
time.sleep(1)
log = open('/content/comfyui.log', 'a')
p = subprocess.Popen([sys.executable, 'main.py', '--listen', '0.0.0.0', '--port', '8188'],
                     cwd='/content/ComfyUI', stdout=log, stderr=log, start_new_session=True)
print('ComfyUI PID:', p.pid)
for _ in range(60):
    time.sleep(3)
    if port_open(8188):
        break
print('ComfyUI 8188:', '✅ 已就绪' if port_open(8188) else '❌ 仍失败')
if port_open(8188):
    try:
        info = json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=20))
        print('UNETLoaderGGUF 节点已注册:', 'UNETLoaderGGUF' in info)
    except Exception as e:
        print('object_info 失败:', repr(e))
else:
    print('日志末尾 40 行:\n' + tail('/content/comfyui.log', 40))

# 3) 检查模型三件套是否下载完整（避免下一步出图才发现）
for path, expect in [
    ('/content/ComfyUI/models/diffusion_models/qwen-image-2.1-turbo-Q4_K_M.gguf', 4.05e9),
    ('/content/ComfyUI/models/text_encoders/qwen3vl_8b_int8_convrot.safetensors', 9.35e9),
    ('/content/ComfyUI/models/vae/qwen_image_2.1_vae_bf16.safetensors', 0.68e9),
]:
    sz = os.path.getsize(path) if os.path.exists(path) else 0
    print(('✅' if sz > expect * 0.9 else '❌'), os.path.basename(path), '%.2f GB' % (sz / 1e9))

# 4) 端到端健康检查
if port_open(8010):
    try:
        print('/health =', urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=10).read().decode())
    except Exception as e:
        print('/health 失败:', repr(e))
else:
    print('⚠️ 8010 未监听，请再跑一次上一格修复代码')
print('>>> 公网接口: https://ensemble-sql-doe-reserves.trycloudflare.com/v1/images/generations')
