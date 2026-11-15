# 一键修复 502 —— 粘贴到 Colab 任意代码单元格运行，无需上传文件、无需联网下载脚本
# 作用：诊断端口 → 补依赖 → 拉起 ComfyUI(8188) → 写入 /content/qwen_api.py → 启动代理(8010) → 健康检查
# cloudflared 隧道进程保持不动，原公网域名不变；后端恢复后 502 自动消失
import os, sys, time, socket, subprocess, base64, urllib.request, json

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

print('诊断: 8188(ComfyUI)=', port_open(8188), '| 8010(FastAPI)=', port_open(8010))
print('--- /content/comfyui.log 末尾 30 行 ---')
print(tail('/content/comfyui.log'))

# 1) 补依赖：ComfyUI 首次启动超时，多半是缺 gguf
print('\n[1/5] 补装 gguf / fastapi / uvicorn / requests ...')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                'gguf', 'fastapi', 'uvicorn', 'requests'], check=False)
r = '/content/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt'
if os.path.exists(r):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', r], check=False)

# 2) 拉起 ComfyUI (8188)
print('\n[2/5] 检查 ComfyUI ...')
if port_open(8188):
    print('✅ ComfyUI 已在运行')
else:
    subprocess.run("ps -eo pid,args | grep '[m]ain.py --listen' | awk '{print $1}' | xargs -r kill", shell=True)
    time.sleep(1)
    log = open('/content/comfyui.log', 'a')
    p = subprocess.Popen([sys.executable, 'main.py', '--listen', '0.0.0.0', '--port', '8188'],
                         cwd='/content/ComfyUI', stdout=log, stderr=log, start_new_session=True)
    print('启动 ComfyUI PID:', p.pid)
    for _ in range(60):
        time.sleep(3)
        if port_open(8188):
            break
    if port_open(8188):
        print('✅ ComfyUI 已就绪: http://127.0.0.1:8188')
    else:
        print('❌ ComfyUI 失败，日志末尾 40 行:\n' + tail('/content/comfyui.log', 40))
if port_open(8188):
    try:
        info = json.load(urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=15))
        print('   UNETLoaderGGUF 节点已注册:', 'UNETLoaderGGUF' in info)
    except Exception as e:
        print('   object_info 读取失败:', repr(e))

