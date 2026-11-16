/* 在 Colab 页面的浏览器上下文执行（控制台 / 自动化 JS）。
 * 把 GitHub 上最新 14 Cell 版覆盖到【当前打开的笔记本】，保留文件 ID、GPU 设置与运行时。
 * 已在 Colab 实际验证：window.colab.global.notebookModel.fillFromJson() + performSave() 可用。
 * 执行前自动把当前 16 个 Cell 备份进 localStorage；执行后刷新页面生效。
 * 想撤销：调用 window.wbRestoreNotebook() 再刷新页面。
 */
(async () => {
  const SRC = 'https://raw.githubusercontent.com/chenchen1008/Colab-notebooks/main/notebooks/Qwen-Image-2.1-Turbo-Colab.ipynb';
  const KEY = 'wb_colab_backup_20261115';
  const m = window.colab && window.colab.global && window.colab.global.notebookModel;
  if (!m) throw new Error('没找到 notebookModel：请确认当前标签页是 Colab 笔记本，不是 Colab 首页');

  // 1) 备份当前内容（只存源码与类型，足够恢复）
  const backup = {
    title: String(m.title),
    fileId: m.fileId,
    metadata: Object.assign({}, m.metadata),
    cells: Array.from(m.cells).map(c => ({
      cell_type: c.getType() === 'text' ? 'markdown' : 'code',
      metadata: {},
      source: c.getText(),
    })),
  };
  localStorage.setItem(KEY, JSON.stringify(backup));
  console.log('已备份', backup.cells.length, '个 Cell 到 localStorage[' + KEY + ']');

  // 2) 拉取新版并统一 source 为字符串、清空输出
  const res = await fetch(SRC, { cache: 'no-store' });
  if (!res.ok) throw new Error('拉取新版失败: HTTP ' + res.status);
  const nb = await res.json();
  const merged = Object.assign({}, nb, {
    metadata: Object.assign({}, nb.metadata, {
      accelerator: m.metadata.accelerator,
      colab: m.metadata.colab,
    }),
  });
  merged.cells = merged.cells.map(c => Object.assign({}, c, {
    source: Array.isArray(c.source) ? c.source.join('') : c.source,
    outputs: [],
    execution_count: null,
  }));

  // 3) 全量替换并强制保存回原 Drive 文件
  await m.fillFromJson(merged, { unsafeSkipAuthorshipUpdate: true });
  await m.performSave({ force: true });
  console.log('✅ 覆盖完成，当前 Cell 数:', m.cells.length,
              '| 类型:', Array.from(m.cells).map(c => c.getType()).join(','));
  console.log('>>> 现在按 Ctrl / Cmd + R 刷新页面，看到 14 个 Cell 即生效');
  console.log('>>> 刷新不重启 VM，ComfyUI / 8010 / cloudflared 继续运行');

  // 4) 撤销入口
  window.wbRestoreNotebook = async () => {
    const raw = localStorage.getItem(KEY);
    if (!raw) throw new Error('没有找到备份');
    const old = JSON.parse(raw);
    await m.fillFromJson(Object.assign({}, old, { nbformat: 4, nbformat_minor: 5 }),
                         { unsafeSkipAuthorshipUpdate: true });
    await m.performSave({ force: true });
    console.log('✅ 已恢复备份的', old.cells.length, '个 Cell，刷新页面生效');
  };
  return { cells: m.cells.length, backupKey: KEY, restore: 'window.wbRestoreNotebook()' };
})();
