# RhythmBridge · 歌单音游桥

把音乐歌单里的歌曲与舞萌 DX、中二节奏曲库对应，生成便于找歌的速查表。

## 启动

需要 Python 3.10 或更高版本，无需安装第三方包。

Windows 双击 `start.cmd`，会自动打开本地页面：

```text
http://127.0.0.1:8848
```

也可以在项目目录运行：

```powershell
python start.py
python start.py --port 8849
```

关闭启动窗口或按 Ctrl+C 停止服务。服务仅监听本机。

## v0.1 已实现

- 上传 CSV／TSV，支持 UTF-8、UTF-8 BOM、GB18030、UTF-16。
- 自动识别 `title/artist`、中文曲名／歌手列、Spotify Exportify 字段；可手动选择列。
- 保留原始标题、歌手和序号。导入上限 10 MB／10,000 条。
- 比对当前国服舞萌 DX 与中二节奏目录，曲库快照可离线使用，可手动在线更新。
- 区分确认对应、待核对候选、已禁用、当前目录未确认。
- 已核对的 24 首作品关系支持不同歌手／翻唱／钢琴／Remix；其中 1 首已禁用。
- 已核对作品带罗马音，支持 A–Z 排序、搜索、游戏／状态筛选。
- 导出当前筛选范围的 CSV、独立 HTML 速查表，打印或保存 PDF。
- 内置示例 CSV，未打包私人完整歌单。

未知曲目的罗马音暂时留空，不猜测汉字读音。v0.1 不接入歌单 URL，也不提供图片直接导出；HTML 可用浏览器另行转图。下一版的解析器调研与接入顺序见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 如何判定

确认对应需要曲名与作者一致，或命中已人工核对的作品／版本规则。只有同名、别名相同、曲名相近而作者不符时，只生成待核对候选。候选不会计入确认作品数量。

`disabled=true` 的曲目保留记录，但不计入正常收录。未确认只表示当前目录没有足够依据，不表示历史版本、日服或国际版从未收录。机台解锁状态不在本工具查询范围内。曲库更新后需要重新查询歌单。

本工具处理的是元数据，不上传歌单到第三方曲库，不保存上传文件。只有点击“更新曲库”时才请求曲库服务。

## 项目结构

```text
rhythmbridge/
  parsers.py    统一 Track 与 PlaylistProvider 接口、CSV 读取器
  catalog.py    曲库来源、快照、原子更新与失败回退
  matching.py   作品匹配、候选与罗马音
  server.py     本地网页与 API
web/            网页界面与导出
data/           初始曲库、人工核对规则
examples/       示例 CSV
tests/          读取、匹配、网络与边界测试
docs/           架构、版本路线与解析项目调研
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 数据来源

- [落雪咖啡屋曲目查询](https://maimai.lxns.net/songs)
- [舞萌 API](https://maimai.lxns.net/docs/api/maimai)
- [中二 API](https://maimai.lxns.net/docs/api/chunithm)

初始快照查询日期为 2026-10-12。作品、曲名与元数据归各权利人所有；`data/` 不因本项目分发而改变其原有权利。本版没有复制第三方歌单解析项目的源代码。


## 个人成绩与自定义图片

查询歌单后，在“带上自己的成绩”选择游戏。可在落雪账号详情生成个人 API 密钥并在此输入，或导入完整成绩 JSON。舞萌和中二分别同步，成绩按 ID 与谱面区分。刷新页面即清除成绩。

在“自定义速查图片”勾选展示内容，设置标题、主题、每页歌曲数，再生成预览。选择预览页后可下载当前 PNG，或下载全部页（浏览器可能要求允许多个下载）。曲名固定保留；罗马音、歌手、游戏、游戏曲名、曲目 ID、状态、难度、分数／达成率、FC／AP／AJ、同步时间、歌单序号可选。HTML 速查表使用相同展示字段。CSV 始终保留谱面键和完整成绩列以便核对。

图片由浏览器 Canvas 生成，HTML 报告单独保存。用户真实成绩接入尚待个人密钥联调，详见 docs/LXNS.md；后续路线见 docs/ROADMAP.md。


## 网易云／QQ 歌单链接

网易云先双击 start-netease.cmd（需 Node 22+），QQ 音乐先双击 start-qqmusic.cmd（创建独立环境安装依赖）。再启动主页面，粘贴标准歌单链接，点击“读取并匹配歌单”。两个辅助服务均只在本机读取元数据。完整性与许可证说明见 docs/ONLINE.md。


## Spotify / YouTube Music

运行 start-globalmusic.cmd 启动可选辅助服务，再导入 YouTube 公开歌单。Spotify 在本地页面填写自己的应用 Client ID，并按页面说明配置回调地址及授权。平台开发模式可能只能读取自己的或协作歌单；无法读取时使用 Exportify CSV。完整使用说明与验证边界见 docs/GLOBAL-MUSIC.md。
