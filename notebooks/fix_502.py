"""Colab 会话内一键修复脚本。

502 根因：笔记本里"写 qwen_api.py"那一格其实只定义了 app 并直接 uvicorn.run()，
既触发 asyncio 事件循环冲突，也从未把 /content/qwen_api.py 写入磁盘；
后续启动代理去运行一个不存在的文件，8010 从未监听 → cloudflared 隧道后端为空 → 502。
另：ComfyUI(8188) 首次启动也可能因缺少 gguf 等依赖而失败。

本脚本按 诊断 → 补依赖 → 拉起 ComfyUI(8188) → 写 qwen_api.py → 启动 8010 → 健康检查 执行。
cloudflared 隧道进程保持不动，因此原公网域名不变，后端恢复后 502 自动消失。
"""
import os
import sys
import time
import socket
import subprocess
import json
import urllib.request


def port_open(p, host="127.0.0.1"):
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect((host, p))
        return True
    except Exception:
        return False
    finally:
        s.close()


def tail(path, n=40):
    if not os.path.exists(path):
        return "(无日志)"
    with open(path, errors="replace") as f:
        return "\n".join(f.read().splitlines()[-n:])


print("=" * 60)
print("诊断: 8188 (ComfyUI) =", port_open(8188), "| 8010 (FastAPI) =", port_open(8010))
print("--- /content/comfyui.log 末尾 30 行 ---")
print(tail("/content/comfyui.log", 30))
print("=" * 60)

# ---------- 1) 补依赖 ----------
print("\n[1/5] 补装 gguf / fastapi / uvicorn / requests ...")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "gguf", "fastapi", "uvicorn", "requests"],
    check=False,
)
gguf_req = "/content/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt"
if os.path.exists(gguf_req):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", gguf_req], check=False)

# ---------- 2) 拉起 ComfyUI ----------
print("\n[2/5] 检查 ComfyUI (8188) ...")
if port_open(8188):
    print("✅ ComfyUI 已在运行")
else:
    subprocess.run(
        "ps -eo pid,args | grep '[m]ain.py --listen' | awk '{print $1}' | xargs -r kill",
        shell=True,
    )
    time.sleep(1)
    log = open("/content/comfyui.log", "a")
    p = subprocess.Popen(
        [sys.executable, "main.py", "--listen", "0.0.0.0", "--port", "8188"],
        cwd="/content/ComfyUI",
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    print("启动 ComfyUI PID:", p.pid)
    for _ in range(60):
        time.sleep(3)
        if port_open(8188):
            break
    if port_open(8188):
        print("✅ ComfyUI 已就绪: http://127.0.0.1:8188")
    else:
        print("❌ ComfyUI 仍未就绪，日志末尾 40 行:")
        print(tail("/content/comfyui.log", 40))

if port_open(8188):
    try:
        info = json.load(urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=15))
        print("   UNETLoaderGGUF 节点已注册:", "UNETLoaderGGUF" in info)
    except Exception as e:
        print("   object_info 读取失败:", repr(e))

