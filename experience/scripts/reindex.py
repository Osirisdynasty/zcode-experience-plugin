# -*- coding: utf-8 -*-
"""reindex.py — 重生成 experience/INDEX.md（五行式版式，frontmatter 正则解析）。

用法: python reindex.py [--out FILE]   # 默认就地重写 INDEX.md（先备份 INDEX.md.bak）

orders 行:   - <id> <title> | MM-DD | <final_state> | <boundary_confidence> | <reconstructed|live> | <会话短id|本会话>
cases 行:    - <id> <标题> | order <W> | v<N> | <reconstructed|live> | <会话短id|本会话>
lessons 行:  - <id>@v<N> <status> | <system>/<project> | <标题> | 来源 E<N>；取用记录 M 条（域外 K）
usages 行:   - <id> | <W> | <lessons + 连接> | <status> MM-DD | 注记
queries 行:  - <file主名> | <W> | N 命中（ids）| 空结果判定：x
"""
import argparse
import glob
import os
import re
import shutil
import sys

EXP = "C:/Users/14538/.zcode/experience"
FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)


def parse_fm(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if inner:
                v = [x.strip().strip('"').strip("'") for x in re.split(r",(?![^（(]*[）)])", inner) if x.strip()]
            else:
                v = []
        fm[k.strip()] = v
    return fm, text[m.end():]


def date_from_name(name):
    m = re.search(r"(20\d{6})", name)
    if m:
        return m.group(1)[4:6] + "-" + m.group(1)[6:8]
    return "??-??"


def sess_short(v):
    if not v:
        return "?"
    s = v[0] if isinstance(v, list) else v
    if "本会话" in s:
        return "本会话"
    return s[:13] if s.startswith("sess_") else s[:12]


def h1_title(body):
    m = re.search(r"^#\s*(.+)$", body, re.M)
    return m.group(1).strip() if m else ""


def build_orders():
    rows = []
    for path in sorted(glob.glob(f"{EXP}/orders/*.md")):
        fm, _ = parse_fm(path)
        rid = fm.get("id", "?")
        title = fm.get("title", os.path.basename(path))
        state = fm.get("final_state", "?")
        conf = fm.get("boundary_confidence", "?")
        rec = "reconstructed" if str(fm.get("reconstructed", "")).lower() == "true" else "live"
        sess = sess_short(fm.get("sessions"))
        note = fm.get("note")
        tail = f" | {note}" if note else ""
        rows.append(f"- {rid} {title} | {date_from_name(os.path.basename(path))} | {state} | {conf} | {rec} | {sess}{tail}")
    return rows


def build_cases():
    rows = []
    for path in sorted(glob.glob(f"{EXP}/cases/*.md")):
        fm, body = parse_fm(path)
        rid = fm.get("id", "?")
        order = fm.get("order", "?")
        ver = fm.get("version", "?")
        rec = "reconstructed" if str(fm.get("reconstructed", "")).lower() == "true" else "live"
        sess = sess_short(fm.get("sessions"))
        title = h1_title(body)
        title = re.sub(r"^案卷\s*\S+[:：]\s*", "", title)
        rows.append(f"- {rid} {title} | order {order} | v{ver} | {rec} | {sess}")
    return rows


def build_lessons():
    rows = []
    for path in sorted(glob.glob(f"{EXP}/lessons/*.md")):
        fm, body = parse_fm(path)
        rid = fm.get("id", "?")
        ver = fm.get("version", "?")
        status = fm.get("status", "?")
        sysname = fm.get("system", "?")
        proj = fm.get("project", "?")
        m = re.search(r"^#\s*v\S+?\s*·\s*(.+)$", body, re.M)
        title = m.group(1).strip() if m else h1_title(body)
        src = re.search(r"\*\*来源\*\*：(.+?)(?=\n\n|\Z)", body, re.S)
        em = re.search(r"\bE\d+\b", src.group(1)) if src else None
        src_txt = f"来源 {em.group(0)}" if em else "来源 ?"
        usage_sec = body.split("## 取用记录", 1)
        u_entries = re.findall(r"^- (\d{4}-\d{2}-\d{2})\s+U\d+", usage_sec[1], re.M) if len(usage_sec) > 1 else []
        u_off = usage_sec[1].count("域外") if len(usage_sec) > 1 else 0
        u_txt = f"取用记录 {len(u_entries)} 条" + (f"（域外 {u_off}）" if u_off else "")
        rows.append(f"- {rid}@v{ver} {status} | {sysname}/{proj} | {title} | {src_txt}；{u_txt}")
    return rows


def build_usages():
    rows = []
    for path in sorted(glob.glob(f"{EXP}/usages/*.md")):
        fm, body = parse_fm(path)
        rid = fm.get("id", "?")
        order = fm.get("order", "?")
        lessons = fm.get("lessons", [])
        if isinstance(lessons, list):
            ltxt = "+".join(lessons) if lessons else "?"
        else:
            ltxt = str(lessons)
        status = fm.get("status", "?")
        t = fm.get("time_settled") or fm.get("time_planned") or "??-??"
        mmdd = t[5:10] if re.match(r"\d{4}-\d{2}-\d{2}", str(t)) else str(t)
        off = body.count("域外")
        adopted = len(re.findall(r"真适用|执行了|第 \d+ 次取用|生产落地|首次真命中", body))
        note = f"采用标记 {adopted} 处" + (f"；域外标记 {off} 处" if off else "")
        rows.append(f"- {rid} | {order} | {ltxt} | {status} {mmdd} | {note}")
    return rows


def build_queries():
    rows = []
    for path in sorted(glob.glob(f"{EXP}/queries/*.md")):
        fm, body = parse_fm(path)
        qid = os.path.basename(path)[:-3]
        order = fm.get("order", "?")
        sec = body.split("## 查询结果", 1)
        hits, misses = [], []
        empty = "?"
        if len(sec) > 1:
            for ln in sec[1].splitlines():
                mh = re.match(r"-\s*(X\d+)(?:@v\d+)?\s*(命中|未命中)", ln)
                if mh:
                    (hits if mh.group(2) == "命中" else misses).append(mh.group(1))
                me = re.search(r"空结果判定：([是否])", ln)
                if me:
                    empty = me.group(1)
        hit_txt = f"{len(hits)} 命中（{'/'.join(hits)}）" if hits else f"0 命中（未命中 {'/'.join(misses)}）" if misses else "0 命中"
        rows.append(f"- {qid} | {order} | {hit_txt} | 空结果判定：{empty}")
    return rows


def main():
    ap = argparse.ArgumentParser(description="重生成 experience/INDEX.md")
    ap.add_argument("--out", help="输出路径（默认就地重写，先备份 .bak）")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    lines = ["# experience/ 索引（脚本生成，勿手改）", ""]
    lines.append("## orders（目标卡）")
    lines += build_orders()
    lines += ["", "## cases（案卷）"]
    lines += build_cases()
    lines += ["", "## lessons（经验条目）"]
    lines += build_lessons()
    lines += ["", "## usages（取用记录）"]
    lines += build_usages()
    lines += ["", "## queries（查询记录）"]
    lines += build_queries()
    text = "\n".join(lines) + "\n"

    target = args.out or f"{EXP}/INDEX.md"
    if not args.out and os.path.exists(target):
        shutil.copy2(target, target + ".bak")
        print(f"已备份 {target}.bak", file=sys.stderr)
    with open(target, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"已生成 {target}（{len(lines)} 行）", file=sys.stderr)


if __name__ == "__main__":
    main()
