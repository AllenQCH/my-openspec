# OpenSpec Workspace Rules

这个仓库是规范与事实面，不是 Multi-Agent 控制面，也不是业务代码仓。

## Source of truth

- 项目内 `openspec/` 是开发期间唯一持续更新的服务级事实。
- `projects/<projectKey>/standards/` 保存项目共用规范。
- `initiatives/_shared/<initiativeKey>/` 保存唯一的中央需求协调对象。
- `initiatives/<projectKey>/<initiativeKey>/binding.yaml` 只保存项目绑定，不复制需求正文。
- `archive/initiatives/_shared/<initiativeKey>/revisions/<revision>/` 保存指定 Commit 下的不可变快照。

## Boundaries

- 不在本仓库注册 Workflow、Stage、Tool 或 Gate Agent。
- 不把业务服务源码 clone 到 Initiative 目录。
- 不保存密码、Cookie、Token、生产数据导出或敏感个人信息。
- 本地 checkout 路径只能作为 CLI 临时参数，不能写入 Project、Binding 或 Archive 元数据。
- 归档必须使用完整 Commit SHA，并从该 Commit 读取项目内 OpenSpec。

## Changes

- 先更新 schema 和测试，再修改 CLI 行为。
- 运行 `python3 -m unittest discover -s tests -v`。
- 运行 `bin/openspec validate-workspace`。
- 未经明确授权，不 commit、push 或修改外部系统。

## Relocation

- 重命名或移动本仓库前，必须完整读取根目录 `move-guidence.md`。
- 迁移时保留 Git 状态、未跟踪文件、权限和远端配置，并同步 Multi-Agent 活跃引用。
- 只有 Agent catalog、OpenSpec bridge、workspace 和单元测试全部通过，才可报告迁移完成。
