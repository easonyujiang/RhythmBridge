# Spotify / YouTube Music

## 启动

先运行 start-globalmusic.cmd，创建独立 .venv 并安装 requirements-lock.txt 中的依赖。测试环境 Windows / Python 3.12。辅助服务端口 8852，仅监听本机。核心仍可独立使用 CSV。

YouTube Music：粘贴公开歌单标准链接，如 https://music.youtube.com/playlist?list=... 或 YouTube playlist / 带 list 参数的 watch 链接。通过 ytmusicapi 1.12.3 读取元数据和内部分页，不下载音频。没有提供登录材料，私密歌单当前使用 CSV。trackCount 与读取列表必须一致，否则拒绝部分结果；动态电台缺少可核对总数，也拒绝导入。缺失歌手保留为空并由 Matcher 判为候选。

Spotify：在 https://developer.spotify.com/dashboard 创建应用，将页面显示的重定向地址（默认 http://127.0.0.1:8848/spotify/callback）添加到应用配置。在本地填写 Client ID，点击授权，完成后返回原页刷新授权状态，再导入标准 Spotify 歌单链接。端口改变时更新应用重定向地址。只申请 playlist-read-private 和 playlist-read-collaborative，不需要 Client Secret。

官方 PKCE / S256 与随机 state，授权状态十分钟过期且仅能消费一次。访问令牌和刷新令牌仅保存在本地服务内存，不写文件，不打印日志，不返回浏览器结果；关闭服务或点击清除即移除。刷新页面不会清除服务内存里的授权。清除本地授权不会撤销 Spotify 账号里的应用权限，撤销需在账号应用管理完成。

读取使用 Spotipy 2.26.0 的当前 /playlists/{id}/items 接口。每页 50 条，核对 offset、total、下一页状态以及读取前后的 snapshot_id；顺序、重复和本地歌曲元数据保留。播客不是歌曲，明确报告排除数量；无法读取的歌曲拒绝导入。API 请求源固定为已识别歌单 ID，不跟随任意用户 URL。

## 平台限制与验证边界

Spotify 2026 年开发模式需应用所有者具有有效 Premium，并对用户数、拥有／协作歌单内容读取施加限制。第三方歌单可能只有元数据，没有可读取内容。权限失败明确提示，不显示为空歌单。Exportify CSV 导入继续可用；CSV 是否能获得第三方歌单同样取决于平台权限。

2026-10-13：真实 YouTube 公开歌单 https://music.youtube.com/playlist?list=PLolCtjnq7-6CVlm_nHV0vJB-rsIRbUfoP 完整返回 56 首，页面导入、匹配和窄屏验证通过。旧文档示例 PLQwVIlKxHM6qv-o99iX9R85og7IzF9YS_ 返回总数 236、实际 233 条，拒绝部分导入。公开歌单内容随时间变化，计数是本次验证值。

Spotify 未提供真实应用和账号，真实授权／完整读取仍待验收。自动测试覆盖 PKCE challenge、state、取消、重放、刷新、清除期间回调防止授权恢复；模拟数据覆盖 53 条／两页、旧新字段、播客、缺失和 snapshot 变化。浏览器授权窗口使用拦截的模拟页面，不视为真实 Spotify 授权成功。

## 上游与来源

- Spotipy 2.26.0，MIT：https://github.com/spotipy-dev/spotipy
- ytmusicapi 1.12.3，MIT：https://github.com/sigma67/ytmusicapi
- 当前接口：https://developer.spotify.com/documentation/web-api/reference/get-playlists-items
- PKCE：https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow
- 开发模式迁移：https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
- YouTube 歌单文档：https://ytmusicapi.readthedocs.io/en/stable/reference/playlists.html

许可全文随 integrations/globalmusic 保存；版本按本次环境锁定。没有复制上游客户端实现进核心。
