---
name: experience
description: zcode 经验复用闭环——体系分层、四命令何时跑、脚本位置
---

# 经验复用体系（experience plugin 0.2.0）

## 体系分层（信息流方向）

原始记录（zcode 会话 db，只读）→ **W 目标卡**（orders/，一单一张：goal/范围/验收/终态+终态证据，observed 与 inferred 分开标）→ **E 案卷**（cases/，执行证据卷：只认 tool part 的 state 与产物路径，工具记录四元组=发起/返回/结果语义/验证）→ **X 经验**（lessons/，可复用条目：frontmatter+九节正文，版本全文落盘）→ **U 取用记录**（usages/，一单一张：执行了吗/帮上忙了吗/升级还是退役/下次能查到吗）。

旁路记录：**Q 查询记录**（queries/，检索式+命中+空结果判定，空检索不算 U）。INDEX.md 由 scripts/reindex.py 生成，勿手改。

## 四个命令何时跑

- **/exp.start**：新单开工、plan 定稿前。跑 query.py → 逐条对照适用条件（先验"本单架构里场景存在吗"再问"条件成立吗"）→ 采用项写冻结"规划引用块"进 plan。
- **/exp.settle**：单收尾、终态已定。timeline.py 切单底稿 → W/E/X/U/Q 落盘 → 最后必跑 verify_chain.py。
- **/exp.archive**：单归档前。查 W/E/Q 齐备（U 可为零，Q 即无采用证明）+ verify_chain 退出码 0（1=引用缺失/2=无引用均进待补）；缺项写 backlog.md，不阻塞、绝不写 db。
- **/exp.query**：随时查账。给 X/W 查取用史与战绩；给 sess_ 反查归属。

## 脚本（plugins-local/experience/scripts/，均确定性、db 只读）

- `timeline.py <session_id> [--out FILE] [--full]` 会话切单底稿
- `query.py "<goal>" [--top N]` 经验检索（打分明细+hit/suspect/drop 三档）
- `verify_chain.py <file.md...>` 引用存在性校验（call/msg/file）
- `reindex.py [--out FILE]` 重生成 INDEX.md（默认就地写，先备份 .bak）
