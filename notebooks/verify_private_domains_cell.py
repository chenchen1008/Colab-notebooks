# 私有域名 / 临时域名统一验证 + 出图调用示例
# RUN_GENERATE 默认 False（只做健康检查，不消耗 GPU）；改成 True 才会真的出图（约 3-4 分钟）
import urllib.request, time, json

API   = 'https://qwythos.gmhqyj.ccwu.cc'                              # -> localhost:8010
COMFY = 'https://comfy.gmhqyj.ccwu.cc'                                # -> localhost:8188
QUICK = 'https://wholesale-priority-rover-winner.trycloudflare.com'   # 临时域名，Colab 重启后会变
RUN_GENERATE = False

def probe(label, url, timeout=45, retries=2):
    for i in range(retries + 1):
        t0 = time.time()
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                body = r.read()
                print('%-20s HTTP %s | %8d bytes | %.1fs | %s' % (
                    label, r.status, len(body), time.time() - t0,
                    body[:110].decode('utf-8', 'replace').replace('\n', ' ')))
                return r.status, body
        except Exception as e:
            if i == retries:
                print('%-20s 失败: %r' % (label, e))
                print('  gaierror / Name or service not known = DNS 还没生效，等 30-60 秒再跑本 Cell 即可，不是服务挂了')
                return None, None
            time.sleep(10)

probe('8010 health', API + '/health')
probe('8010 models', API + '/v1/models')
probe('8188 私有 /system_stats', COMFY + '/system_stats')
probe('8188 私有 Web UI', COMFY + '/')
probe('8188 临时 Web UI', QUICK + '/')
probe('8188 临时 /system_stats', QUICK + '/system_stats')

print('\n=== 地址用途 ===')
print('OpenAI 兼容 : %s/v1/images/generations   (base_url=%s/v1)' % (API, API))
print('ComfyUI UI  : %s  或  %s' % (COMFY, QUICK))
print('原生 API     : /prompt /history /view /object_info /system_stats，WebSocket /ws')
print('\n=== OpenAI 客户端写法（本地/其它机器上跑，需 pip install openai）===')
print("from openai import OpenAI")
print("client = OpenAI(base_url='%s/v1', api_key='not-needed')" % API)
print("r = client.images.generate(model='qwen-image-2.1-turbo-Q4_K_M.gguf',")
print("                          prompt='春日樱花下的江南小镇，水墨风格', size='1024x1024')")

if RUN_GENERATE:
    import requests, base64
    payload = {
        'model': 'qwen-image-2.1-turbo-Q4_K_M.gguf',
        'prompt': '春日樱花下的江南小镇，水墨风格，8K',
        'width': 1024, 'height': 1024, 'steps': 8, 'seed': 42, 'cfg': 1.0,
    }
    t0 = time.time()
    r = requests.post(API + '/v1/images/generations', json=payload, timeout=900)
    print('\n出图 HTTP %s | 端到端 %.1fs' % (r.status_code, time.time() - t0))
    if r.ok:
        img = base64.b64decode(r.json()['data'][0]['b64_json'])
        open('/content/private_domain_test.png', 'wb').write(img)
        print('已保存 /content/private_domain_test.png', len(img), 'bytes')
    else:
        print(r.text[:500])
