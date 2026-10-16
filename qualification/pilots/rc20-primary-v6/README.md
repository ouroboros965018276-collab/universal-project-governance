# RC20 primary v6 冻结源码修订

本目录以 Git 基线 `9fa1df5e3f7b07e6e22fec7cb27d3c5d3d92fa7c` 中的 `qualification/pilots/rc20-primary-v4/source-revision.json` 为依据，固定使用其 `/target/source_map` 的完整 120 文件身份。118 文件继承，仅逐字保存 `manual/helper.py` 与 `shared/project_auditor_primary.py` 两份覆盖；不引用未提交的 v5 草稿，不复制 worker README 或运行时源码树。

`source-revision.json` 登记冻结 primary v6 源码的完整目标映射。治理 runtime、v8 分析标准、66 角色 roster、质量门禁和预算身份保持不变。该目录仅是冻结 SOURCE 修订，不是实测结果、当前项目状态或升级授权。

当前事实及后续资格一律以 [PROJECT_STATE](../../../PROJECT_STATE.md) 为准。
