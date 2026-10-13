# 版本路线与歌单解析项目调研

调研日期：2026-10-12。下表是后续接入候选，仓库与文档已查阅；CSV、个人成绩接口和网易云／QQ 公开歌单已实现；公开歌单已在线验证，个人成绩尚待用户真实密钥联调。

## v0.1：CSV 基础版（已实现）

CSV 导入 → 当前国服目录匹配 → 候选核对 → 罗马音筛选 → CSV／HTML 导出。优先保证误匹配不被计为确认收录。

## v0.2：个人成绩与自定义导出（已实现基础功能）

用户于 2026-10-12 增加查分与自定义图片需求，因此将其作为下一阶段优先项，原平台接入顺延。

- 舞萌／中二个人 API 只读完整成绩；本地页面输入个人密钥，不保存、不写入日志、不返回客户端结果。
- JSON 成绩导入；按游戏、曲目 ID、谱面类型与难度关联；候选不关联个人成绩。
- 页面、CSV、HTML 显示舞萌达成率与中二分数，以及 FC／AP／AJ、同步时间。
- 勾选导出字段，配置标题、浅色／深色主题与分页，预览并下载 PNG。
- 30 项自动测试及真实浏览器交互验证通过。个人 API 请求路径和字段已按官方文档核验；尚未使用用户真实密钥联调。该项仍待真实账号验收。

OAuth 多用户授权放在在线部署阶段：需用户在落雪注册应用并提供其应用配置，不能用好友码开发者简化接口替代完整分数接口。

## v0.3：网易云与 QQ 音乐公开歌单（已实现）

统一 URL 识别、歌单 ID、分页、元数据标准化。公开歌单先做；需要用户授权时显示登录需求，不把解析失败视为“空歌单”。

| 平台／项目 | 已核验的能力与许可证 | 拟接入方式 |
|---|---|---|
| [NeteaseCloudMusicApiEnhanced/api-enhanced](https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced) | 网易云第三方 Node API 服务；仓库声明 MIT；文档要求 Node 22+ | 自建辅助服务，读取歌单详情和分页歌曲列表后转换为 Track。先验证本地服务响应与歌单完整性 |
| [L-1124/QQMusicApi](https://github.com/L-1124/QQMusicApi) | Python 异步 QQ 音乐 API；仓库标识 GPL-3.0，README 表示 v3 or later | 候选适配器；接入前核查具体模块与许可证。可考虑独立可选组件，但不把进程隔离本身视为许可证结论 |

2026-10-13 已实现可选本地辅助服务、标准链接识别、分页与完整性检查。网易云 139 首／两批和 QQ 519 首／六页真实在线验证通过；失效歌单失败保留结果。私密、需登录与平台限流提示失败，当前通过 CSV 导入。分页、重复记录、部分返回、无歌手和平台失败由自动测试覆盖。详见 ONLINE.md；登录接入后续另行验收。

## v0.4：Spotify 与 YouTube Music（已实现，Spotify 待真实授权验收）

| 项目 | 已核验的能力与许可证 | 拟接入方式 |
|---|---|---|
| [watsonbox/exportify](https://github.com/watsonbox/exportify) | Spotify 歌单导出 CSV；MIT；字段包含 Track Name、Artist Name(s)、Album Name、Track URI | 其 CSV 格式已兼容。后续保留导出文件导入流程，不复制整个 React 应用 |
| [spotipy-dev/spotipy](https://github.com/spotipy-dev/spotipy) | 官方 Spotify Web API 的 Python 客户端；MIT | 如启用直接读歌单，使用用户授权和 Spotify 官方权限流程，逐页读取 |
| [sigma67/ytmusicapi](https://github.com/sigma67/ytmusicapi) | YouTube Music 非官方 Python API；MIT | 可选 Provider，读取歌单元数据。先检查公开／登录歌单需求、分页与接口稳定性 |

2026-10-13：已接入 Spotipy 2.26.0／ytmusicapi 1.12.3、官方 Spotify PKCE 与当前 items 接口、完整性核对。YouTube 56 首真实公开歌单验证通过；Spotify 模拟分页／授权测试通过，尚待用户真实应用配置验收。授权取消、读取失败保留原结果，不影响 CSV；登录材料不写进报告。详见 GLOBAL-MUSIC.md。

## v0.5：曲库地区、读音与人工确认

- 国服、日服、国际版分区，显示实际版本与来源。
- 从 SEGA 官方读音字段生成罗马音；自动转写单独标注。
- 可审核、撤销和保存人工作品关系，并导出核对规则。
- v0.2 已提供浏览器 Canvas PNG 与同字段 HTML。后续增加可复现的 HTML 截图导出和封面排版。

## 接入策略

依赖按平台选装；v0.1 保持 Python 标准库即可启动。Provider 只解析歌单元数据，Matcher 始终统一判断作品关系。真实接入前再次核查维护状态、API 行为与许可证，锁定版本并记录上游来源。库存在、仓库仍可访问，不等于接口已验证可用。


## 持续目标与验收记录

持续目标已在 Codex 建立；整个路线图尚未完成。每个阶段先验证数据完整性与失败处理，再同步到 E:\Projects\Code\RhythmBridge 并打包。

下一阶段：分区曲库与人工规则管理 → OAuth 和高级图片布局。账号／应用授权不足时保留待验收项，继续独立功能。
