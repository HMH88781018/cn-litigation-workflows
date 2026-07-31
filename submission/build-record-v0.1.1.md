# v0.1.1 Skills-only 构建记录

构建日期：2026-07-30

源版本：Git commit
`eabf123c13da838772beb743b97a235c100e8c07`（`0.1.1` 最终候选；既有本地
`v0.1.1` 标签保留为上一候选，不作为本次构建来源）

构建命令：

```bash
python3 scripts/package_plugin.py . --submission \
  --output dist/cn-litigation-workflows-openai-v0.1.1.zip
```

## 最终候选物

- 文件：`cn-litigation-workflows-openai-v0.1.1.zip`
- 大小：`856446` bytes
- 条目：`24`
- SHA-256：
  `7a6b6e69d6e92964b324c47db924a82c933d0ff28cc4b2d86987743f60eb0a3b`

## 已执行检查

- 项目确定性验证：通过；
- Python `unittest`：34/34 通过；
- 合成 eval 结构：10/10 有效；
- 插件 manifest 校验：通过；
- 两个 Skill `quick_validate`：通过；
- 最终 ZIP 解压后再次执行插件和两个 Skill 校验：通过；
- 品牌图仅作无损 PNG 重压缩，1024×1024 像素逐点差异为 `0`；
- ZIP 白名单：仅 manifest、品牌图、两个 Skill、许可证和第三方排除说明；
- ZIP 不含 MCP、app、screenshots、GitHub workflow、测试源码、投稿说明、
  DOCX、缓存、符号链接或真实案件材料；
- 旧 `cn-litigation-workflows-v0.1.0.zip` 未改写，SHA-256 仍为
  `932a12d111ad5e063e75ce4b99bf338467c7fa52a5ee568963e05095437fb4f4`。

发布主体已确认为个人，可用范围已确认为 OpenAI 门户提供的全部可选国家和
地区；公开发布者显示名及个人验证身份英文拼写均为 `Huang Minghuan`。
作者已于 2026-07-30 在 ChatGPT 会话中逐项电子确认
`author-rights-confirmation.md` 所列八项内容。OpenAI Platform 个人身份验证
仍须发布者本人在平台完成；上述人工事项均不是机器测试可以替代的。
