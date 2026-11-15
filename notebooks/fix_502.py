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
nb_url = (
    "https://raw.githubusercontent.com/chenchen1008/Colab-notebooks/"
    "main/notebooks/Qwen-Image-2.1-Turbo-Colab.ipynb"
)
nb = json.load(urllib.request.urlopen(nb_url, timeout=30))
src = next(
    "".join(c["source"])
    for c in nb["cells"]
    if "".join(c["source"]).startswith("%%writefile /content/qwen_api.py")
)
api_code = src.split("\n", 1)[1]
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
