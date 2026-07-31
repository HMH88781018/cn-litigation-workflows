# OpenAI 插件目录提交文案（v0.1.1）

状态：提交候选。发布主体、可用范围和作者权利八项声明已由发布者确认；
OpenAI Platform 个人身份验证及公开链接可访问性仍须在提交前完成。

## Info

- 提交类型：Skills only
- Package name：`cn-litigation-workflows`
- Plugin name / Display name：`中国诉讼工作流`
- Version：`0.1.1`
- Developer name：`Huang Minghuan`
- Publisher type：`Individual / 个人`
- Availability：`OpenAI 提交门户提供的全部可选国家和地区`
- Primary language：`简体中文`
- Jurisdictional scope：`中国大陆诉讼实务`
- Category：`Productivity`
- Short description：`可审计的中国诉状、证据与交通事故赔偿工作流`
- Website：`https://github.com/HMH88781018/cn-litigation-workflows`
- Support：`https://github.com/HMH88781018/cn-litigation-workflows/issues`
- Privacy：`https://github.com/HMH88781018/cn-litigation-workflows/blob/main/PRIVACY.md`
- Terms：`https://github.com/HMH88781018/cn-litigation-workflows/blob/main/TERMS.md`

公开发布者显示名及个人验证身份英文拼写统一确定为 `Huang Minghuan`，并已
同步写入 `author.name` 与 `interface.developerName`。该姓名与项目版权、
原创方法论作者及维护者记录中的真实权利主体一致。

发布者选择以个人身份提交，并选择 OpenAI 提交门户当时提供的全部可选国家和
地区，以覆盖全球可访问范围。该设置不表示插件能突破 OpenAI 的地区、账户、
工作区或产品可用性限制，也不把本插件的法律适用范围扩展到中国大陆法域之外。

## Long description

面向中国大陆诉讼实务的专业辅助，将要素式起诉状、证据清单与目录、证据成册
及交通事故赔偿计算转化为可追溯、可复算、可测试的阶段门禁。缺少现行法源、
关键事实、最终页码、人工法律判断或跨文书一致性时，输出保持 `DRAFT` 并列明
阻断项。插件不包含 MCP、远程服务、遥测、账号系统或真实案件数据。仅供具备
相应资质的法律专业人员使用，或在其实际参与和人工复核下使用；不替代个案
法律意见，不自动作出高风险法律决定。

## Starter prompts

1. `按门禁复核这份要素式起诉状，列出阻断正式交付的问题。`
2. `根据匿名化材料制作证据清单、证据目录和页码映射。`
3. `复核交通事故赔偿表的法源、公式、保险分层与金额闭合。`

## Release notes

首次提交的 Skills-only 插件，包含两项中国诉讼工作流。v0.1.1 增加目录品牌
图、最小化提交 ZIP、五个正向和三个负向审查用例、原创权利确认草案，并收窄
两个 Skill 的触发边界。无需账号、MCP 或测试凭证；审查材料全部使用合成事实。

## 提交前人工确认

- [x] 发布主体确定为个人（Individual）。
- [x] 可用范围确定为 OpenAI 门户提供的全部可选国家和地区。
- [ ] OpenAI Platform 中已按 `Huang Minghuan` 完成个人身份验证，且门户
  显示的验证姓名与 manifest 一致。
- [ ] 提交账号在同一组织拥有 `Apps Management: Write`。
- [x] 发布者显示名与 manifest 完全一致：`Huang Minghuan`。
- [ ] Website、Support、Privacy、Terms 均已公开可访问。
- [x] 已运行最终 ZIP 的安全扫描和全部本地测试。
- [x] 已核验并以 ChatGPT 会话电子确认方式确认
  `author-rights-confirmation.md`。
