# 在【当前 Colab 笔记本】里新建一个临时 Cell，把本文件全部内容粘贴进去运行。
# 作用：用 GitHub 上最新 14 Cell 版覆盖当前 Drive 文件 —— 不换文件 ID、不换 VM、不丢 Secret 授权，
#       VM 上正在跑的 ComfyUI(8188) / FastAPI(8010) / cloudflared 进程都不受影响。
# 运行前会自动把当前笔记本下载备份到本地；覆盖完成后【立刻刷新浏览器页面】才会看到新内容。
import json, urllib.request
from google.colab import auth, files

auth.authenticate_user()   # 首次会弹一次账号授权，点允许即可
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

FILE_ID = '1x4kdEtBzIc3N7suf2R0DQPu-t396xuOv'   # 当前笔记本地址栏 /drive/<这段> 就是它
SRC = ('https://raw.githubusercontent.com/chenchen1008/Colab-notebooks/'
       'main/notebooks/Qwen-Image-2.1-Turbo-Colab.ipynb')

drive = build('drive', 'v3')

# 1) 备份当前笔记本（浏览器会下载一个 .ipynb）
try:
    old = drive.files().get_media(fileId=FILE_ID).execute()
except Exception as e:
    raise RuntimeError(
        '备份失败，已中止覆盖。请先用菜单 File → Download → Download .ipynb 手动备份'
    ) from e
open('/content/backup_before_replace.ipynb', 'wb').write(old)
files.download('/content/backup_before_replace.ipynb')
print('已备份当前笔记本:', len(old), '字节 |', len(json.loads(old)['cells']), '个 Cell')

# 2) 拉取新版
new = urllib.request.urlopen(SRC, timeout=30).read()
nb = json.loads(new)
print('新版 Cell 数:', len(nb['cells']))

# 3) 保留当前笔记本的 GPU 设置（T4），避免覆盖后掉回 CPU
cur = json.loads(old)
nb['metadata'] = {**cur.get('metadata', {}), **nb.get('metadata', {})}
for k in ('colab', 'accelerator'):
    if k in cur.get('metadata', {}):
        nb['metadata'][k] = cur['metadata'][k]

# 4) 原地覆盖同一个 Drive 文件
payload = json.dumps(nb, ensure_ascii=False).encode('utf-8')
drive.files().update(
    fileId=FILE_ID,
    media_body=MediaInMemoryUpload(payload, mimetype='application/x-ipynb+json', resumable=False),
).execute()
print('✅ 已覆盖同一 Drive 文件（file ID 不变）')
print('>>> 现在立刻按 Ctrl / Cmd + R 刷新 Colab 页面，看到 14 个 Cell 即完成')
print('>>> 刷新只重载页面，不会重启 VM；刷新前不要在页面上编辑任何 Cell，避免旧内容被自动保存写回')

# 备选（不想用 Drive API 时）：
#   ① 浏览器控制台版：notebooks/replace_colab_notebook.js（已验证可用，含 localStorage 备份/恢复）
#   ② Google Drive 网页打开该文件 → 管理版本 → 上传新版本 → 回 Colab 刷新
#   ③ 直接打开 https://colab.research.google.com/github/chenchen1008/Colab-notebooks/blob/main/notebooks/Qwen-Image-2.1-Turbo-Colab.ipynb
#      这是【新笔记本】：Secret 要重新授权、VM 重置、14GB 模型要重下，代价最大
