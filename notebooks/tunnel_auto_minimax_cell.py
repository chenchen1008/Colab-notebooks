# -*- coding: utf-8 -*-
"""MiniMax H3-Image 隧道自动二选一 Cell：有 Secret 用私有域名，没有走 trycloudflare。

在 Colab 新建一个 Cell 整段粘贴运行；或：
    import urllib.request
    src = urllib.request.urlopen(
        'https://raw.githubusercontent.com/chenchen1008/Colab-notebooks/main/notebooks/tunnel_auto_minimax_cell.py',
        timeout=30).read().decode('utf-8')
    exec(compile(src, 'tunnel_auto_minimax_cell.py', 'exec'))
等价于最新 9 Cell 笔记本的「启动 ComfyUI 8188 + 公网隧道」Cell（index 6）里的隧道部分。
本 Cell 只负责隧道，ComfyUI 需已在 8188 监听。
"""
import os, re, time, subprocess, urllib.request, json, base64

PORT = 8188
CF = '/usr/local/bin/cloudflared'
TLOG = '/content/cloudflared.log'

PRIVATE_HOST = 'https://comfy.gmhqyj.ccwu.cc'   # Public Hostname -> localhost:8188
SECRET_CANDIDATES = ['CF_TUNNEL_TOKEN_MINIMAX', 'CF_TUNNEL_TOKEN']  # 独立 Secret 优先
ALLOW_SHARED_TOKEN = True   # False：检测到共享的 CF_TUNNEL_TOKEN 时不抢 Qwen 会话，直接走临时域名

if not os.path.exists(CF):
    subprocess.run(['wget', '-q',
        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',
        '-O', CF], check=True)
    os.chmod(CF, 0o755)

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
