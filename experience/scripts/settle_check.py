# -*- coding: utf-8 -*-
"""settle_check.py — Stop hook 兜底：会话结束时查 W 目标卡缺失并记 backlog。

设计约束（2026-10-12 实装）：
- 确定性脚本，零 LLM、零网络；db 只读（mode=ro）。
- fail-open：任何异常都 exit 0，绝不阻塞会话收尾。
- 幂等：同一 session 的缺项在 backlog 只记一次（按 session_id 查重）。
- 探针豁免：消息数 < 4 的会话（探针/误触）不记。

stdin（hook 协议 JSON）里取 session_id（容错 session_id/sessionId/session）。
匹配 W 卡双通道：frontmatter sessions 列表含该 id，或 session_anchor 含
本会话标题。旧占位卡（sessions: [本会话]）无法按 id 匹配，靠人工补检。
"""
import io
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_URI = "file:C:/Users/14538/.zcode/cli/db/db.sqlite?mode=ro"
EXP = Path("C:/Users/14538/.zcode/experience")
ORDERS = EXP / "orders"
BACKLOG = EXP / "backlog.md"


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0
    sid = (data.get("session_id") or data.get("sessionId")
           or data.get("session") or "")
    if not sid or not re.fullmatch(r"[A-Za-z0-9_\-]+", sid):
        return 0
    core = re.sub(r"^sess_", "", sid)          # db 里 id 形态是 sess_<uuid>
    try:
        db = sqlite3.connect(DB_URI, uri=True)
        row = db.execute(
            "SELECT title, (SELECT COUNT(*) FROM message m WHERE m.session_id"
            " = s.id) AS n FROM session s WHERE s.id LIKE ?",
            ("%" + core[:8] + "%",)).fetchone()
        db.close()
    except Exception:
        return 0
    if row is None:
        return 0                       # 老库/副本库对不上：静默放过
    title, n_msgs = row[0] or "", row[1] or 0
    if n_msgs < 4:
        return 0                       # 探针豁免

    covered = False
    try:
        for w in ORDERS.glob("W*.md"):
            text = w.read_text(encoding="utf-8", errors="replace")
            fm = text.split("---", 2)
            head = fm[1] if len(fm) >= 3 else ""
            if core[:16] in text:
                covered = True
                break
            anchor = re.search(r"session_anchor:\s*(.+)", head)
            if anchor and title and title[:20] in anchor.group(1):
                covered = True
                break
    except Exception:
        return 0
    if covered:
        return 0

    try:                                # 幂等追加
        existing = BACKLOG.read_text(encoding="utf-8") if BACKLOG.exists() else ""
        if sid[:16] in existing:
            return 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        line = (f"| {sid[:16]} | W 目标卡缺失（Stop hook 自动查缺，"
                f"标题={title[:40]}，消息数={n_msgs}） | {now} | 待补 |\n")
        if "| 会话/单 | 缺什么 | 何时进单 | 状态 |" not in existing:
            return 0                   # backlog 结构异常：不乱写
        with open(BACKLOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.exit(main())
