# OpenSpec

项目级规范、跨项目需求协调、问题排查和不可变历史归档工具。

## 边界

OpenSpec 与 Multi-Agent 分离：

- Multi-Agent 决定使用哪个 Workflow、Stage、Tool 和 Gate。
- OpenSpec 只提供对象、schema、模板、校验和归档命令。
- 项目内 `openspec/` 是开发期间的活跃原件；中央仓库只保存协调信息和最终快照。

## 对象结构

```text
projects/<projectKey>/
initiatives/_shared/<initiativeKey>/
initiatives/<projectKey>/<initiativeKey>/binding.yaml
investigations/<projectKey|_unassigned>/<investigation>/
archive/initiatives/_shared/<initiativeKey>/revisions/rNNN/
```

一个需求，无论涉及一个还是多个项目，都只有一个 `_shared` Initiative。每个参与项目只有一个 Binding；一个项目内可登记多个服务级 OpenSpec。

## 快速开始

```bash
bin/openspec init-project project-a '示例项目' shared

bin/openspec init-initiative \
  DEMO-100-example-shared \
  DEMO-100 '示例需求' shared \
  --project project-a

bin/openspec bind-service \
  DEMO-100-example-shared project-a \
  shared:service-a git@example.com:team/service-a.git \
  openspec/changes/DEMO-100 feature/DEMO-100
```

项目完成后按服务收集结果：

```bash
bin/openspec collect-project-result \
  DEMO-100-example-shared project-a shared:service-a \
  <full-commit-sha> \
  --test-evidence openspec/changes/DEMO-100/testing.md \
  --delivery-evidence openspec/changes/DEMO-100/rollout.md
```

归档前检查并从精确 Commit 生成快照：

```bash
bin/openspec set-initiative-status DEMO-100-example-shared completed
bin/openspec check-archive-ready DEMO-100-example-shared
bin/openspec archive-initiative DEMO-100-example-shared \
  --checkout shared:service-a=/absolute/path/to/service-a
```

本地路径只参与本次归档，不会写入中央元数据。

## Investigation

```bash
bin/openspec new-investigation '示例接口异常' shared --project project-a
```

目录名使用 `inv-YYYYMMDD-shortid-symptom-env`，不依赖需求号，也不包含完整 traceId。排查可独立关闭，或通过 `promote-investigation` 转成 Initiative。

## 校验

```bash
python3 -m unittest discover -s tests -v
bin/openspec validate-workspace
```

## 迁移仓库

重命名或移动中央仓库前，先完整阅读 [`move-guidence.md`](move-guidence.md)。该指南包含
Multi-Agent 引用更新、Git 状态保护、跨磁盘迁移和迁移后验证步骤。
