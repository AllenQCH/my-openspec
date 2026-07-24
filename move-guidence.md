# my-openspec 迁移指南

本指南用于重命名或移动中央 `my-openspec` 仓库。迁移属于本机配置维护，使用
`workflow_solve_personal_problem`，不创建业务分支、OpenSpec Initiative、commit、push
或外部发布动作。

## 迁移原则

- 迁移前先确认源目录、目标目录和目标目录不存在。
- 保留 `.git`、未跟踪文件、文件权限和 `bin/openspec` 可执行位。
- 不修改 `projects/`、`initiatives/`、Binding、服务 `openSpecPath` 或 Git remote。
- 不修改历史 session、memory 或归档记录中的旧路径；它们记录的是历史事实。
- 不在验证完成前删除原目录。跨磁盘迁移必须先复制、验证，再单独确认清理。
- 正在运行 OpenSpec CLI、归档或 Multi-Agent 交付时，不执行迁移。

## 推荐位置抽象

长期推荐让运行时只引用一个固定软链接，例如：

```text
/Users/heytea/.codex/workspaces/my-openspec -> /absolute/new/location/my-openspec
```

首次采用软链接时，必须同步修改下方“运行时引用”并完成全部验证。以后再次移动时，
只需更新软链接目标并重新验证。软链接本身存在但运行时仍引用其他绝对路径时，不算迁移完成。

## 迁移前检查

先设置明确的绝对路径，不使用未解析的 glob：

```bash
my_openspec_source="/absolute/current/location/my-openspec"
my_openspec_target="/absolute/new/location/my-openspec"

test -d "$my_openspec_source"
test ! -e "$my_openspec_target"
git -C "$my_openspec_source" rev-parse HEAD
git -C "$my_openspec_source" remote -v
git -C "$my_openspec_source" status --porcelain=v1 -uall
git -C "$my_openspec_source" worktree list --porcelain
stat -f '%Sp %N' "$my_openspec_source/bin/openspec"
```

记录上述输出。仓库有未提交或未跟踪文件时可以迁移，但迁移后必须逐项一致。

## 执行方式

### 同一磁盘

同一磁盘优先原位移动，以保留 Git 元数据、权限和未跟踪内容：

```bash
mv "$my_openspec_source" "$my_openspec_target"
```

### 跨磁盘

跨磁盘先复制并保留源目录：

```bash
mkdir -p "$my_openspec_target"
rsync -a "$my_openspec_source/" "$my_openspec_target/"
```

验证通过前不要删除源目录。源目录清理由用户另行明确授权。

## 运行时引用

如果没有使用已经接入运行时的固定软链接，需要更新以下活跃引用：

- `/Users/heytea/.codex/agents/control/control_request_router.toml`
- `/Users/heytea/.codex/agents/control/control_stage_orchestrator.toml`
- `/Users/heytea/.codex/agents/docs/tool-agent-matrix.md`
- `/Users/heytea/.codex/agent-catalog-runtime/check_openspec_bridge.py`
- `/Users/heytea/.codex/agents/README.md`
- `/Users/heytea/Documents/myHeytea/codex-workspace/AGENTS.md`
- Obsidian 的 `my-multi-agents` 与 `my-openspec` 当前入口

`~/.codex/config.toml` 只有在目标目录不属于当前 trusted project 范围时才需要补充。
便携 `multi-agent` 仓库不得写入本机绝对路径。

修改 Agent TOML 后运行：

```bash
/Users/heytea/.codex/agent-catalog-runtime/sync_agent_catalog.sh
/Users/heytea/.codex/agent-catalog-runtime/check_agent_catalog.sh
```

## 迁移后验证

使用迁移后的真实根目录执行：

```bash
git -C "$my_openspec_target" rev-parse HEAD
git -C "$my_openspec_target" remote -v
git -C "$my_openspec_target" status --porcelain=v1 -uall
stat -f '%Sp %N' "$my_openspec_target/bin/openspec"

"$my_openspec_target/bin/openspec" validate-workspace
python3 -m unittest discover -s "$my_openspec_target/tests" -v
python3 /Users/heytea/.codex/agent-catalog-runtime/check_openspec_bridge.py
```

最终还要确认：

- HEAD、remote、dirty 和未跟踪文件清单与迁移前一致。
- `bin/openspec` 仍可执行。
- `check_openspec_bridge.py` 返回 `valid: true`。
- 直接路径迁移时，活跃配置中不存在旧路径；软链接迁移时，固定入口能解析到新目录。
- 新开 Codex 任务后，Router 和 Orchestrator 能读取本指南。

## 失败处理

任一验证失败时停止后续操作，报告第一条具体错误。源目录仍存在时继续保留；同一磁盘移动
且原位置为空时，可以把目录移回原位置后重新运行验证。不要通过修改 Binding、删除未跟踪
文件或重新 clone 来掩盖迁移问题。
