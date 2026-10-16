# -*- coding: utf-8 -*-
"""
llm.py —— 大模型后端抽象

两种实现共享同一套接口，agent 只认接口不认具体后端：
    choose_skill(query, index)      → 触发决策（对应 ③ 的真实语义匹配）
    generate_lesson(skill)          → 第2步：安排学习
    generate_questions(skill)       → 第3步：出题
    grade(question, answer)         → 判卷
    summarize(correct, total, pass_)→ 第4步：掌握判定与下一步

MockLLM         离线可用，无需 Key（内置入门课程内容）
OpenAICompatLLM 配置 OPENAI_API_KEY 后启用，可接任何 OpenAI 兼容服务
"""

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field


@dataclass
class Question:
    kind: str                 # "choice" | "free"
    prompt: str
    options: list = field(default_factory=list)
    correct: str = ""                 # 单选题：正确选项字母
    expected_groups: list = field(default_factory=list)  # 简答题：命中≥2组算对


class BaseLLM:
    is_live = False

    def choose_skill(self, query, index):        # pragma: no cover
        raise NotImplementedError

    def generate_lesson(self, skill):            # pragma: no cover
        raise NotImplementedError

    def generate_questions(self, skill):         # pragma: no cover
        raise NotImplementedError

    def grade(self, question, answer):           # pragma: no cover
        raise NotImplementedError

    def summarize(self, correct, total, pass_):  # pragma: no cover
        raise NotImplementedError


# ────────────────────────────────────────────────────────────
# 离线模拟：把 SKILL.md 里定义的课程内容与题目“硬编码”进来
# ────────────────────────────────────────────────────────────
class MockLLM(BaseLLM):
    LESSON = (
        "【谷歌 SEO 入门 · 安排学习】\n"
        "A. 关键词研究\n"
        "  · 目标：找出用户会在谷歌输入的搜索词。\n"
        "  · 关键概念：搜索量、竞争度、搜索意图（信息型/导航型/交易型）。\n"
        "  · 例：卖跑鞋 → 种子词‘跑鞋’→ 扩展‘缓震跑鞋 男’等等意图词。\n"
        "B. 站内优化（On-page）\n"
        "  · title/H1 含主关键词并概括页面；\n"
        "  · 正文首段出现主词，H2/H3 分层；\n"
        "  · meta description 吸引点击；图片 alt 描述并适度含词；相关页内链。\n"
    )

    QUESTIONS = [
        Question("choice", "Q1 下列哪项属于‘站内优化 on-page’？\n"
                 "  A.购买外链  B.优化标题 title 标签  C.更换服务器机房  D.投放广告",
                 correct="B"),
        Question("choice", "Q2 分析关键词‘搜索意图’的最主要目的是？\n"
                 "  A.增加页面字数  B.匹配用户需求以提升转化  C.提高服务器速度  D.躲避竞争对手",
                 correct="B"),
        Question("free", "Q3 请说出做好一页‘关键词布局’时，至少应放置关键词的 3 个位置。",
                 expected_groups=[
                     {"title", "标题标签", "标题", "title标签"},
                     {"h1", "h标签", "header", "标题"},
                     {"正文", "首段", "文章", "内容"},
                     {"alt", "图片"},
                     {"meta description", "描述", "description"},
                 ]),
    ]

    def choose_skill(self, query, index):
        from skill_loader import keyword_match
        return keyword_match(query, index)

    def generate_lesson(self, skill):
        return self.LESSON

    def generate_questions(self, skill):
        return list(self.QUESTIONS)

    def grade(self, question, answer):
        ans = (answer or "").strip().lower()
        if question.kind == "choice":
            picked = ans[0] if ans[:1] in ("a", "b", "c", "d") else ans
            ok = picked == question.correct.lower()
            return ok, ("✓ 回答正确" if ok else f"✗ 回答错误，正确答案是 {question.correct}")
        # 简答题：命中期望关键词组数
        hits = sum(1 for g in question.expected_groups if any(k in ans for k in g))
        ok = hits >= 2
        return ok, f"{'✓' if ok else '✗'} 简答命中 {hits} 个要点（title/H标签/正文首段/图片alt/meta描述 等）"

    def summarize(self, correct, total, pass_):
        if pass_:
            return (f"结果：{correct}/{total} 答对 → 判定【已掌握】✅\n"
                    "下一步建议：进阶主题（外链建设 / 技术SEO / 内容策略）。")
        return (f"结果：{correct}/{total} 答对 → 判定【需巩固】📌\n"
                "下一步建议：重讲错题对应模块，再进行一次小测。")


# ────────────────────────────────────────────────────────────
# 真实 LLM：OpenAI 兼容 /chat/completions（纯标准库 urllib 实现）
# ────────────────────────────────────────────────────────────
class OpenAICompatLLM(BaseLLM):
    is_live = True

    def __init__(self):
        self.key = os.environ["OPENAI_API_KEY"]
        self.base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def _chat(self, messages, temperature=0.3) -> str:
        payload = json.dumps({"model": self.model, "messages": messages,
                              "temperature": temperature}).encode("utf-8")
        req = urllib.request.Request(
            self.base + "/chat/completions", data=payload, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.key}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def choose_skill(self, query, index):
        listing = "\n".join(f"- {s.name}: {s.description}" for s in index)
        out = self._chat([
            {"role": "system",
             "content": "根据用户请求，从下列 skill 中选出最匹配的一个，只输出其 name；"
                        "若都不合适则输出 NONE。\n" + listing},
            {"role": "user", "content": query},
        ])
        name = out.strip().splitlines()[0].strip()
        for s in index:
            if s.name.lower() == name.lower():
                return s
        return None

    def generate_lesson(self, skill):
        return self._chat([
            {"role": "system", "content": "严格按以下技能说明的‘安排学习’步骤，"
                                          "用中文给出简洁的分模块讲解：\n" + skill.load_body()},
            {"role": "user", "content": "我想学习谷歌 SEO 入门。"},
        ])

    def generate_questions(self, skill):
        raw = self._chat([
            {"role": "system", "content":
                "依据技能说明的‘三道题测试’，输出 JSON 数组，含 2 道单选(kind=choice,correct=字母)"
                "和 1 道简答(kind=free,expected_groups=二维数组,每组是同义词)。仅输出 JSON。\n"
                + skill.load_body()},
            {"role": "user", "content": "出题。"},
        ])
        try:
            arr = json.loads(re.search(r"\[.*\]", raw, re.S).group(0))
            return [Question(q["kind"], q["prompt"],
                             q.get("options", []), q.get("correct", ""),
                             [set(g) for g in q.get("expected_groups", [])]) for q in arr]
        except Exception:
            return MockLLM().generate_questions(skill)  # 解析失败回退到内置题

    def grade(self, question, answer):
        out = self._chat([
            {"role": "system", "content": "判断考生答案是否正确。只输出 PASS 或 FAIL。\n"
                        f"题目：{question.prompt}\n"
                        f"参考：正确项={question.correct or ''} 要点={question.expected_groups}"},
            {"role": "user", "content": f"考生答案：{answer}"},
        ])
        ok = "PASS" in out.upper()
        return ok, ("✓ 判定正确" if ok else "✗ 判定错误")

    def summarize(self, correct, total, pass_):
        return MockLLM().summarize(correct, total, pass_)


def get_llm() -> BaseLLM:
    """有 OPENAI_API_KEY 就用真实 LLM，否则自动回退到离线模拟。"""
    if os.environ.get("OPENAI_API_KEY"):
        try:
            return OpenAICompatLLM()
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 初始化 LLM 失败，回退离线模式：{e}")
    return MockLLM()
