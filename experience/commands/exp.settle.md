---
description: 收尾提取：从会话提炼经验并落盘（timeline→W→E→X→verify）
argument-hint: <session_id 或目标卡编号>
---

# exp.settle 收尾提取协议 0.2.0

> 0.2.0 变更（codex 审计 2026-10-12）：①提取改**当班主会话内执行**，删除
> headless 自调用链路（本机处理边界）；②goal 距离过滤升为**双基准**（W.goal
> + 会话 anchor）；③W 卡开工建立、本协议只补终态；④引用校验失败必须当失败
> 处理（verify_chain 退出码 0/1/2）。

1. 跑 `python .../scripts/timeline.py <session_id> --out <底稿.md>`（长会话默认截断模式；要核全文加 --full，--full 为真全文不截断；error 调用的报错取自 state.error）。db 只读，脚本不会写。
2. 按**目标三问**切单：要解决什么 / 怎样算完成 / 最后到什么状态。拿不准的单子标 pending，不硬编终态。
3. 补 W 目标卡终态（**W 卡在开工时由 exp.start 建立**，此处只补 final_state 与范围变更记录）。证据分 observed（tool output 直接可见）与 inferred（推算），**分开标注**，推算必须给推算链。reconstructed 的单 boundary_confidence 如实标。
4. 组织 E 案卷：执行证据**只认 tool part 的 state 与产物路径，回复自述不算数**。工具记录按四元组写：发起（input/意图）/ 返回（output 可见窗口，注明总长）/ 结果语义（completed≠成功，含失败信号加注）/ 验证（靠什么确认）。表格式失败链优先。
5. **当班主会话内提炼 X 候选**——本协议的执行者（当班智能体）本人就是提取器，直接读底稿做判断，禁止另起进程。**本机处理边界三禁**：禁 `zcode.cmd -p` 等 headless 自调用、禁把底稿/经验正文/可还原摘要发给当前会话通道之外的任何端点（含 A2A 桥）、禁在提取环节新增任何网络出口。候选必须带来源定位（E 案卷节号 + [call:] 引用）。
6. goal 距离过滤（**双基准**，codex 审计修正——单比较切单后 W.goal 挡不住漂移单）：
   - 基准一：候选与本单 W.goal 实体零交集 → 丢弃并留痕（写明理由）；
   - 基准二：候选与**会话 anchor**（W 卡 frontmatter 的 session_anchor：来源会话标题 + 首条真人消息摘要）零交集 → 属漂移单产物，不入 lessons，留痕记录（原始记录保留在 E 案卷，不删）；
   - 漂移经殿下明确批准的目标变更：W 卡记 `approved_goal_change: <批准口径>`，其候选按新 goal 走基准一，免基准二但注明。
7. 落盘 lessons/X<N>.md：版本全文落盘（新版本全文写进同一文件，旧版本全文进"版本历史"节——**旧版必须可完整还原**），frontmatter 对齐既有格式（id/version/status/system/project/tags/created），正文九节齐全（适用条件/建议/预期效果/验证点/例外/来源/状态/版本历史/取用记录）。
8. 生成/更新 U（取用结算：执行了吗/帮上忙了吗/升级还是退役/下次能查到吗）与 Q 回填（检索环节有无漏召回、对照环节教训）。U 只对应真正被采用或被显式评估的条目；空查询记 Q 不记 U。
9. **最后一律跑** `python .../scripts/verify_chain.py <本次落盘的全部文件>`；退出码 0 才算沉淀完成；**1（MISSING/AMBIGUOUS）或 2（无引用）都当失败处理**——不得为消 MISSING 删引用，失败进 backlog 待补。

提取目标：$ARGUMENTS。
