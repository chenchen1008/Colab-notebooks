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
API_B64 = "IyBPcGVuQUkg5YW85a655Luj55CG77ya5oqKIENvbWZ5VUkg55qEIFF3ZW4tSW1hZ2UgMi4xIOW3peS9nOa1geWMheijheaIkCAvdjEvaW1hZ2VzL2dlbmVyYXRpb25zCiMg6IqC54K557uT5p6E5oyJIENvbWZ5VUkg5a6Y5pa5IGltYWdlX3F3ZW5faW1hZ2VfMl8xX3QyaSDlt6XkvZzmtYEgKyBDb21meVVJLUdHVUYg5L+u5q2j77yaCiMgICBVbmV0TG9hZGVyR0dVRiAvIENMSVBMb2FkZXIodHlwZT1xd2VuX2ltYWdlKSAvIFZBRUxvYWRlcgojICAgVGV4dEVuY29kZVF3ZW5JbWFnZTIx77yI5ZCM5pe26L6T5Ye6IHBvc2l0aXZlIC8gbmVnYXRpdmUgLyA2NCDpgJrpgZPnqbogbGF0ZW5077yJCiMgICBLU2FtcGxlciAvIFZBRURlY29kZSAvIFNhdmVJbWFnZQpmcm9tIGZhc3RhcGkgaW1wb3J0IEZhc3RBUEkKZnJvbSBweWRhbnRpYyBpbXBvcnQgQmFzZU1vZGVsCmltcG9ydCByZXF1ZXN0cywgYmFzZTY0LCB1dWlkLCB0aW1lLCB1dmljb3JuLCB0cmFjZWJhY2sKCmFwcCA9IEZhc3RBUEkodGl0bGU9J1F3ZW4tSW1hZ2UtMi4xLVR1cmJvIHByb3h5JykKQ09NRlkgPSAnaHR0cDovLzEyNy4wLjAuMTo4MTg4JwpVTkVUID0gJ3F3ZW4taW1hZ2UtMi4xLXR1cmJvLVE0X0tfTS5nZ3VmJwpDTElQID0gJ3F3ZW4zdmxfOGJfaW50OF9jb252cm90LnNhZmV0ZW5zb3JzJwpWQUUgPSAncXdlbl9pbWFnZV8yLjFfdmFlX2JmMTYuc2FmZXRlbnNvcnMnClVORVRfQ0xBU1MgPSAnVW5ldExvYWRlckdHVUYnCgpjbGFzcyBJbWFnZUdlblJlcXVlc3QoQmFzZU1vZGVsKToKICAgIHByb21wdDogc3RyCiAgICBtb2RlbDogc3RyID0gVU5FVAogICAgd2lkdGg6IGludCA9IDEwMjQKICAgIGhlaWdodDogaW50ID0gMTAyNAogICAgc3RlcHM6IGludCA9IDgKICAgIHNlZWQ6IGludCA9IC0xCiAgICBjZmc6IGZsb2F0ID0gMS4wCiAgICBuZWdhdGl2ZV9wcm9tcHQ6IHN0ciA9ICcnCgpAYXBwLmdldCgnLycpCmRlZiByb290KCk6CiAgICByZXR1cm4geydzdGF0dXMnOiAnb2snLCAnYmFja2VuZCc6IENPTUZZLCAnZW5kcG9pbnQnOiAnL3YxL2ltYWdlcy9nZW5lcmF0aW9ucyd9CgpAYXBwLmdldCgnL2hlYWx0aCcpCmRlZiBoZWFsdGgoKToKICAgIHRyeToKICAgICAgICByZXF1ZXN0cy5nZXQoQ09NRlkgKyAnL3N5c3RlbV9zdGF0cycsIHRpbWVvdXQ9NSkucmFpc2VfZm9yX3N0YXR1cygpCiAgICAgICAgcmV0dXJuIHsnb2snOiBUcnVlLCAnY29tZnl1aSc6ICd1cCd9CiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGU6CiAgICAgICAgcmV0dXJuIHsnb2snOiBGYWxzZSwgJ2NvbWZ5dWknOiByZXByKGUpfQoKQGFwcC5nZXQoJy92MS9tb2RlbHMnKQpkZWYgbW9kZWxzKCk6CiAgICByZXR1cm4geydvYmplY3QnOiAnbGlzdCcsICdkYXRhJzogW3snaWQnOiBVTkVULCAnb2JqZWN0JzogJ21vZGVsJ31dfQoKZGVmIGJ1aWxkX3dvcmtmbG93KHJlcTogSW1hZ2VHZW5SZXF1ZXN0KToKICAgIHNlZWQgPSByZXEuc2VlZCBpZiByZXEuc2VlZCBhbmQgcmVxLnNlZWQgPj0gMCBlbHNlIHV1aWQudXVpZDQoKS5pbnQgPj4gNjQKICAgICMgUXdlbi1JbWFnZSAyLjEg55qEIGxhdGVudCDmmK8gNjQg6YCa6YGT44CB6L656ZW/IC8xNu+8jOeUsSBUZXh0RW5jb2RlUXdlbkltYWdlMjEg55Sf5oiQ77yMCiAgICAjIOS4jeiDveeUqCBFbXB0eUxhdGVudEltYWdl77yI6YKj5pivIDQg6YCa6YGT44CB6L656ZW/IC84IOeahOiAgeagvOW8j++8ieOAggogICAgIyDor6XoioLngrnml6Dlj4LogIPlm77ml7bovpPlh7rmraPmlrnlvaIgbGF0ZW5077yM6L656ZW/55SxIHJlc29sdXRpb24g5Yaz5a6a44CCCiAgICByZXNvbHV0aW9uID0gbWF4KDMyLCAobWF4KHJlcS53aWR0aCwgcmVxLmhlaWdodCkgLy8gMzIpICogMzIpCiAgICByZXR1cm4gewogICAgICAgICcxJzogeydpbnB1dHMnOiB7J3VuZXRfbmFtZSc6IHJlcS5tb2RlbH0sICdjbGFzc190eXBlJzogVU5FVF9DTEFTU30sCiAgICAgICAgJzInOiB7J2lucHV0cyc6IHsnY2xpcF9uYW1lJzogQ0xJUCwgJ3R5cGUnOiAncXdlbl9pbWFnZSd9LCAnY2xhc3NfdHlwZSc6ICdDTElQTG9hZGVyJ30sCiAgICAgICAgJzMnOiB7J2lucHV0cyc6IHsndmFlX25hbWUnOiBWQUV9LCAnY2xhc3NfdHlwZSc6ICdWQUVMb2FkZXInfSwKICAgICAgICAnNCc6IHsnaW5wdXRzJzogewogICAgICAgICAgICAnY2xpcCc6IFsnMicsIDBdLAogICAgICAgICAgICAncHJvbXB0JzogcmVxLnByb21wdCwKICAgICAgICAgICAgJ25lZ2F0aXZlX3Byb21wdCc6IHJlcS5uZWdhdGl2ZV9wcm9tcHQsCiAgICAgICAgICAgICd2YWUnOiBbJzMnLCAwXSwKICAgICAgICAgICAgJ3Jlc29sdXRpb24nOiByZXNvbHV0aW9uLAogICAgICAgIH0sICdjbGFzc190eXBlJzogJ1RleHRFbmNvZGVRd2VuSW1hZ2UyMSd9LAogICAgICAgICc1JzogeydpbnB1dHMnOiB7CiAgICAgICAgICAgICdtb2RlbCc6IFsnMScsIDBdLAogICAgICAgICAgICAncG9zaXRpdmUnOiBbJzQnLCAwXSwKICAgICAgICAgICAgJ25lZ2F0aXZlJzogWyc0JywgMV0sCiAgICAgICAgICAgICdsYXRlbnRfaW1hZ2UnOiBbJzQnLCAyXSwKICAgICAgICAgICAgJ3NlZWQnOiBpbnQoc2VlZCksCiAgICAgICAgICAgICdzdGVwcyc6IHJlcS5zdGVwcywKICAgICAgICAgICAgJ2NmZyc6IHJlcS5jZmcsCiAgICAgICAgICAgICdzYW1wbGVyX25hbWUnOiAnZXVsZXInLAogICAgICAgICAgICAnc2NoZWR1bGVyJzogJ25vcm1hbCcsCiAgICAgICAgICAgICdkZW5vaXNlJzogMS4wLAogICAgICAgIH0sICdjbGFzc190eXBlJzogJ0tTYW1wbGVyJ30sCiAgICAgICAgJzYnOiB7J2lucHV0cyc6IHsnc2FtcGxlcyc6IFsnNScsIDBdLCAndmFlJzogWyczJywgMF19LCAnY2xhc3NfdHlwZSc6ICdWQUVEZWNvZGUnfSwKICAgICAgICAnNyc6IHsnaW5wdXRzJzogeydpbWFnZXMnOiBbJzYnLCAwXSwgJ2ZpbGVuYW1lX3ByZWZpeCc6ICdxd2VuX2NvbGFiJ30sICdjbGFzc190eXBlJzogJ1NhdmVJbWFnZSd9LAogICAgfQoKQGFwcC5wb3N0KCcvdjEvaW1hZ2VzL2dlbmVyYXRpb25zJykKZGVmIGdlbmVyYXRlKHJlcTogSW1hZ2VHZW5SZXF1ZXN0KToKICAgIHRyeToKICAgICAgICByID0gcmVxdWVzdHMucG9zdChDT01GWSArICcvcHJvbXB0JywganNvbj17J3Byb21wdCc6IGJ1aWxkX3dvcmtmbG93KHJlcSl9LCB0aW1lb3V0PTMwKQogICAgICAgIGlmIHIuc3RhdHVzX2NvZGUgIT0gMjAwOgogICAgICAgICAgICByZXR1cm4geydlcnJvcic6ICdjb21meXVpIC9wcm9tcHQgcmVqZWN0ZWQnLCAnZGV0YWlsJzogci50ZXh0WzoxNTAwXX0KICAgICAgICBwaWQgPSByLmpzb24oKVsncHJvbXB0X2lkJ10KICAgICAgICBvdXRzID0gTm9uZQogICAgICAgIGZvciBfIGluIHJhbmdlKDI0MCk6CiAgICAgICAgICAgIHRpbWUuc2xlZXAoMikKICAgICAgICAgICAgaCA9IHJlcXVlc3RzLmdldChDT01GWSArIGYnL2hpc3Rvcnkve3BpZH0nLCB0aW1lb3V0PTEwKS5qc29uKCkKICAgICAgICAgICAgaWYgcGlkIGluIGggYW5kICdvdXRwdXRzJyBpbiBoW3BpZF06CiAgICAgICAgICAgICAgICBvdXRzID0gaFtwaWRdWydvdXRwdXRzJ10KICAgICAgICAgICAgICAgIGJyZWFrCiAgICAgICAgICAgIGlmIHBpZCBpbiBoIGFuZCBoW3BpZF0uZ2V0KCdzdGF0dXMnLCB7fSkuZ2V0KCdzdGF0dXNfc3RyJykgPT0gJ2Vycm9yJzoKICAgICAgICAgICAgICAgIHJldHVybiB7J2Vycm9yJzogJ2NvbWZ5dWkgZXhlY3V0aW9uIGVycm9yJywgJ2RldGFpbCc6IHN0cihoW3BpZF0uZ2V0KCdzdGF0dXMnKSlbOjE1MDBdfQogICAgICAgIGlmIG91dHMgaXMgTm9uZToKICAgICAgICAgICAgcmV0dXJuIHsnZXJyb3InOiAnZ2VuZXJhdGlvbiB0aW1lb3V0J30KICAgICAgICBpbWFnZXMgPSBbXQogICAgICAgIGZvciBub2RlX2lkLCBvdXQgaW4gb3V0cy5pdGVtcygpOgogICAgICAgICAgICBmb3IgaW1nIGluIG91dC5nZXQoJ2ltYWdlcycsIFtdKToKICAgICAgICAgICAgICAgIGRhdGEgPSByZXF1ZXN0cy5nZXQoQ09NRlkgKyAnL3ZpZXcnLAogICAgICAgICAgICAgICAgICAgIHBhcmFtcz17J2ZpbGVuYW1lJzogaW1nWydmaWxlbmFtZSddLCAnc3ViZm9sZGVyJzogaW1nLmdldCgnc3ViZm9sZGVyJywgJycpLCAndHlwZSc6ICdvdXRwdXQnfSwKICAgICAgICAgICAgICAgICAgICB0aW1lb3V0PTYwKS5jb250ZW50CiAgICAgICAgICAgICAgICBpbWFnZXMuYXBwZW5kKHsnYjY0X2pzb24nOiBiYXNlNjQuYjY0ZW5jb2RlKGRhdGEpLmRlY29kZSgnYXNjaWknKX0pCiAgICAgICAgaWYgbm90IGltYWdlczoKICAgICAgICAgICAgcmV0dXJuIHsnZXJyb3InOiAnbm8gaW1hZ2VzIGluIG91dHB1dCcsICdkZXRhaWwnOiBzdHIob3V0cylbOjE1MDBdfQogICAgICAgIHJldHVybiB7J2NyZWF0ZWQnOiBpbnQodGltZS50aW1lKCkpLCAnZGF0YSc6IGltYWdlc30KICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgcmV0dXJuIHsnZXJyb3InOiAncHJveHkgZXhjZXB0aW9uJywgJ2RldGFpbCc6IHRyYWNlYmFjay5mb3JtYXRfZXhjKClbLTE1MDA6XX0KCmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6CiAgICBwcmludCgncXdlbl9hcGk6IGxpc3RlbmluZyBvbiAwLjAuMC4wOjgwMTAgLT4gJyArIENPTUZZLCBmbHVzaD1UcnVlKQogICAgdXZpY29ybi5ydW4oYXBwLCBob3N0PScwLjAuMC4wJywgcG9ydD04MDEwLCBsb2dfbGV2ZWw9J2luZm8nKQo="
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
