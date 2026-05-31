@/Users/hwj/.codex/RTK.md

# MediaMark 协作规范

- 所有 shell 命令使用 `rtk` 前缀执行。
- 功能开发遵循测试先行：先写失败测试，再实现，再跑完整验证。
- 每完成一个版本的开发，必须执行 `git commit` 并 `git push` 到远程仓库。
- 版本功能、配置、README、roadmap、release 文档需要同步更新。
- 不回退用户已有改动；遇到无关未提交文件时保持原样。
- 交付前至少运行 `rtk .venv/bin/python -m pytest -q`，并确认 CLI 帮助、配置示例可用。