# ---------- 3) 写入 qwen_api.py（核心修复） ----------
print("\n[3/5] 写入 /content/qwen_api.py ...")
# 代理源码已内联（base64），不再依赖二次网络拉取
import base64
api_code = base64.b64decode(
    "IyBPcGVuQUkg5YW85a655Luj55CG77ya5oqKIENvbWZ5VUkg5bel5L2c5rWB5YyF6KOF5oiQIC92MS9pbWFnZXMvZ2VuZXJhdGlvbnMKIyDoi6UgQ29tZnlVSS1HR1VGIOiKgueCueexu+WQjeS4jeWQjO+8jOaUuSBVTkVUX0NMQVNTIOWNs+WPrwpmcm9tIGZhc3RhcGkgaW1wb3J0IEZhc3RBUEkKZnJvbSBweWRhbnRpYyBpbXBvcnQgQmFzZU1vZGVsCmltcG9ydCByZXF1ZXN0cywgYmFzZTY0LCB1dWlkLCB0aW1lLCB1dmljb3JuLCB0cmFjZWJhY2sKCmFwcCA9IEZhc3RBUEkodGl0bGU9J1F3ZW4tSW1hZ2UtMi4xLVR1cmJvIHByb3h5JykKQ09NRlkgPSAnaHR0cDovLzEyNy4wLjAuMTo4MTg4JwpVTkVUID0gJ3F3ZW4taW1hZ2UtMi4xLXR1cmJvLVE0X0tfTS5nZ3VmJwpDTElQID0gJ3F3ZW4zdmxfOGJfaW50OF9jb252cm90LnNhZmV0ZW5zb3JzJwpWQUUgPSAncXdlbl9pbWFnZV8yLjFfdmFlX2JmMTYuc2FmZXRlbnNvcnMnClVORVRfQ0xBU1MgPSAnVU5FVExvYWRlckdHVUYnCgpjbGFzcyBJbWFnZUdlblJlcXVlc3QoQmFzZU1vZGVsKToKICAgIHByb21wdDogc3RyCiAgICBtb2RlbDogc3RyID0gVU5FVAogICAgd2lkdGg6IGludCA9IDEwMjQKICAgIGhlaWdodDogaW50ID0gMTAyNAogICAgc3RlcHM6IGludCA9IDgKICAgIHNlZWQ6IGludCA9IC0xCiAgICBjZmc6IGZsb2F0ID0gMS4wCgpAYXBwLmdldCgnLycpCmRlZiByb290KCk6CiAgICByZXR1cm4geydzdGF0dXMnOiAnb2snLCAnYmFja2VuZCc6IENPTUZZLCAnZW5kcG9pbnQnOiAnL3YxL2ltYWdlcy9nZW5lcmF0aW9ucyd9CgpAYXBwLmdldCgnL2hlYWx0aCcpCmRlZiBoZWFsdGgoKToKICAgIHRyeToKICAgICAgICByZXF1ZXN0cy5nZXQoQ09NRlkgKyAnL3N5c3RlbV9zdGF0cycsIHRpbWVvdXQ9NSkucmFpc2VfZm9yX3N0YXR1cygpCiAgICAgICAgcmV0dXJuIHsnb2snOiBUcnVlLCAnY29tZnl1aSc6ICd1cCd9CiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGU6CiAgICAgICAgcmV0dXJuIHsnb2snOiBGYWxzZSwgJ2NvbWZ5dWknOiByZXByKGUpfQoKQGFwcC5nZXQoJy92MS9tb2RlbHMnKQpkZWYgbW9kZWxzKCk6CiAgICByZXR1cm4geydvYmplY3QnOiAnbGlzdCcsICdkYXRhJzogW3snaWQnOiBVTkVULCAnb2JqZWN0JzogJ21vZGVsJ31dfQoKZGVmIGJ1aWxkX3dvcmtmbG93KHJlcTogSW1hZ2VHZW5SZXF1ZXN0KToKICAgIHNlZWQgPSByZXEuc2VlZCBpZiByZXEuc2VlZCBhbmQgcmVxLnNlZWQgPj0gMCBlbHNlIHV1aWQudXVpZDQoKS5pbnQgPj4gNjQKICAgIHJldHVybiB7CiAgICAgICAgJzEnOiB7J2lucHV0cyc6IHsndW5ldF9uYW1lJzogcmVxLm1vZGVsfSwgJ2NsYXNzX3R5cGUnOiBVTkVUX0NMQVNTfSwKICAgICAgICAnMic6IHsnaW5wdXRzJzogeydjbGlwX25hbWUnOiBDTElQLCAndHlwZSc6ICdxd2VuX2ltYWdlJ30sICdjbGFzc190eXBlJzogJ0NMSVBMb2FkZXInfSwKICAgICAgICAnMyc6IHsnaW5wdXRzJzogeyd2YWVfbmFtZSc6IFZBRX0sICdjbGFzc190eXBlJzogJ1ZBRUxvYWRlcid9LAogICAgICAgICc0JzogeydpbnB1dHMnOiB7J3dpZHRoJzogcmVxLndpZHRoLCAnaGVpZ2h0JzogcmVxLmhlaWdodCwgJ2JhdGNoX3NpemUnOiAxfSwgJ2NsYXNzX3R5cGUnOiAnRW1wdHlMYXRlbnRJbWFnZSd9LAogICAgICAgICc1JzogeydpbnB1dHMnOiB7J21vZGVsJzogWycxJywgMF0sICdwb3NpdGl2ZSc6IFsnMicsIDBdLCAnbmVnYXRpdmUnOiBbJzInLCAwXSwgJ2xhdGVudF9pbWFnZSc6IFsnNCcsIDBdLAogICAgICAgICAgICAgICAgJ3NlZWQnOiBpbnQoc2VlZCksICdzdGVwcyc6IHJlcS5zdGVwcywgJ2NmZyc6IHJlcS5jZmcsCiAgICAgICAgICAgICAgICAnc2FtcGxlcl9uYW1lJzogJ2V1bGVyJywgJ3NjaGVkdWxlcic6ICdub3JtYWwnLCAnZGVub2lzZSc6IDEuMH0sICdjbGFzc190eXBlJzogJ0tTYW1wbGVyJ30sCiAgICAgICAgJzYnOiB7J2lucHV0cyc6IHsnc2FtcGxlcyc6IFsnNScsIDBdLCAndmFlJzogWyczJywgMF19LCAnY2xhc3NfdHlwZSc6ICdWQUVEZWNvZGUnfSwKICAgICAgICAnNyc6IHsnaW5wdXRzJzogeydpbWFnZXMnOiBbJzYnLCAwXSwgJ2ZpbGVuYW1lX3ByZWZpeCc6ICdxd2VuX2NvbGFiJ30sICdjbGFzc190eXBlJzogJ1NhdmVJbWFnZSd9LAogICAgfQoKQGFwcC5wb3N0KCcvdjEvaW1hZ2VzL2dlbmVyYXRpb25zJykKZGVmIGdlbmVyYXRlKHJlcTogSW1hZ2VHZW5SZXF1ZXN0KToKICAgIHRyeToKICAgICAgICByID0gcmVxdWVzdHMucG9zdChDT01GWSArICcvcHJvbXB0JywganNvbj17J3Byb21wdCc6IGJ1aWxkX3dvcmtmbG93KHJlcSl9LCB0aW1lb3V0PTMwKQogICAgICAgIGlmIHIuc3RhdHVzX2NvZGUgIT0gMjAwOgogICAgICAgICAgICByZXR1cm4geydlcnJvcic6ICdjb21meXVpIC9wcm9tcHQgcmVqZWN0ZWQnLCAnZGV0YWlsJzogci50ZXh0WzoxMDAwXX0KICAgICAgICBwaWQgPSByLmpzb24oKVsncHJvbXB0X2lkJ10KICAgICAgICBvdXRzID0gTm9uZQogICAgICAgIGZvciBfIGluIHJhbmdlKDE4MCk6CiAgICAgICAgICAgIHRpbWUuc2xlZXAoMikKICAgICAgICAgICAgaCA9IHJlcXVlc3RzLmdldChDT01GWSArIGYnL2hpc3Rvcnkve3BpZH0nLCB0aW1lb3V0PTEwKS5qc29uKCkKICAgICAgICAgICAgaWYgcGlkIGluIGggYW5kICdvdXRwdXRzJyBpbiBoW3BpZF06CiAgICAgICAgICAgICAgICBvdXRzID0gaFtwaWRdWydvdXRwdXRzJ10KICAgICAgICAgICAgICAgIGJyZWFrCiAgICAgICAgaWYgb3V0cyBpcyBOb25lOgogICAgICAgICAgICByZXR1cm4geydlcnJvcic6ICdnZW5lcmF0aW9uIHRpbWVvdXQnfQogICAgICAgIGltYWdlcyA9IFtdCiAgICAgICAgZm9yIG5vZGVfaWQsIG91dCBpbiBvdXRzLml0ZW1zKCk6CiAgICAgICAgICAgIGZvciBpbWcgaW4gb3V0LmdldCgnaW1hZ2VzJywgW10pOgogICAgICAgICAgICAgICAgZGF0YSA9IHJlcXVlc3RzLmdldChDT01GWSArICcvdmlldycsCiAgICAgICAgICAgICAgICAgICAgcGFyYW1zPXsnZmlsZW5hbWUnOiBpbWdbJ2ZpbGVuYW1lJ10sICdzdWJmb2xkZXInOiBpbWcuZ2V0KCdzdWJmb2xkZXInLCAnJyksICd0eXBlJzogJ291dHB1dCd9LAogICAgICAgICAgICAgICAgICAgIHRpbWVvdXQ9NjApLmNvbnRlbnQKICAgICAgICAgICAgICAgIGltYWdlcy5hcHBlbmQoeydiNjRfanNvbic6IGJhc2U2NC5iNjRlbmNvZGUoZGF0YSkuZGVjb2RlKCdhc2NpaScpfSkKICAgICAgICByZXR1cm4geydjcmVhdGVkJzogaW50KHRpbWUudGltZSgpKSwgJ2RhdGEnOiBpbWFnZXN9CiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHJldHVybiB7J2Vycm9yJzogJ3Byb3h5IGV4Y2VwdGlvbicsICdkZXRhaWwnOiB0cmFjZWJhY2suZm9ybWF0X2V4YygpWy0xNTAwOl19CgppZiBfX25hbWVfXyA9PSAnX19tYWluX18nOgogICAgcHJpbnQoJ3F3ZW5fYXBpOiBsaXN0ZW5pbmcgb24gMC4wLjAuMDo4MDEwIC0+ICcgKyBDT01GWSwgZmx1c2g9VHJ1ZSkKICAgIHV2aWNvcm4ucnVuKGFwcCwgaG9zdD0nMC4wLjAuMCcsIHBvcnQ9ODAxMCwgbG9nX2xldmVsPSdpbmZvJykK"
).decode("utf-8")
with open("/content/qwen_api.py", "w", encoding="utf-8") as f:
    f.write(api_code)
