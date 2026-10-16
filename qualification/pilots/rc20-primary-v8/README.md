# RC20 primary v8 冻结源码修订

本目录保存已关闭 primary9 研究使用的 source8 的 SOURCE 身份，以 Git `b4831ccff1ee5ecf4a7ce0a334d6d9190611b504` 中 primary-v6 的 `/target/source_map` 为基线。完整目标包含 120 文件，其中 109 文件继承，11 文件逐字保存在 `overrides/`；重建时递归解析固定基线，再应用 `source-revision.json` 中的覆盖。

manifest、source seal、完整目标映射及每份覆盖的 SHA-256 均固定在 `source-revision.json`。`overrides/README.md` 是历史源码的一部分，仅供字节重建，其状态文字不代表当前事实。发布仅核对原始字节，不执行源码、测试、编译器或模型。

本目录不是实测结果、资格通过、独立新留出集、净收益结论或发布安装授权。当前事实及后续资格以 [PROJECT_STATE](../../../PROJECT_STATE.md) 为准。