# 3) 写入 /content/qwen_api.py —— 核心修复：旧笔记本从未把文件落盘
#    下面 API_B64 就是完整的 qwen_api.py 源码（base64），内联以做到零网络依赖
print('\n[3/5] 写入 /content/qwen_api.py ...')
API_B64 = (
    "IyBPcGVuQUkg5YW85a655Luj55CG77ya5oqKIENvbWZ5VUkg5bel5L2c5rWB5YyF6KOF5oiQIC92MS9pbWFnZXMvZ2VuZXJhdGlv"
    "bnMKIyDoi6UgQ29tZnlVSS1HR1VGIOiKgueCueexu+WQjeS4jeWQjO+8jOaUuSBVTkVUX0NMQVNTIOWNs+WPrwpmcm9tIGZhc3Rh"
    "cGkgaW1wb3J0IEZhc3RBUEkKZnJvbSBweWRhbnRpYyBpbXBvcnQgQmFzZU1vZGVsCmltcG9ydCByZXF1ZXN0cywgYmFzZTY0LCB1"
    "dWlkLCB0aW1lLCB1dmljb3JuLCB0cmFjZWJhY2sKCmFwcCA9IEZhc3RBUEkodGl0bGU9J1F3ZW4tSW1hZ2UtMi4xLVR1cmJvIHBy"
    "b3h5JykKQ09NRlkgPSAnaHR0cDovLzEyNy4wLjAuMTo4MTg4JwpVTkVUID0gJ3F3ZW4taW1hZ2UtMi4xLXR1cmJvLVE0X0tfTS5n"
    "Z3VmJwpDTElQID0gJ3F3ZW4zdmxfOGJfaW50OF9jb252cm90LnNhZmV0ZW5zb3JzJwpWQUUgPSAncXdlbl9pbWFnZV8yLjFfdmFl"
    "X2JmMTYuc2FmZXRlbnNvcnMnClVORVRfQ0xBU1MgPSAnVU5FVExvYWRlckdHVUYnCgpjbGFzcyBJbWFnZUdlblJlcXVlc3QoQmFz"
    "ZU1vZGVsKToKICAgIHByb21wdDogc3RyCiAgICBtb2RlbDogc3RyID0gVU5FVAogICAgd2lkdGg6IGludCA9IDEwMjQKICAgIGhl"
    "aWdodDogaW50ID0gMTAyNAogICAgc3RlcHM6IGludCA9IDgKICAgIHNlZWQ6IGludCA9IC0xCiAgICBjZmc6IGZsb2F0ID0gMS4w"
    "CgpAYXBwLmdldCgnLycpCmRlZiByb290KCk6CiAgICByZXR1cm4geydzdGF0dXMnOiAnb2snLCAnYmFja2VuZCc6IENPTUZZLCAn"
    "ZW5kcG9pbnQnOiAnL3YxL2ltYWdlcy9nZW5lcmF0aW9ucyd9CgpAYXBwLmdldCgnL2hlYWx0aCcpCmRlZiBoZWFsdGgoKToKICAg"
    "IHRyeToKICAgICAgICByZXF1ZXN0cy5nZXQoQ09NRlkgKyAnL3N5c3RlbV9zdGF0cycsIHRpbWVvdXQ9NSkucmFpc2VfZm9yX3N0"
    "YXR1cygpCiAgICAgICAgcmV0dXJuIHsnb2snOiBUcnVlLCAnY29tZnl1aSc6ICd1cCd9CiAgICBleGNlcHQgRXhjZXB0aW9uIGFz"
    "IGU6CiAgICAgICAgcmV0dXJuIHsnb2snOiBGYWxzZSwgJ2NvbWZ5dWknOiByZXByKGUpfQoKQGFwcC5nZXQoJy92MS9tb2RlbHMn"
    "KQpkZWYgbW9kZWxzKCk6CiAgICByZXR1cm4geydvYmplY3QnOiAnbGlzdCcsICdkYXRhJzogW3snaWQnOiBVTkVULCAnb2JqZWN0"
    "JzogJ21vZGVsJ31dfQoKZGVmIGJ1aWxkX3dvcmtmbG93KHJlcTogSW1hZ2VHZW5SZXF1ZXN0KToKICAgIHNlZWQgPSByZXEuc2Vl"
    "ZCBpZiByZXEuc2VlZCBhbmQgcmVxLnNlZWQgPj0gMCBlbHNlIHV1aWQudXVpZDQoKS5pbnQgPj4gNjQKICAgIHJldHVybiB7CiAg"
    "ICAgICAgJzEnOiB7J2lucHV0cyc6IHsndW5ldF9uYW1lJzogcmVxLm1vZGVsfSwgJ2NsYXNzX3R5cGUnOiBVTkVUX0NMQVNTfSwK"
    "ICAgICAgICAnMic6IHsnaW5wdXRzJzogeydjbGlwX25hbWUnOiBDTElQLCAndHlwZSc6ICdxd2VuX2ltYWdlJ30sICdjbGFzc190"
    "eXBlJzogJ0NMSVBMb2FkZXInfSwKICAgICAgICAnMyc6IHsnaW5wdXRzJzogeyd2YWVfbmFtZSc6IFZBRX0sICdjbGFzc190eXBl"
    "JzogJ1ZBRUxvYWRlcid9LAogICAgICAgICc0JzogeydpbnB1dHMnOiB7J3dpZHRoJzogcmVxLndpZHRoLCAnaGVpZ2h0JzogcmVx"
    "LmhlaWdodCwgJ2JhdGNoX3NpemUnOiAxfSwgJ2NsYXNzX3R5cGUnOiAnRW1wdHlMYXRlbnRJbWFnZSd9LAogICAgICAgICc1Jzog"
    "eydpbnB1dHMnOiB7J21vZGVsJzogWycxJywgMF0sICdwb3NpdGl2ZSc6IFsnMicsIDBdLCAnbmVnYXRpdmUnOiBbJzInLCAwXSwg"
    "J2xhdGVudF9pbWFnZSc6IFsnNCcsIDBdLAogICAgICAgICAgICAgICAgJ3NlZWQnOiBpbnQoc2VlZCksICdzdGVwcyc6IHJlcS5z"
    "dGVwcywgJ2NmZyc6IHJlcS5jZmcsCiAgICAgICAgICAgICAgICAnc2FtcGxlcl9uYW1lJzogJ2V1bGVyJywgJ3NjaGVkdWxlcic6"
    "ICdub3JtYWwnLCAnZGVub2lzZSc6IDEuMH0sICdjbGFzc190eXBlJzogJ0tTYW1wbGVyJ30sCiAgICAgICAgJzYnOiB7J2lucHV0"
    "cyc6IHsnc2FtcGxlcyc6IFsnNScsIDBdLCAndmFlJzogWyczJywgMF19LCAnY2xhc3NfdHlwZSc6ICdWQUVEZWNvZGUnfSwKICAg"
    "ICAgICAnNyc6IHsnaW5wdXRzJzogeydpbWFnZXMnOiBbJzYnLCAwXSwgJ2ZpbGVuYW1lX3ByZWZpeCc6ICdxd2VuX2NvbGFiJ30s"
    "ICdjbGFzc190eXBlJzogJ1NhdmVJbWFnZSd9LAogICAgfQoKQGFwcC5wb3N0KCcvdjEvaW1hZ2VzL2dlbmVyYXRpb25zJykKZGVm"
    "IGdlbmVyYXRlKHJlcTogSW1hZ2VHZW5SZXF1ZXN0KToKICAgIHRyeToKICAgICAgICByID0gcmVxdWVzdHMucG9zdChDT01GWSAr"
    "ICcvcHJvbXB0JywganNvbj17J3Byb21wdCc6IGJ1aWxkX3dvcmtmbG93KHJlcSl9LCB0aW1lb3V0PTMwKQogICAgICAgIGlmIHIu"
    "c3RhdHVzX2NvZGUgIT0gMjAwOgogICAgICAgICAgICByZXR1cm4geydlcnJvcic6ICdjb21meXVpIC9wcm9tcHQgcmVqZWN0ZWQn"
    "LCAnZGV0YWlsJzogci50ZXh0WzoxMDAwXX0KICAgICAgICBwaWQgPSByLmpzb24oKVsncHJvbXB0X2lkJ10KICAgICAgICBvdXRz"
    "ID0gTm9uZQogICAgICAgIGZvciBfIGluIHJhbmdlKDE4MCk6CiAgICAgICAgICAgIHRpbWUuc2xlZXAoMikKICAgICAgICAgICAg"
    "aCA9IHJlcXVlc3RzLmdldChDT01GWSArIGYnL2hpc3Rvcnkve3BpZH0nLCB0aW1lb3V0PTEwKS5qc29uKCkKICAgICAgICAgICAg"
    "aWYgcGlkIGluIGggYW5kICdvdXRwdXRzJyBpbiBoW3BpZF06CiAgICAgICAgICAgICAgICBvdXRzID0gaFtwaWRdWydvdXRwdXRz"
    "J10KICAgICAgICAgICAgICAgIGJyZWFrCiAgICAgICAgaWYgb3V0cyBpcyBOb25lOgogICAgICAgICAgICByZXR1cm4geydlcnJv"
    "cic6ICdnZW5lcmF0aW9uIHRpbWVvdXQnfQogICAgICAgIGltYWdlcyA9IFtdCiAgICAgICAgZm9yIG5vZGVfaWQsIG91dCBpbiBv"
    "dXRzLml0ZW1zKCk6CiAgICAgICAgICAgIGZvciBpbWcgaW4gb3V0LmdldCgnaW1hZ2VzJywgW10pOgogICAgICAgICAgICAgICAg"
    "ZGF0YSA9IHJlcXVlc3RzLmdldChDT01GWSArICcvdmlldycsCiAgICAgICAgICAgICAgICAgICAgcGFyYW1zPXsnZmlsZW5hbWUn"
    "OiBpbWdbJ2ZpbGVuYW1lJ10sICdzdWJmb2xkZXInOiBpbWcuZ2V0KCdzdWJmb2xkZXInLCAnJyksICd0eXBlJzogJ291dHB1dCd9"
    "LAogICAgICAgICAgICAgICAgICAgIHRpbWVvdXQ9NjApLmNvbnRlbnQKICAgICAgICAgICAgICAgIGltYWdlcy5hcHBlbmQoeydi"
    "NjRfanNvbic6IGJhc2U2NC5iNjRlbmNvZGUoZGF0YSkuZGVjb2RlKCdhc2NpaScpfSkKICAgICAgICByZXR1cm4geydjcmVhdGVk"
    "JzogaW50KHRpbWUudGltZSgpKSwgJ2RhdGEnOiBpbWFnZXN9CiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHJldHVybiB7"
    "J2Vycm9yJzogJ3Byb3h5IGV4Y2VwdGlvbicsICdkZXRhaWwnOiB0cmFjZWJhY2suZm9ybWF0X2V4YygpWy0xNTAwOl19CgppZiBf"
    "X25hbWVfXyA9PSAnX19tYWluX18nOgogICAgcHJpbnQoJ3F3ZW5fYXBpOiBsaXN0ZW5pbmcgb24gMC4wLjAuMDo4MDEwIC0+ICcg"
    "KyBDT01GWSwgZmx1c2g9VHJ1ZSkKICAgIHV2aWNvcm4ucnVuKGFwcCwgaG9zdD0nMC4wLjAuMCcsIHBvcnQ9ODAxMCwgbG9nX2xl"
    "dmVsPSdpbmZvJykK"
)
api_code = base64.b64decode(API_B64).decode('utf-8')
with open('/content/qwen_api.py', 'w', encoding='utf-8') as f:
    f.write(api_code)
