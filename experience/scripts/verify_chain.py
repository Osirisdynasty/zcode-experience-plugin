# -*- coding: utf-8 -*-
"""verify_chain.py — 校验经验库文件中的引用是否存在（db 只读）。

用法: python verify_chain.py <file.md...> [--json]

引用形态：
- [call:<16位前缀>]  → part 表 data LIKE '%"callID":"<prefix>%'（前缀唯一=OK，多条=AMBIGUOUS，零条=MISSING）
- [msg:<id>]          → message 表（支持前缀：唯一=OK，多条=AMBIGUOUS，零条=MISSING）
- [file:<路径>]       → os.path.exists（兼容 D:\\ 盘符与 /c/ 形态，允许空格）

退出码（2026-10-12 codex 审计修正——自动流程必须能判失败）：
- 0 = 全部 OK
- 1 = 存在 MISSING 或 AMBIGUOUS
- 2 = 文件中没有任何可识别引用（协议要求 X/U 带 provenance，无引用即不合格）

报告末尾固定注明：本校验只证引用存在，不证证据支持结论；支持力需内容审查。
"""
import argparse
import json
import os
import re
import sqlite3
import sys

DB_URI = "file:C:/Users/14538/.zcode/cli/db/db.sqlite?mode=ro"

CALL_RE = re.compile(r"\[call:([A-Za-z0-9_\-]+)\]")
MSG_RE = re.compile(r"\[msg:([A-Za-z0-9_\-]+)\]")
FILE_RE = re.compile(r"\[file:([^\]]+?)\]")


def norm_path(p):
    """D:\\... 与 /c/... 两种形态归一到本机可 exists 的路径"""
    p = p.strip().strip('"').rstrip("；;，,。")
    if re.match(r"^/[a-zA-Z]/", p):  # /c/Users/... -> C:/Users/...
        p = p[1].upper() + ":" + p[2:]
    return p


def _like_escape(s):
    """LIKE 特义字符转义（codex 审计：call id 里的 _ 是通配符会假阳性）"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def check_call(cur, prefix):
    n = cur.execute(
        "SELECT count(*) FROM part WHERE data LIKE ? ESCAPE '\\'",
        ('%"callID":"' + _like_escape(prefix) + '%',),
    ).fetchone()[0]
    return n


def check_msg(cur, mid):
    if re.fullmatch(r"[A-Za-z0-9_\-]+", mid):
        n = cur.execute("SELECT count(*) FROM message WHERE id LIKE ? ESCAPE '\\'",
                        (_like_escape(mid) + "%",)).fetchone()[0]
    else:
        n = 0
    return n


def verdict(n):
    return "OK" if n == 1 else ("AMBIGUOUS" if n > 1 else "MISSING")


def main():
    ap = argparse.ArgumentParser(description="经验库引用存在性校验（db 只读）")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true",
                    help="机器可读输出（stdout 单行 JSON，人类报告仍打印）")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    db = sqlite3.connect(DB_URI, uri=True)
    cur = db.cursor()

    total = {"OK": 0, "MISSING": 0, "AMBIGUOUS": 0}
    no_ref_files = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        print(f"# {path}")
        seen = set()
        for kind, rx, fn in (
            ("call", CALL_RE, lambda v: check_call(cur, v)),
            ("msg", MSG_RE, lambda v: check_msg(cur, v)),
            ("file", FILE_RE, lambda v: 1 if os.path.exists(norm_path(v)) else 0),
        ):
            for m in rx.finditer(text):
                raw = m.group(1)
                if (kind, raw) in seen:
                    continue
                seen.add((kind, raw))
                if kind == "file":
                    np = norm_path(raw)
                    ok = os.path.exists(np)
                    v = "OK" if ok else "MISSING"
                    print(f"- [{kind}:{raw}] {v} (检查路径: {np})")
                    total[v] += 1
                else:
                    n = fn(raw)
                    v = verdict(n)
                    print(f"- [{kind}:{raw}] {v} (匹配 {n} 条)")
                    total[v] += 1
        if not seen:
            print("- 无任何可识别引用（协议要求 X/U 带 provenance 引用）")
            no_ref_files.append(path)
        print()

    print("# 汇总")
    for k in ("OK", "MISSING", "AMBIGUOUS"):
        print(f"- {k}: {total[k]}")
    if no_ref_files:
        print(f"- NO_REFS: {len(no_ref_files)} 个文件无引用")
    print()
    print("边界注明：本校验只证引用存在，不证证据支持结论；支持力需内容审查。")

    if total["MISSING"] or total["AMBIGUOUS"]:
        code = 1
    elif no_ref_files:
        code = 2
    else:
        code = 0
    if args.json:
        print(json.dumps({"ok": code == 0, "exit_code": code,
                          "OK": total["OK"], "MISSING": total["MISSING"],
                          "AMBIGUOUS": total["AMBIGUOUS"],
                          "no_ref_files": no_ref_files}, ensure_ascii=False))
    sys.exit(code)


if __name__ == "__main__":
    main()
