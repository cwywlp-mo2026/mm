# -*- coding: utf-8 -*-
"""
skill_loader.py —— skill 的“发现 / 索引 / 加载 / 触发”harness

对应概念（见 trigger_demo.py 的 ①②④ 与 ③）：
    discover()        ① 发现：扫描目录收集 SKILL.md
    build_index()     ② 索引：只解析 name + description（轻量，常驻）
    load_body()       ④ 加载：命中后才把正文读进内存
    keyword_match()   ③ 匹配的“离线替身”：无 LLM 时用关键词打分决定触发
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    _body: str = field(default="", repr=False)

    def load_body(self) -> str:
        """④ 加载正文（懒加载：只有用到时才真正读盘）。"""
        if not self._body:
            text = self.path.read_text(encoding="utf-8")
            # 去掉 frontmatter，只留正文说明
            self._body = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.S)
        return self._body


def parse_frontmatter(md_text: str) -> dict:
    """极简 YAML frontmatter 解析（仅顶层 key: value）。"""
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip("'\"")
    return meta


def discover(roots) -> list[Path]:
    """① 发现：在给定根目录下递归查找 SKILL.md。"""
    found = []
    for root in roots:
        root = Path(root)
        if root.exists():
            found.extend(sorted(root.rglob("SKILL.md")))
    return found


def build_index(roots) -> list[Skill]:
    """② 索引：解析每个 skill 的 name + description，正文保持懒加载。"""
    index = []
    for f in discover(roots):
        meta = parse_frontmatter(f.read_text(encoding="utf-8"))
        index.append(Skill(
            name=meta.get("name", f.parent.name),
            description=meta.get("description", ""),
            path=f,
        ))
    return index


# ── ③ 的离线替身：关键词打分匹配 ──────────────────────────
def _tokens(text: str) -> set:
    return set(re.findall(r"[\u4e00-\u9fff]|[A-Za-z]+", text.lower()))


def keyword_match(query: str, index: list[Skill], threshold: float = 1.2):
    """无 LLM 时，用请求与 description 的关键词重合度模拟‘触发决策’。"""
    q = _tokens(query)
    best, best_score = None, 0.0
    for skill in index:
        d = _tokens(skill.description)
        if not d:
            continue
        score = len(q & d) / (len(d) ** 0.4)
        if score > best_score:
            best, best_score = skill, score
    return best if best_score >= threshold else None
