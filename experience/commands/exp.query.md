---
description: 账查：按 X/W 编号查取用史与战绩，或按 session 反查 W/E
argument-hint: <X<N> | W<N> | sess_...>
---

# exp.query 账查协议 0.1.0

纯读操作，可直跑脚本+读文件，不调用提取/结算流程。

1. 给 X<N>：读 lessons/X<N>.md——当前版本/状态/版本历史；再扫 usages/*.md 找引用该 X 的 U，按三列分列：**采用**（真适用且执行）/ **域外**（显式拒绝或场景不存在）/ **未知**（planned、未结算）。战绩口径：采用次数、域外次数、有无反例，逐条给 U 编号与日期；采用/域外判分不清时归未知并注明。
2. 给 W<N>：读 orders/ 对应 W——goal/终态/证据齐备性；查 U（本单取用结算）与 E（本单案卷）是否存在并互相印证（U 引的 X 是否都在 E 的来源链上）。
3. 给 sess_<id>：反查——扫 orders/cases frontmatter 的 sessions 字段找归属的 W/E；无归属则报"该会话未沉淀"。
4. 输出一律给文件路径，不转述大段正文；发现 INDEX.md 与条目状态不一致时提示跑 reindex.py。

查账目标：$ARGUMENTS。
