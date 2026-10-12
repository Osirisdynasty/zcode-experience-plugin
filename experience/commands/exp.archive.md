---
description: 归档补检：W/E/Q 齐备性与引用检查，缺项写 backlog 不阻塞
argument-hint: <W 编号或本单标识>
---

# exp.archive 归档补检协议 0.2.0

> 0.2.0 变更（codex 审计 2026-10-12）：①齐备性必查项改为 **W/E/Q**——U 可为
> 零（Q 即无采用的证明，合法无取用单不算缺项）；②verify_chain 退出码非零
> （1=引用缺失，2=无引用）也进待补清单，不得标沉淀成功。

1. 查齐备性：本单 W（orders/，含 final_state 与 session_anchor）、E（cases/）、Q（queries/——**U 可为零**，Q 证明无采用）是否都在、frontmatter 关键字段是否齐全。
2. 跑 `python C:/Users/14538/.zcode/plugins-local/experience/scripts/verify_chain.py <本单全部文件>`，按退出码判：0=通过；1（MISSING/AMBIGUOUS）与 2（无引用）都进待补。
3. 缺项处理：**追加写 backlog.md 待补清单**（缺什么/属哪单/建议补法）。三绝不：不阻塞归档、**绝不写 session.time_archived**、**绝不直写 db**。db 全程只读。
4. 报告殿下统一口径：「沉淀完成」或「缺 N 项待补（清单见 backlog.md）」。
5. 试点期不设硬闸：不齐也照归，只留痕。硬闸（缺 W 不许归档之类）待试点数据说话后再定。
6. 自动兜底：会话结束钩子（Stop hook → scripts/settle_check.py）会自动查本会话的 W 缺失并写 backlog；本命令是其人工/显式版。

补检目标：$ARGUMENTS。
