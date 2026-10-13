# 落雪成绩接入

核验日期：2026-10-12。官方资料：

- https://maimai.lxns.net/docs/developer-guide
- https://maimai.lxns.net/docs/api/maimai
- https://maimai.lxns.net/docs/api/chunithm

个人密钥在落雪账号详情生成。只在本地应用页面输入，不要发到聊天中。本应用使用 X-User-Token 调用 GET /api/v0/user/{maimai|chunithm}/player/scores；没有向落雪上传歌单或写入成绩的接口。

开发者好友码的所有成绩接口返回 SimpleScore，缺少完整数值，不能替代本功能。多人服务优先采用 OAuth，需要注册应用和授权，当前未实现 OAuth。

舞萌保留 achievements 原百分数（100.1234 即 100.1234%），中二保留整数 score。标准与 DX 分开，难度分开；候选曲不带入成绩。JSON 导入接受数组、{data:[...]} 或 {scores:[...]}；简化成绩和无效数值拒绝导入。

未同步、读取失败、已导入记录里无相应谱面、已有成绩是不同状态。缺失不等于没玩过。个人 API 只代表落雪已同步的数据；JSON 只代表文件提供的数据。UTC 时间在页面和图片显示为北京时间，CSV 保留原时间。

密钥不落盘、不写日志、不同域跳转被拒绝；输入发送后立即清空。成绩保存在当前页面内存，刷新页面清除，下载的文件由用户自行保留。失败不覆盖此前的成绩。本地接口沿用 Host / Origin 限制。

验证边界：请求构造、错误处理、导入、关联、导出使用模拟数据测试通过；没有用户的个人密钥，因此未验证真实账号响应。不要把示例分数视为用户真实成绩。
