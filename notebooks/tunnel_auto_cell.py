# -*- coding: utf-8 -*-
"""Qwen 隧道自动二选一 Cell：有 Secret 用私有域名，没有走 trycloudflare。

在 Colab 新建一个 Cell 整段粘贴运行；或：
    import urllib.request
    src = urllib.request.urlopen(
        'https://raw.githubusercontent.com/chenchen1008/Colab-notebooks/main/notebooks/tunnel_auto_cell.py',
        timeout=30).read().decode('utf-8')
    exec(compile(src, 'tunnel_auto_cell.py', 'exec'))
等价于最新 14 Cell 笔记本的「cloudflared 公网隧道」Cell（index 8）。
"""
import subprocess, re, time, os, json, base64, urllib.request

TUNNEL_PORT = 8010   # 改成 8188 即直连 ComfyUI 原生 API（不需要 FastAPI 这层）
CF = '/usr/local/bin/cloudflared'
API_HOST = 'https://qwythos.gmhqyj.ccwu.cc'      # Public Hostname -> localhost:8010
COMFY_HOST = 'https://comfy.gmhqyj.ccwu.cc'      # Public Hostname -> localhost:8188
PRIVATE_HOST = API_HOST if TUNNEL_PORT == 8010 else COMFY_HOST
PROBE_PATH = '/health' if TUNNEL_PORT == 8010 else '/system_stats'

if not os.path.exists(CF):
    subprocess.run(['wget', '-q',
        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',
        '-O', CF], check=True)
    subprocess.run(['chmod', '+x', CF], check=True)

# ---- 1) 有 Secret 用私有域名，没有（或本笔记本未授权）走 trycloudflare ----
TOKEN = None
try:
    from google.colab import userdata
    TOKEN = userdata.get('CF_TUNNEL_TOKEN')
except Exception as e:
    print('未读取到 Secret CF_TUNNEL_TOKEN（%s）→ 走 quick tunnel' % type(e).__name__)
if not TOKEN:
    print('未配置 Secret CF_TUNNEL_TOKEN → 走 quick tunnel')
else:
    try:
        meta = json.loads(base64.b64decode(TOKEN))
        assert meta.get('a') and meta.get('t') and meta.get('s'), 'token 缺字段'
        print('检测到 Secret CF_TUNNEL_TOKEN | Tunnel ID:', meta['t'])
    except Exception as e:
        print('Secret 不是有效的隧道 token（%r）→ 走 quick tunnel' % e)
        TOKEN = None

def quick_tunnel():
    """无 Secret 或私有域名不可用：开 quick tunnel，拿 trycloudflare.com 临时域名"""
    cmd = "ps -eo args | grep -c '[c]loudflared.*--url http://localhost:%d'" % TUNNEL_PORT
    running = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
    log_path = '/content/cloudflared.log'
    if running != '0' and os.path.exists(log_path):
        m = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',
                       open(log_path, errors='replace').read())
        if m:
            print('已有指向 %d 的 quick tunnel，沿用原域名' % TUNNEL_PORT)
            return m[0]
    tlog = open(log_path, 'w')
    subprocess.Popen([CF, 'tunnel', '--no-autoupdate', '--url',
                      'http://localhost:%d' % TUNNEL_PORT],
                     stdout=tlog, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(40):
        time.sleep(2)
        m = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',
                       open(log_path, errors='replace').read())
        if m:
            return m[0]
    print('未取到临时域名，日志末尾：\n', open(log_path, errors='replace').read()[-800:])
    return None

def stop_named():
    subprocess.run("ps -eo pid,args | grep '[c]loudflared tunnel.*run --token' "
                   "| awk '{print $1}' | xargs -r kill", shell=True)

def private_tunnel():
    """有 Secret：接管 Named Tunnel，并验证固定域名是否真的可用"""
    stop_named()
    time.sleep(1)
    log = open('/content/cloudflared_named.log', 'w')
    p = subprocess.Popen([CF, 'tunnel', '--no-autoupdate', '--loglevel', 'info',
                          'run', '--token', TOKEN],
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    print('Named Tunnel PID:', p.pid, '| 等待云端下发 ingress ...')
    for attempt in range(8):
        time.sleep(5)
        try:
            with urllib.request.urlopen(PRIVATE_HOST + PROBE_PATH, timeout=20) as r:
                body = r.read()
            if TUNNEL_PORT == 8010 and json.loads(body).get('ok') is not True:
                continue
            print('✅ 私有域名验证通过:', PRIVATE_HOST + PROBE_PATH)
            return True
        except Exception as e:
            if attempt == 7:
                print('私有域名验证失败: %r' % e)
    print('⚠️ 检查 Zero Trust → Public Hostname 与本地 %d 端口；先回退 quick tunnel' % TUNNEL_PORT)
    return False

PRIVATE_OK = bool(TOKEN) and private_tunnel()
if PRIVATE_OK:
    PUBLIC_BASE = PRIVATE_HOST
    print('>>> 私有域名模式（Secret CF_TUNNEL_TOKEN 已启用）')
    print('>>> 另一条固定域名:', COMFY_HOST if TUNNEL_PORT == 8010 else API_HOST)
else:
    if TOKEN:
        stop_named()   # 私有域名验证失败，停掉 named 再走临时域名
    PUBLIC_BASE = quick_tunnel()
    print('>>> quick tunnel 模式（临时域名，每次重启会变）')

if PUBLIC_BASE:
    print('>>> 公网地址:', PUBLIC_BASE)
    if TUNNEL_PORT == 8010:
        print('>>> OpenAI 兼容接口:', PUBLIC_BASE + '/v1/images/generations')
    else:
        print('>>> ComfyUI 原生 API:', PUBLIC_BASE + '/system_stats')
else:
    print('❌ 没拿到公网地址，等 30-60 秒重跑本 Cell')
