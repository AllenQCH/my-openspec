# 交付规范

- 只有 `gate_test_passed` 后才能 commit、push、发布依赖或触发流水线。
- `hsp-invoice` 发生变化时，先发布依赖包，再构建或部署受影响服务。
- 中央 Binding 只记录完整 Commit SHA、仓库相对 OpenSpec 路径和证据路径，不记录本机 checkout 路径。
- Delivery 为每个实际交付服务生成 `collect-project-result` 请求；Root 执行并回填 CLI JSON 和退出码。
- 未经明确授权不创建 MR、不合并主干、不执行权限 SQL、不触发生产动作。
- 测试环境通过且 Project/Initiative 检查完成后，方可进入归档检查和不可变 Revision 生成。