print('✅ 已写入 /content/qwen_api.py:', len(api_code), '字节')

# 4) 启动 FastAPI 代理 (8010)
print('\n[4/5] 启动 FastAPI 代理 ...')
subprocess.run("ps -eo pid,args | grep '[q]wen_api.py' | awk '{print $1}' | xargs -r kill", shell=True)
time.sleep(1)
api = subprocess.Popen([sys.executable, 'qwen_api.py'], cwd='/content',
                       stdout=open('/content/qwen_api.log', 'w'), stderr=subprocess.STDOUT,
                       start_new_session=True)
print('FastAPI PID:', api.pid)
for _ in range(40):
    if port_open(8010):
        break
    time.sleep(2)
if port_open(8010):
    print('✅ 8010 已监听')
else:
    print('❌ 8010 未起，日志:\n' + tail('/content/qwen_api.log', 40))

# 5) 健康检查
print('\n[5/5] 健康检查 ...')
if port_open(8010):
    try:
        print('   /health =', urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=10).read().decode())
    except Exception as e:
        print('   /health 失败:', repr(e))
n = subprocess.run("ps -eo args | grep -c '[c]loudflared tunnel'", shell=True,
                   capture_output=True, text=True).stdout.strip()
print('   cloudflared 隧道进程数:', n, '(>0 表示原域名保留)')
print('\n>>> 刷新原域名: https://ensemble-sql-doe-reserves.trycloudflare.com')
print('>>> 接口: https://ensemble-sql-doe-reserves.trycloudflare.com/v1/images/generations')
