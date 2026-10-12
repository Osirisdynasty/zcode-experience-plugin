# -*- coding: utf-8 -*-
"""timeline.py — 从 zcode 会话 db 切单底稿（只读）。

用法: python timeline.py <session_id> [--out FILE] [--full]

输出 markdown：
- 头部：session id/title/directory/起止时间/是否已归档
- 主事件流（按 message.sequence, part.sequence）：
  real_user 消息全文（[msg:<id>]）；assistant text 段（截 300 字）；
  tool 调用骨架（工具名+status+input 摘要+output 头 200 字，[call:<16位前缀>]）；
  completed 但 output 含失败信号（Traceback/FAILED/Error/非零 exit）加注 ⚠
- 子智能体 / A2A 分区单独标注
默认 tool 骨架全量、文本截断；--full 输出全文。
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime

DB_URI = "file:C:/Users/14538/.zcode/cli/db/db.sqlite?mode=ro"

FAIL_SIGNALS = [
    r"Traceback \(most recent call last\)",
    r"\bFAILED\b",
    r"\bError\b",
    r"\berror\b",
    r"exit code:? [1-9]",
    r"Command failed with exit code: [1-9]",
    r"AssertionError",
]
FAIL_RE = re.compile("|".join(FAIL_SIGNALS))

TEXT_LIMIT = 300
OUTPUT_LIMIT = 200


def ts(ms):
    if not ms:
        return "?"
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def one_line(s, limit):
    s = re.sub(r"\s+", " ", str(s)).strip()
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s


def load_session(cur, sid):
    row = cur.execute(
        "SELECT id,title,directory,time_created,time_archived,task_type "
        "FROM session WHERE id=?",
        (sid,),
    ).fetchone()
    return row


def render_session(cur, sid, full):
    """返回 (markdown 文本行列表, 首末时间ms元组)"""
    row = load_session(cur, sid)
    if not row:
        return None, None
    _, title, directory, tc, ta, task_type = row
    lines = []
    lines.append(f"### 会话 {sid}")
    lines.append(f"- title: {one_line(title, 200)}")
    lines.append(f"- directory: {directory}")
    lines.append(f"- task_type: {task_type}")
    lines.append(f"- 起止时间: 见事件流首末条目")
    lines.append(f"- 已归档: {'是' if ta else '否'}")
    lines.append("")

    msgs = cur.execute(
        "SELECT id, sequence, data FROM message WHERE session_id=? "
        "ORDER BY sequence",
        (sid,),
    ).fetchall()
    parts = cur.execute(
        "SELECT message_id, sequence, data FROM part WHERE session_id=? "
        "ORDER BY sequence",
        (sid,),
    ).fetchall()

    mdata = {}
    for mid, mseq, raw in msgs:
        try:
            d = json.loads(raw)
        except Exception:
            d = {}
        mdata[mid] = (mseq, d)

    # 按 message 分组 parts，保持 message 顺序
    by_msg = {}
    for mid, pseq, raw in parts:
        by_msg.setdefault(mid, []).append((pseq, raw))

    first_ts, last_ts = None, None
    n_tool = 0
    for mid, mseq, _ in sorted(
        ((mid, v[0], v[1]) for mid, v in mdata.items()), key=lambda x: x[1]
    ):
        _, md = mdata[mid]
        role = md.get("role")
        sem = md.get("semantics") or {}
        mtime = (md.get("time") or {}).get("created")
        if mtime:
            first_ts = first_ts or mtime
            last_ts = mtime

        if role == "user":
            origin = sem.get("origin")
            if origin is not None and origin != "real_user":
                continue  # 语义标注存在且非真人（工具回执合成等）不进底稿
            # semantics 缺失（老会话）→ role==user 即视为真人消息；
            # A2A 会话在会话级按标题前缀排除，不在此处重复判
            texts = []
            for pseq, raw in by_msg.get(mid, []):
                try:
                    pd = json.loads(raw)
                except Exception:
                    continue
                if pd.get("type") == "text" and pd.get("text"):
                    texts.append(pd["text"])
            body = "\n".join(texts).strip() or md.get("text") or ""
            if not body:
                continue  # 顶层与 text parts 均无正文（老会话空壳消息），不产空块
            lines.append(f"**[msg:{mid}] {ts(mtime)} 用户**")
            lines.append("```")
            lines.append(body if full else one_line(body, 4000))
            lines.append("```")
            lines.append("")
        elif role == "assistant":
            for pseq, raw in by_msg.get(mid, []):
                try:
                    pd = json.loads(raw)
                except Exception:
                    continue
                ptype = pd.get("type")
                if ptype == "text":
                    text = pd.get("text") or ""
                    if full:
                        shown, mark = text, ""
                    else:
                        shown = text[:TEXT_LIMIT]
                        mark = " …[截断]" if len(text) > TEXT_LIMIT else ""
                    lines.append(f"[assistant {ts(mtime)}] {shown}{mark}")
                    lines.append("")
                elif ptype == "tool":
                    n_tool += 1
                    callid = pd.get("callID") or "?"
                    prefix = callid[:16]
                    tool = pd.get("tool") or "?"
                    st = pd.get("state") or {}
                    status = st.get("status") or "?"
                    inp_raw = st.get("input")
                    out = st.get("output")
                    out = "" if out is None else str(out)
                    # codex 审计 #6：status=error 时报错在 state.error，
                    # output 常为空——丢失真正的报错内容
                    err_note = ""
                    if status == "error" and not out:
                        err = st.get("error")
                        if err:
                            out = str(err)
                            err_note = " ⚠(取自state.error)"
                    if full:
                        inp = inp_raw if inp_raw is not None else ""
                        out_head = out
                        out_mark = ""
                    else:
                        inp = one_line(inp_raw, 160)
                        out_head = out[:OUTPUT_LIMIT]
                        out_mark = " …[截断]" if len(out) > OUTPUT_LIMIT else ""
                    warn = ""
                    if status == "completed" and out and FAIL_RE.search(out):
                        warn = " ⚠(completed但output含失败信号)"
                    lines.append(
                        f"- [call:{prefix}] tool={tool} status={status}{warn}{err_note}"
                    )
                    lines.append(f"  - input: {inp}")
                    lines.append(
                        f"  - output头: {one_line(out_head, 4000) if not full else out_head}{out_mark}"
                        f"（总长 {len(out)} 字符）"
                    )
    lines.append(f"<!-- tool 调用数: {n_tool} -->")
    return lines, (first_ts, last_ts)


def main():
    ap = argparse.ArgumentParser(description="会话切单底稿生成器（db 只读）")
    ap.add_argument("session_id")
    ap.add_argument("--out", help="输出到文件（默认 stdout）")
    ap.add_argument("--full", action="store_true", help="文本不截断")
    args = ap.parse_args()

    db = sqlite3.connect(DB_URI, uri=True)
    cur = db.cursor()

    out_lines = ["# 切单底稿", ""]
    main_lines, span = render_session(cur, args.session_id, args.full)
    if main_lines is None:
        print(f"错误：session {args.session_id} 不存在", file=sys.stderr)
        sys.exit(1)

    # 回填头部时间
    start, end = span if span else (None, None)
    header = main_lines[:6]
    header[4] = f"- 起止时间: {ts(start)} → {ts(end)}"

    out_lines += header + main_lines[6:]

    # 子智能体分区
    subs = cur.execute(
        "SELECT id, title, time_created, time_archived FROM session "
        "WHERE parent_id=? ORDER BY time_created",
        (args.session_id,),
    ).fetchall()
    out_lines.append("")
    out_lines.append("## 子智能体 / A2A 事件分区")
    if not subs:
        out_lines.append("（本会话无派生子智能体会话）")
    for sid, title, tc, ta in subs:
        tag = "子智能体" if sid.startswith("sess_subagent_agent_") else "派生会话"
        a2a = "；A2A" if title and title.startswith("[A2A task from peer") else ""
        out_lines.append(f"- [{tag}{a2a}] {sid} | {ts(tc)} | 已归档={'是' if ta else '否'} | {one_line(title, 120)}")
        sub_lines, _ = render_session(cur, sid, args.full)
        if sub_lines:
            for ln in sub_lines[6:]:  # 跳过子会话自身头部
                if ln.strip():
                    out_lines.append("  " + ln)

    # 全局 A2A 提示
    a2a_ct = cur.execute(
        "SELECT count(*) FROM session WHERE title LIKE '[A2A task from peer%'"
    ).fetchone()[0]
    out_lines.append("")
    out_lines.append(f"<!-- 库内 A2A 会话总数: {a2a_ct}（仅标题前缀识别） -->")

    text = "\n".join(out_lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写出 {args.out}（{len(out_lines)} 行）", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
