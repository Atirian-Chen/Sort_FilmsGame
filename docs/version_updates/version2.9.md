# version2.9

## Summary

v2.9 在豆瓣已看“电脑导入助手”的第一次导入页面新增“详细导入教程”入口，帮助第一次使用浏览器书签导入的用户直接查看完整图文说明。

## 功能细节

- 按钮文本：`详细导入教程`
- 展示位置：书签按钮说明文字下方、“拖不动？手动复制导入按钮代码”折叠栏上方。
- 目标链接：

```text
https://www.douban.com/doubanapp/dispatch?uri=%2Fgroup%2Ftopic%2F489801091&_spm_id=Mjk1Mzg4OTgz&_i=82214441c34a8be
```

- 点击后使用新标签页打开，不替换当前电影审美名单页面。
- 链接带有 `rel="noopener noreferrer"`。
- 使用独立的小按钮样式，尺寸和视觉层级低于“导入我的豆瓣已看”主按钮。
- 不增加新的事件埋点。

## 实现说明

- 在豆瓣导入相关常量区新增 `DOUBAN_IMPORT_TUTORIAL_URL`，集中保存完整教程地址。
- 在 `render_douban_bookmarklet_import()` 中按指定位置渲染外链。
- URL 在写入 HTML 属性前通过 `html.escape(..., quote=True)` 转义。
- 新增 `.import-tutorial-link-wrap` 和 `.import-tutorial-link` 样式，兼顾桌面端和移动端展示。

## 兼容性

- 不修改浏览器书签生成与导入逻辑。
- 不修改 Supabase schema。
- 不修改豆瓣电影 / 剧集读取、筛选和预编辑逻辑。
- Supabase 未配置或书签工具无法生成时，继续使用原有警告流程，不额外显示无效教程入口。

## 版本元信息

- `APP_VERSION = "v2.9"`
- `APP_RELEASE_ID = "v2.9-douban-import-tutorial-link"`
- `APP_RELEASE_NAME = "豆瓣导入详细教程入口"`
- `APP_RELEASED_AT = "2026-06-23T19:52:00+08:00"`

## 测试清单

- 教程按钮出现在指定红框位置。
- 按钮文字完整显示且不溢出。
- 桌面端和移动端均不遮挡相邻控件。
- 点击后打开完整目标 URL。
- 原应用页面不被替换。
- 外链包含 `target="_blank"` 和 `rel="noopener noreferrer"`。
- 当前版本显示为 v2.9。
- README 和版本更新文档链接有效。

## 回归命令

```bash
python -m py_compile merged_douban_ranker_v3.py import_store.py analytics.py release_history.py
git diff --check
```
