# 热启动性能复测 —— 模型已常驻显存，测真实单图推理耗时（排除首次 14GB 加载）
# 首次冷启动实测 216.5 s；这一格测热启动，并做 1024 / 768 分辨率对比
import time, base64, requests
from IPython.display import Image, display

API = 'http://127.0.0.1:8010'
PUB = 'https://ensemble-sql-doe-reserves.trycloudflare.com'
COLD = 216.5  # 上一格实测的冷启动耗时（秒）

PROMPT = '一只穿宇航服的猫坐在月球表面，背景是地球升起，电影级光照，超细节，4K'
CASES = [
    ('1024x1024 / 8 steps 热启动', dict(width=1024, height=1024, steps=8)),
    ('768x768  / 8 steps',        dict(width=768,  height=768,  steps=8)),
]

rows = []
for label, kw in CASES:
    payload = dict(prompt=PROMPT, seed=42, cfg=1.0, **kw)
    t0 = time.time()
    try:
        r = requests.post(API + '/v1/images/generations', json=payload, timeout=900)
    except Exception as e:
        print('%-28s FAIL 请求异常 %r' % (label, e))
        continue
    dt = time.time() - t0
    res = r.json()
    if 'error' in res:
        print('%-28s FAIL %s | %s' % (label, res.get('error'), res.get('detail', '')[:400]))
        continue
    png = '/content/qwen_warm_%d.png' % len(rows)
    open(png, 'wb').write(base64.b64decode(res['data'][0]['b64_json']))
    rows.append((label, dt, kw['steps'], png))
    print('%-28s %7.1f s | %5.2f s/step | %s' % (label, dt, dt / kw['steps'], png))

if rows:
    avg = sum(x[1] for x in rows) / len(rows)
    print('\n热启动均值 %.1f s | 冷启动 %.1f s -> 加速 %.2fx' % (avg, COLD, COLD / avg))
    print('注意：冷启动含 14GB 模型加载 + 首次 CUDA 初始化，不能直接当推理速度对比。')
    display(Image(filename=rows[0][3]))

# 公网 OpenAI 兼容接口轻量验证（只查模型列表，不触发耗时的生成）
print('\n[公网验证]')
try:
    m = requests.get(PUB + '/v1/models', timeout=30)
    print('   GET %s/v1/models -> %s %s' % (PUB, m.status_code, str(m.json())[:200]))
except Exception as e:
    print('   失败(不影响本地出图):', repr(e))
print('   OpenAI 客户端: OpenAI(base_url="%s/v1", api_key="任意")' % PUB)
print('                 .images.generate(model="qwen-image-2.1-turbo-Q4_K_M.gguf", prompt=..., size="1024x1024")')
