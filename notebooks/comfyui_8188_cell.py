# 给 ComfyUI (8188) 单独开一条公网隧道，不影响现有指向 8010 的 trycloudflare.com 域名
# 一个 quick tunnel 只能绑一个本地端口，所以 8010 与 8188 需要两条独立隧道/两个域名
# 若要走自有域名：见文末说明，在 Cloudflare Zero Trust 里给同一个 Named Tunnel 加两条 Public Hostname
import subprocess, re, time, os, socket, urllib.request, json

PORT = 8188
CF = '/usr/local/bin/cloudflared'

if not os.path.exists(CF):
    subprocess.run(['wget', '-q',
        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',
        '-O', CF], check=True)
    subprocess.run(['chmod', '+x', CF], check=True)

def port_open(p):
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect(('127.0.0.1', p)); return True
    except Exception:
        return False
    finally:
        s.close()

if not port_open(PORT):
    raise RuntimeError('8188 未监听：先重跑「启动 ComfyUI」Cell，确认 /content/comfyui.log 无报错')

# 保留旧的 8010 隧道，只清理本条 8188 隧道的旧进程（可重复运行本 Cell）
subprocess.run(
    "ps -eo pid,args | grep '[c]loudflared.*--url http://localhost:8188' | awk '{print $1}' | xargs -r kill",
    shell=True)
time.sleep(1)

LOG = '/content/cloudflared_8188.log'
log = open(LOG, 'w')
p = subprocess.Popen(
    [CF, 'tunnel', '--no-autoupdate', '--url', 'http://localhost:%d' % PORT],
    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print('8188 隧道 PID:', p.pid)

URL = None
for _ in range(40):
    time.sleep(2)
    m = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',
                   open(LOG, errors='replace').read())
    if m:
        URL = m[0]; break

print('\n>>> ComfyUI 公网地址:', URL or '未获取到域名，日志末尾见下')
if not URL:
    print(open(LOG, errors='replace').read()[-1500:])

if URL:
    for path in ['/', '/system_stats', '/object_info']:
        try:
            with urllib.request.urlopen(URL + path, timeout=45) as r:
                body = r.read()
                print('  %-15s -> HTTP %s, %d bytes' % (path, r.status, len(body)))
                if path == '/system_stats' and len(body) < 2000:
                    print('   ', body.decode(errors='replace')[:300])
        except Exception as e:
            print('  %-15s -> %r' % (path, e))
    print('\n=== 浏览器打开 Web UI ===')
    print(URL)
    print('\n=== ComfyUI 原生 API（无需 FastAPI 代理）===')
    print('  POST %s/prompt        提交工作流 JSON' % URL)
    print('  GET  %s/history       查询任务结果' % URL)
    print('  GET  %s/view?filename=...&subfolder=...&type=output   取图' % URL)
    print('  GET  %s/object_info   节点清单与必填参数' % URL)
    print('  GET  %s/system_stats  显存/设备信息' % URL)
    print('  WS   %s/ws           前端实时进度（Cloudflare 会代理 WSS）' % URL.replace('https://', 'wss://'))
    print('\n注意：8188 没有任何鉴权，谁拿到域名都能提交任务和读输出文件，别公开分享；')
    print('      建议用 Cloudflare Access 保护，或改用下面的自有域名方案。')

# 顺带打印保留的 8010 域名，方便两边对照
try:
    old = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com',
                     open('/content/cloudflared.log', errors='replace').read())
    if old:
        print('\n>>> 原 8010 OpenAI 兼容接口域名（保持不变）:', old[0])
except Exception:
    pass

print('\n--- 自有域名方案（推荐，固定域名 + 可加 Access 鉴权）---')
print('Zero Trust -> Networks -> Tunnels -> 07ab6aa0-... -> Public Hostname -> Add a public hostname:')
print('  comfy.<你的域名>   Service: HTTP   URL: localhost:8188   <- ComfyUI Web UI / 原生 API')
print('  api.<你的域名>     Service: HTTP   URL: localhost:8010   <- OpenAI 兼容接口')
print('remotely-managed 隧道会自动拉取新配置，约 1 分钟内生效；没生效就重跑 named_tunnel_cell.py')
