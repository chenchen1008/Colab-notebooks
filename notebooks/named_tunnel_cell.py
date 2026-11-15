# 切换到自有域名：Cloudflare Named Tunnel（remotely-managed）
# token 从 Colab Secret「CF_TUNNEL_TOKEN」读取，笔记本与公开仓库里都不出现明文
# 前提：已在 Colab 左侧 Secret 面板添加该密钥，并开启「笔记本访问权限」
import os, json, base64, re, time, socket, subprocess, urllib.request
from google.colab import userdata

try:
    TOKEN = userdata.get('CF_TUNNEL_TOKEN')
except Exception as e:
    raise RuntimeError(
        '读取 Colab Secret「CF_TUNNEL_TOKEN」失败：请确认密钥已添加，且已开启本笔记本的访问权限'
    ) from e

BACKEND_PORT = 8010        # 8010=OpenAI 兼容代理；8188=ComfyUI 原生 API
KEEP_QUICK_TUNNEL = True   # 保留旧 trycloudflare.com 域名做回退，改 False 则停掉
PUBLIC_HOST = ''           # 已知域名可直接填，如 'qwen.example.com'

meta = json.loads(base64.b64decode(TOKEN))
TID = meta['t']
print('Tunnel ID:', TID, '| Account:', meta['a'][:8] + '...')
print('CNAME 目标:', TID + '.cfargotunnel.com')

# cloudflared 二进制（部署笔记本里已装过）
if not os.path.exists('/usr/local/bin/cloudflared'):
    subprocess.run(['wget', '-q',
        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',
        '-O', '/usr/local/bin/cloudflared'], check=True)
    subprocess.run(['chmod', '+x', '/usr/local/bin/cloudflared'], check=True)

def port_open(p):
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect(('127.0.0.1', p)); return True
    except Exception:
        return False
    finally:
        s.close()
print('后端监听 8010:', port_open(8010), '| 8188:', port_open(8188))

# 清掉同 token 的旧连接；按开关决定是否停用 quick tunnel
subprocess.run("ps -eo pid,args | grep '[c]loudflared tunnel.*run --token' | awk '{print $1}' | xargs -r kill", shell=True)
if not KEEP_QUICK_TUNNEL:
    subprocess.run("ps -eo pid,args | grep '[c]loudflared tunnel.*--url' | awk '{print $1}' | xargs -r kill", shell=True)
time.sleep(1)

LOG = '/content/cloudflared_named.log'
log = open(LOG, 'w')
p = subprocess.Popen(
    ['/usr/local/bin/cloudflared', 'tunnel', '--no-autoupdate',
     '--loglevel', 'debug', '--logfile', LOG, 'run', '--token', TOKEN],
    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print('Named Tunnel PID:', p.pid)

# 等待连接建立；debug 日志会打印云端下发的配置，从中自动发现 Public Hostname
txt = ''
connected = False
for _ in range(30):
    time.sleep(2)
    txt = open(LOG, errors='replace').read()
    if 'Registered tunnel connection' in txt or 'connIndex' in txt:
        connected = True
        break
print('隧道连接:', 'OK' if connected else '未确认（看下方日志）')

hosts = sorted(set(re.findall(r'hostname\W{1,8}([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,})', txt)))
hosts = [h for h in hosts if not h.endswith('.cfargotunnel.com') and 'trycloudflare.com' not in h]
if PUBLIC_HOST and PUBLIC_HOST not in hosts:
    hosts.append(PUBLIC_HOST)
print('云端 Public Hostname:', hosts or '（未发现 → 需去 Dashboard 配 Public Hostname）')

safe = [l for l in txt.splitlines() if TOKEN not in l and 'eyJhIjoi' not in l]
print('\n--- cloudflared 日志末尾 20 行（已过滤 token）---')
print('\n'.join(safe[-20:]))

for h in hosts[:3]:
    try:
        with urllib.request.urlopen('https://' + h + '/health', timeout=15) as r:
            print('验证 https://%s/health -> %s %s' % (h, r.status, r.read().decode()[:120]))
    except Exception as e:
        print('验证 https://%s/health 失败: %r' % (h, e))

print('\nDashboard: Zero Trust -> Networks -> Tunnels -> %s -> Public Hostname' % TID)
print('  Service = HTTP, URL = localhost:%d' % BACKEND_PORT)
