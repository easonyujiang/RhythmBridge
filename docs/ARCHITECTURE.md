# 架构与接入约定

```text
CSVProvider / 未来的歌单 API Provider
          ↓ Track(index, title, artist, album, url, source)
CatalogStore → Matcher → rows / stats / evidence
                            ↓
                     筛选、检索、CSV / HTML 导出
```

## 解析器

`PlaylistProvider` 定义 `name` 与 `load(source, **options) -> list[Track]`。当前注册表仅启用 CSV。新增适配器放在 `rhythmbridge/providers/`，再注册到 `PROVIDERS`。v0.1 的网页 API 只接收 CSV，不接受任意 URL。

后续歌单解析器负责：识别平台与歌单 ID、分页、统一元数据、返回来源与完整性提示。解析器不得替代匹配器做“同名即同曲”的判断。

## 数据层

`data/catalog.json` 是随项目提供的基准快照。在线更新写入忽略目录 `.cache/catalog.json`，四个固定来源全部读取成功后才原子替换。失败保留旧快照。网页显示实际快照日期。

`data/rules.json` 是可审阅的作品关系，每条规则包含规范曲名、罗马音、目标游戏编号、经过核对的标题／歌手组合、核对日期与说明。规则必须同时匹配标题与歌手，不把歌手不同的同名曲自动视为翻唱。

新增规则可扩大确认范围；游戏编号是否仍存在、是否禁用，由当前快照决定。人工规则不覆盖禁用状态。

## API

| 接口 | 用途 |
|---|---|
| GET /api/catalog | 曲库摘要与更新时间 |
| POST /api/inspect | 读取 CSV 表头、推断列，返回识别条数 |
| POST /api/analyze | CSV → 逐条匹配与汇总 |
| POST /api/refresh | 从固定曲库来源更新快照 |

CSV 请求使用 `csv_base64`（原始文件字节），或 UTF-8 字符串 `csv`。可传 `columns: {title: "曲名列", artist: "歌手列"}` 覆盖自动识别。状态为 `confirmed` / `candidate` / `disabled` / `unmatched`。导出在浏览器本地生成。

## 后续扩展

平台解析接口需要保留来源、分页完整性、登录需求和失败原因，凭据不能进入日志或导出。独立服务适配器只交换 Track 元数据；确认是否使用 GPL 依赖或改变项目分发方式应在真正接入前重新核查许可证。

日服／国际版曲库要增加显式 `region` 与版本过滤，禁止合并成“国服已收录”。自动罗马音可使用日服读音字段／转写库，但必须标注“官方读音”“人工核对”“自动转写”三种依据。
