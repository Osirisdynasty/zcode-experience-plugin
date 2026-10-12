# -*- coding: utf-8 -*-
"""query.py — 按 goal 文本确定性检索经验条目（只读 lessons/*.md，不调 LLM）。

用法: python query.py "<goal 文本>" [--top N]

打分维度：
- 已知名片段映射：goal 中出现的关键名（人名/系统名/域词）展开为同域实体集
- 实体命中 tags（+3）、system/project（+3）、适用条件/建议正文（+2）
- CJK bigram 与 lessons 正文重叠（+1/个，封顶 5）
goal 距离判定：
- hit    得分 >= 3（实体级命中）
- suspect 仅 bigram 弱重叠（1-2 分，无实体命中）
- drop   与 goal 实体零交集
"""
import argparse
import glob
import os
import re
import sys

LESSONS_DIR = "C:/Users/14538/.zcode/experience/lessons"

# 已知名片段 -> 同域实体展开（源自试点证据：夏洛特=CowAgent/comfytext 域）
# 两级划分（2026-10-12 codex 审计修正）：
# - DOMAIN：域词（系统名/机制名），命中给实体资格
# - GENERIC：泛词（动作/通用词，如「验证」「编码」「施工」），只进 bigram
#   弱重叠池，不展开实体、不给命中资格——否则「帮我验证诗歌的编码」会
#   把整个代码域灌进实体集，误召回变量遮蔽类经验。
DOMAIN_FRAGMENTS = {
    "夏洛特": ["夏洛特", "charlotte", "cowagent", "comfytext"],
    "charlotte": ["charlotte", "夏洛特", "cowagent", "comfytext"],
    "comfytext": ["comfytext"],
    "cowagent": ["cowagent", "牛子", "工人"],
    "zcode": ["zcode"],
    "监工": ["监工", "轮询", "工人", "flow_monitor", "ct_bridge", "产物"],
    "接口": ["接口", "api", "端点", "web_channel"],
    "波次": ["波次", "wave", "build"],
    "契约": ["契约", "contract", "profile", "编译"],
    "工场": ["工场", "workshop", "bot", "派工", "群聊"],
    "蓝图": ["蓝图", "plan", "图纸", "dag", "流程图"],
    "e2e": ["e2e", "端到端", "真模型"],
    "真模型": ["真模型", "e2e", "端到端", "llm"],
    "可重入": ["可重入", "幂等", "重跑", "租约"],
    "回执": ["回执", "receipt", "送达"],
}
GENERIC_FRAGMENTS = {"验证", "编码", "施工", "测试", "改动", "重构"}
RETIRED_STATUS = {"retired", "rejected", "superseded"}

SECTION_RE = re.compile(r"\*\*适用条件\*\*：(.+?)(?=\n\n|\Z)", re.S)
SECTION_RE2 = re.compile(r"\*\*建议\*\*：(.+?)(?=\n\n|\Z)", re.S)
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), text[m.end():]
    fm = {}
    for line in fm_raw.splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
        fm[k.strip()] = v
    return fm, body


def goal_entities(goal):
    """goal -> (域实体集, 泛词bigram池, 分段)。

    域词（DOMAIN_FRAGMENTS）展开为实体并具备命中资格；泛词
    （GENERIC_FRAGMENTS）只折进 bigram 池贡献弱重叠分，绝不展开实体。
    """
    ents = set()
    weak = set()
    segs = re.findall(r"\S+", goal)
    for s in segs:
        sl = s.lower()
        in_generic = any(g in sl for g in GENERIC_FRAGMENTS)
        ents.add(sl)
        for frag, mapped in DOMAIN_FRAGMENTS.items():
            if frag.lower() in sl:
                ents.update(m.lower() for m in mapped)
        if in_generic:
            weak.add(sl)
    ents -= {g for g in GENERIC_FRAGMENTS}
    return ents, weak, segs


def cjk_bigrams(s):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1) if re.search(r"[\u4e00-\u9fff]", s[i:i + 2])}