print("✅ 已写入", len(api_code), "字节（来源：GitHub 修复版笔记本）")

# ---------- 4) 启动 8010 ----------
print("\n[4/5] 启动 FastAPI 代理 (8010) ...")
subprocess.run(
    "ps -eo pid,args | grep '[q]wen_api.py' | awk '{print $1}' | xargs -r kill",
    shell=True,
)
time.sleep(1)
api = subprocess.Popen(
    [sys.executable, "qwen_api.py"],
    cwd="/content",
    stdout=open("/content/qwen_api.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
print("FastAPI PID:", api.pid)
for _ in range(40):
    if port_open(8010):
        break
    time.sleep(2)
if port_open(8010):
    print("✅ 8010 已监听")
else:
    print("❌ 8010 未监听，日志:", tail("/content/qwen_api.log", 40))

# ---------- 5) 健康检查 ----------
print("\n[5/5] 健康检查 ...")
if port_open(8010):
    try:
        h = urllib.request.urlopen("http://127.0.0.1:8010/health", timeout=10).read().decode()
        print("   /health =", h)
    except Exception as e:
        print("   /health 失败:", repr(e))

n = subprocess.run(
    "ps -eo args | grep -c '[c]loudflared tunnel'", shell=True, capture_output=True, text=True
).stdout.strip()
print("   cloudflared 隧道进程数:", n, "(>0 表示原域名保留)")

print("\n" + "=" * 60)
if port_open(8010) and port_open(8188):
    print("✅ 后端已恢复，刷新原公网域名即可（502 应消失）")
    print("   https://ensemble-sql-doe-reserves.trycloudflare.com")
    print("   https://ensemble-sql-doe-reserves.trycloudflare.com/v1/images/generations")
else:
    print("⚠️ 仍有端口未就绪，请把上面的日志贴回来继续排查")
print("=" * 60)
