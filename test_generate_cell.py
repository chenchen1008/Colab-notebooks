# 测试出图 —— 服务全绿后运行这一格
# 首次要把 7B DiT + 8B 文本编码器载入 T4，耗时数分钟；打印端到端耗时、显存与完整错误
import os, time, base64, subprocess, requests
from IPython.display import Image, display

API   = 'http://127.0.0.1:8010'
COMFY = 'http://127.0.0.1:8188'
PUB   = 'https://ensemble-sql-doe-reserves.trycloudflare.com'

def vram():
    try:
        return subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return 'n/a'

def comfy_log(n=40):
    try:
        return '\n'.join(open('/content/comfyui.log', errors='replace').read().splitlines()[-n:])
    except Exception as e:
        return '读日志失败: ' + repr(e)

# ── [0] 预检：确认节点定义与代理里的工作流一致 ──────────────────────────
print('[0] 预检 ...')
try:
    print('   /health =', requests.get(API + '/health', timeout=10).json())
    n = requests.get(COMFY + '/object_info/TextEncodeQwenImage21', timeout=20).json()['TextEncodeQwenImage21']
    print('   TextEncodeQwenImage21 必填输入:', list(n['input'].get('required', {}).keys()))
    print('   TextEncodeQwenImage21 可选输入:', list(n['input'].get('optional', {}).keys()))
    print('   输出:', n.get('output'), '|', n.get('output_name'))
    ct = requests.get(COMFY + '/object_info/CLIPLoader', timeout=20).json()['CLIPLoader']['input']['required']['type'][0]
    print('   CLIPLoader 支持 qwen_image:', 'qwen_image' in ct)
except Exception as e:
    print('   预检异常（不阻断出图）:', repr(e))
print('   显存 used,total (MiB):', vram())

# ── [1] 出图 ───────────────────────────────────────────────────────────
payload = {
    'prompt': '一只穿宇航服的猫坐在月球表面，背景是地球升起，电影级光照，超细节，4K',
    'width': 1024, 'height': 1024, 'steps': 8, 'seed': 42, 'cfg': 1.0,
}
print('\n[1] 提交出图 | 1024x1024 / 8 steps / euler / cfg=1.0 ...')
t0 = time.time()
try:
    r = requests.post(API + '/v1/images/generations', json=payload, timeout=1200)
except Exception as e:
    print('[FAIL] 请求异常:', repr(e))
    print('\n--- comfyui.log 末尾 40 行 ---\n' + comfy_log())
    raise
dt = time.time() - t0
print('HTTP %s | 端到端耗时 %.1f 秒 (%.2f 分钟)' % (r.status_code, dt, dt / 60))
print('显存 used,total (MiB):', vram())
res = r.json()

if 'error' in res:
    print('[FAIL]', res.get('error'))
    print(res.get('detail', '')[:3000])
    print('\n--- comfyui.log 末尾 40 行 ---\n' + comfy_log())
else:
    png = '/content/qwen_image_test.png'
    raw = base64.b64decode(res['data'][0]['b64_json'])
    open(png, 'wb').write(raw)
    print('[OK] 已保存:', png, len(raw), '字节 | 返回图片数:', len(res['data']))
    display(Image(filename=png))

    # ── [2] 公网 OpenAI 兼容接口轻量验证 ────────────────────────────────
    print('\n[2] 公网接口验证 ...')
    try:
        m = requests.get(PUB + '/v1/models', timeout=30)
        print('   GET /v1/models ->', m.status_code, str(m.json())[:200])
    except Exception as e:
        print('   公网验证失败（不影响本地出图）:', repr(e))
    print('   OpenAI 客户端: base_url=%s/v1 | api_key=任意字符串 | model=qwen-image-2.1-turbo-Q4_K_M.gguf' % PUB)
