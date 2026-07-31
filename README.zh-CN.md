# 中国诉讼工作流

[English](README.md)

这是一个面向 ChatGPT 与 Codex 的开源法律工作流项目，把中国诉讼实务中
高风险、易出错的操作规则转化为可追溯、可复算、可测试的 Agent Skills。

> 当前为首次公开版本。本项目不宣称获得法院或 OpenAI 背书，不承诺法律结论
> 必然正确，也不宣称已经形成广泛采用。是否符合 OpenAI Codex for Open
> Source 项目福利，由 OpenAI 独立审核决定。

## 项目包含什么

| Skill | 负责范围 | 不负责范围 |
|---|---|---|
| `draft-cn-element-complaints` | 要素式起诉状路由、官方母版保护、定点修改、DOCX 结构审计、跨文书放行 | 普通法律咨询、非中国法院诉状 |
| `prepare-cn-evidence-damages` | 证据清单、证据材料目录、证据成册与页码、交通事故赔偿、保险与付款闭合 | 起诉状主文、一般质证意见 |

两项 Skill 之间存在明确责任边界：证据与赔偿 Skill 是证据编号、页码、
公式和金额的唯一真源；要素式起诉状 Skill 读取已经锁定的数据，并负责诉状
及整套文件的最终状态。

## 与普通提示词集合的区别

项目不仅提供文字说明，还包括：

- DOCX 表格结构审计与定点修改差异检测脚本；
- 证据—争点—诉请—赔偿项目的双向闭合规则；
- 可复算的交通事故赔偿审计模板；
- 合成数据测试、隐私扫描、Skill 合同校验和发布打包；
- GitHub Actions 持续集成；
- 可选择启用的只读 Codex PR 审查工作流；
- 法源更新、人工复核、版本发布和贡献治理规则。

## 安装

在 Codex 中添加本 GitHub 仓库并安装插件：

```bash
codex plugin marketplace add HMH88781018/cn-litigation-workflows --ref v0.1.1
codex plugin add cn-litigation-workflows@cn-litigation-workflows
```

在 ChatGPT 桌面端打开 **Plugins**，选择 `CN Litigation Workflows`
来源，再安装并启用本插件。

GitHub 市场安装不等于公开目录发表。向 OpenAI Plugins Directory 提交时，
构建白名单化的 Skills-only ZIP：

```bash
python3 scripts/package_plugin.py . --submission \
  --output dist/cn-litigation-workflows-openai-v0.1.1.zip
```

再使用 OpenAI Platform 插件提交门户和
[提交材料](submission/listing.zh-CN.md)。目录审核与公开发表本身不构成
任何创作者付款计划的资格。

如只需在 Codex 中使用独立 Skill：

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/draft-cn-element-complaints "$HOME/.agents/skills/"
cp -R skills/prepare-cn-evidence-damages "$HOME/.agents/skills/"
```

## 使用示例

```text
使用 $draft-cn-element-complaints，以 REVIEW 模式复核这份要素式起诉状。
不得修改文件。列明官方母版版本、结构漂移、未锁定字段和放行阻断项。
```

```text
使用 $prepare-cn-evidence-damages，根据匿名化材料制作证据 manifest 和
交通事故赔偿表。动态法律和统计数值必须保留来源与核验日期；全部门禁通过前
标记为 DRAFT。
```

## 本地校验

```bash
python3 scripts/validate_project.py .
python3 -m unittest discover -s tests -v
python3 scripts/run_evals.py
python3 scripts/package_plugin.py --output dist/cn-litigation-workflows.zip
python3 scripts/package_plugin.py . --submission \
  --output dist/cn-litigation-workflows-openai-v0.1.1.zip
```

合成提示词的人工/代理执行与结果评分方法见 [eval 指南](docs/evals.md)。

## 必须明确的限制

- 默认适用中国大陆，但每案仍须重新核验现行法律、案由、官方母版、受诉法院
  技术要求、统计参数和保险限额。
- 工具运行成功不等于文书正确。未通过对应门禁及独立复核，一律不得使用
  `RELEASE`。
- 禁止把真实客户姓名、身份证号码、联系方式、病历、证据或其他机密信息提交
  到公开 Issue、PR、测试文件或 CI 日志。
- 项目不收集遥测数据，不包含远程服务、MCP 服务或账号凭证。
- 67 类模板项目 `yaosushi-suzhuang` 以及第三方通用 Skill
  `legal-logic-analysis` 未纳入本发布包，避免许可证混同和来源误认。

进一步阅读：[隐私政策](PRIVACY.md)、[安全政策](SECURITY.md)、
[使用条款](TERMS.md)、[法源政策](docs/legal-source-policy.md)、
[贡献指南](CONTRIBUTING.md)和[治理规则](GOVERNANCE.md)。

## 许可证

项目原创内容采用 [Apache-2.0](LICENSE) 开源许可证。该许可证不处分项目
无权处分的法院表格、法律文件、外部网站或其他第三方材料。详见
[第三方说明](THIRD_PARTY_NOTICES.md)。