def load_lessons():
    lessons = []
    for path in sorted(glob.glob(os.path.join(LESSONS_DIR, "*.md"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        fm, body = parse_frontmatter(text)
        if str(fm.get("status", "")).lower() in RETIRED_STATUS:
            continue    # retired/rejected/superseded 不再召回（codex 审计 #3）
        title_m = re.search(r"^# .*?·\s*(.+)$", body, re.M)
        cond_m = SECTION_RE.search(body)
        adv_m = SECTION_RE2.search(body)
        lessons.append({
            "file": os.path.basename(path),
            "id": fm.get("id", "?"),
            "version": fm.get("version", "?"),
            "status": fm.get("status", "?"),
            "system": fm.get("system", ""),
            "project": fm.get("project", ""),
            "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
            "title": title_m.group(1).strip() if title_m else "",
            "cond": cond_m.group(1) if cond_m else "",
            "advice": adv_m.group(1) if adv_m else "",
        })
    return lessons


def score_lesson(ls, ents, goal_bgs):
    hits = []  # (位置, 命中内容, 分值)
    score = 0
    for tag in ls["tags"]:
        tl = tag.lower()
        if any(e and (e in tl or tl in e) for e in ents):
            hits.append(("tags", tag, 3))
            score += 3
    for field in ("system", "project"):
        v = str(ls[field]).lower()
        if v and any(e and (e in v or v in e) for e in ents):
            hits.append((field, ls[field], 3))
            score += 3
    for field, body in (("适用条件", ls["cond"]), ("建议", ls["advice"])):
        bl = body.lower()
        matched = [e for e in ents if len(e) >= 2 and e in bl]
        if matched:
            hits.append((field, "/".join(matched[:4]), 2))
            score += 2
    corpus_bgs = cjk_bigrams(" ".join([ls["title"], ls["cond"], ls["advice"], " ".join(ls["tags"])]))
    bg_overlap = goal_bgs & corpus_bgs
    if bg_overlap:
        bg_pts = min(len(bg_overlap), 5)
        hits.append(("bigram重叠", " ".join(sorted(bg_overlap)[:6]), bg_pts))
        score += bg_pts
    return score, hits


def judge(score, has_entity_hit):
    """hit 必须有实体级命中（tags/system/project/适用条件/建议），
    纯 bigram 重叠再高分也只是 suspect（codex 审计：bigram 项分值 2-5，
    旧判定 h[2]>=2 会把纯词面重叠当实体命中）。"""
    if score >= 3 and has_entity_hit:
        return "hit"
    if score > 0:
        return "suspect"
    return "drop"


def main():
    ap = argparse.ArgumentParser(description="经验条目确定性检索（只读 lessons/*.md）")
    ap.add_argument("goal")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    ents, weak, segs = goal_entities(args.goal)
    goal_bgs = cjk_bigrams(args.goal)

    print(f"# 经验检索：{args.goal}")
    print(f"- goal 分段: {segs}")
    print(f"- 展开实体({len(ents)}): {sorted(ents)}")
    if weak:
        print(f"- 泛词降级(仅弱重叠): {sorted(weak)}")
    print()

    lessons = load_lessons()
    results = []
    for ls in lessons:
        score, hits = score_lesson(ls, ents, goal_bgs)
        has_entity = any(h[0] != "bigram重叠" for h in hits)
        results.append((score, ls, hits, judge(score, has_entity)))

    results.sort(key=lambda x: -x[0])
    shown = 0
    for score, ls, hits, j in results:
        if shown >= args.top:
            break
        shown += 1
        reason = {"hit": "实体级命中，进入对照",
                  "suspect": "仅词面弱重叠，需人工判断",
                  "drop": "与 goal 实体零交集"}[j]
        print(f"## {ls['id']}@v{ls['version']} [{j}] 得分 {score} — {ls['title']}")
        print(f"- status: {ls['status']} | system: {ls['system']} | project: {ls['project']}")
        for loc, what, pts in hits:
            print(f"  - +{pts} [{loc}] {what}")
        print(f"- 判定: {reason}")
        print()

    n_hit = sum(1 for r in results if r[3] == "hit")
    n_sus = sum(1 for r in results if r[3] == "suspect")
    n_drop = sum(1 for r in results if r[3] == "drop")
    print(f"# 汇总: {len(results)} 条经验 | hit {n_hit} / suspect {n_sus} / drop {n_drop}")


if __name__ == "__main__":
    main()
