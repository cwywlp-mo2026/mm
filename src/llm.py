# -*- coding: utf-8 -*-
"""
llm.py —— 大模型后端抽象

两种实现共享同一套接口，agent 只认接口不认具体后端：
    choose_skill(query, index)       → 触发决策
    generate_lesson(skill)           → 第2步：安排学习
    generate_questions(skill)        → 第3步：出题（离线=题库随机抽题+乱序）
    grade(question, answer)          → 判卷，返回(对错, 含参考答案/解析的反馈)
    summarize(correct, total, pass_) → 第4步：掌握判定与下一步

MockLLM         离线可用，无需 Key（内置题库，每次随机抽题）
OpenAICompatLLM 配置 OPENAI_API_KEY 后启用，可接任何 OpenAI 兼容服务
"""

import json
import os
import random
import re
import urllib.request
from dataclasses import dataclass, field, replace


@dataclass
class Question:
    kind: str                       # "choice" | "free"
    prompt: str                     # 题干（不含选项）
    options: list = field(default_factory=list)  # 单选题：选项文本列表
    answer: str = ""                # 单选=正确选项文本；简答=参考答案
    expected_groups: list = field(default_factory=list)  # 简答题：命中≥2组算对
    explanation: str = ""           # 解析

    def display(self) -> str:
        """把题目渲染成带 A/B/C/D 选项的文本。"""
        if self.kind == "choice":
            lines = [self.prompt]
            for i, opt in enumerate(self.options):
                lines.append(f"  {chr(65 + i)}. {opt}")
            return "\n".join(lines)
        return self.prompt

    def letter_of(self, text) -> str:
        """正确选项对应的字母。"""
        if text in self.options:
            return chr(65 + self.options.index(text))
        return "?"


class BaseLLM:
    is_live = False

    def choose_skill(self, query, index): ...
    def generate_lesson(self, skill): ...
    def generate_questions(self, skill): ...
    def grade(self, question, answer): ...
    def summarize(self, correct, total, pass_): ...


# ────────────────────────────────────────────────────────────
# 离线模拟：题库 + 随机抽题 + 选项乱序
# ────────────────────────────────────────────────────────────
class MockLLM(BaseLLM):
    LESSON = (
        "【谷歌 SEO 入门 · 安排学习】\n"
        "A. 关键词研究\n"
        "  · 目标：找出用户会在谷歌输入的搜索词。\n"
        "  · 关键概念：搜索量、竞争度、搜索意图（信息型/导航型/交易型）。\n"
        "  · 例：卖跑鞋 → 种子词‘跑鞋’→ 扩展‘缓震跑鞋 男’等意图词。\n"
        "B. 站内优化（On-page）\n"
        "  · title/H1 含主关键词并概括页面；\n"
        "  · 正文首段出现主词，H2/H3 分层；\n"
        "  · meta description 吸引点击；图片 alt 描述并适度含词；相关页内链。\n"
    )

    CHOICE_BANK = [
        Question("choice", "Q 下列哪项属于‘站内优化 on-page’？",
                 ["购买外链", "优化标题 title 标签", "更换服务器机房位置", "投放竞价广告"],
                 answer="优化标题 title 标签",
                 explanation="title/H标签、正文、内链等属于站内；外链与广告属于站外/付费。"),
        Question("choice", "Q 分析关键词‘搜索意图’的最主要目的是？",
                 ["增加页面字数", "匹配用户需求以提升转化", "提高服务器速度", "躲避竞争对手"],
                 answer="匹配用户需求以提升转化",
                 explanation="意图分信息/导航/交易型，匹配意图才能满足需求并提升排名与转化。"),
        Question("choice", "Q 关于 meta description，下列说法正确的是？",
                 ["它直接决定排名高低", "它是搜索结果里的摘要，主要影响点击率",
                  "它必须堆满关键词", "它等同于 H1 标签"],
                 answer="它是搜索结果里的摘要，主要影响点击率",
                 explanation="meta description 一般不直接算排名因子，但影响点击与用户体验。"),
        Question("choice", "Q 以下哪项是‘长尾关键词’的典型特点？",
                 ["搜索量极大、竞争极低", "字数多、意图明确、竞争较小",
                  "全部是品牌词", "只能出现在图片里"],
                 answer="字数多、意图明确、竞争较小",
                 explanation="长尾词搜索量小但转化意图强，是新手起步的好选择。"),
        Question("choice", "Q 给图片添加 alt 属性的主要作用是？",
                 ["让网站打开更快", "描述图片内容，利于图片检索与无障碍",
                  "增加广告收入", "完全替代 title 标签"],
                 answer="描述图片内容，利于图片检索与无障碍",
                 explanation="alt 帮助搜索引擎与屏幕阅读器理解图片，可适度含关键词。"),
    ]

    FREE_BANK = [
        Question("free", "Q 请说出做好一页‘关键词布局’时，至少应放置关键词的 3 个位置。",
                 answer="title 标题、H1/H 标签、正文首段、图片 alt、meta description（任答 3 个）",
                 expected_groups=[
                     {"title", "标题标签", "标题"},
                     {"h1", "h标签", "header", "标签"},
                     {"正文", "首段", "文章", "内容"},
                     {"alt", "图片"},
                     {"meta description", "描述", "description"},
                 ],
                 explanation="关键词应自然分布在标题、正文开头、图片与元信息中，切忌堆砌。"),
        Question("free", "Q 关键词研究通常包含哪几个步骤？",
                 answer="确定种子词 → 扩展相关/长尾词 → 分析搜索量与竞争度 → 按搜索意图与转化价值筛选",
                 expected_groups=[
                     {"种子", "核心词", "初始", "root"},
                     {"扩展", "长尾", "联想", "相关"},
                     {"搜索量", "竞争", "难度", "volume"},
                     {"意图", "转化", "筛选", "价值"},
                 ],
                 explanation="从种子词出发，扩展后按量、竞争、意图筛选出值得做的词。"),
        Question("free", "Q 站内优化（on-page）通常关注哪些方面？",
                 answer="标题 title、H 标签结构、正文内容与关键词布局、图片 alt、内链、URL 与 meta 信息",
                 expected_groups=[
                     {"title", "标题"},
                     {"h1", "h标签", "结构", "层级", "标签"},
                     {"正文", "内容"},
                     {"alt", "图片"},
                     {"内链", "链接"},
                     {"url", "meta", "描述"},
                 ],
                 explanation="站内优化聚焦页面本身可控制的元素。"),
    ]

    def choose_skill(self, query, index):
        from skill_loader import keyword_match
        return keyword_match(query, index)

    def generate_lesson(self, skill):
        return self.LESSON

    def generate_questions(self, skill):
        """随机抽 2 道单选 + 1 道简答，并对单选题选项乱序（答案跟着重排）。"""
        choices = random.sample(self.CHOICE_BANK, 2)
        shuffled = []
        for q in choices:
            opts = q.options[:]
            random.shuffle(opts)
            shuffled.append(replace(q, options=opts))
        free = random.sample(self.FREE_BANK, 1)
        return shuffled + free

    def grade(self, question, answer):
        ans = (answer or "").strip()
        low = ans.lower()
        if question.kind == "choice":
            # 支持“字母”或“选项原文”两种作答
            picked = None
            m = re.match(r"^\s*([A-D])", ans.upper())
            if m and 0 <= ord(m.group(1)) - 65 < len(question.options):
                picked = question.options[ord(m.group(1)) - 65]
            elif ans in question.options:
                picked = ans
            ok = (picked == question.answer)
            if ok:
                return True, f"✓ 回答正确。解析：{question.explanation}"
            return False, (f"✗ 回答错误。正确答案是 {question.letter_of(question.answer)}"
                           f"（{question.answer}）。解析：{question.explanation}")
        # 简答题
        hits = sum(1 for g in question.expected_groups if any(k in low for k in g))
        ok = hits >= 2
        if ok:
            return True, f"✓ 命中 {hits} 个要点，回答到位。解析：{question.explanation}"
        return False, (f"✗ 仅命中 {hits} 个要点。参考答案：{question.answer}。"
                       f"解析：{question.explanation}")

    def summarize(self, correct, total, pass_):
        if pass_:
            return (f"结果：{correct}/{total} 答对 → 判定【已掌握】✅\n"
                    "下一步建议：进阶主题（外链建设 / 技术SEO / 内容策略）。")
        return (f"结果：{correct}/{total} 答对 → 判定【需巩固】📌\n"
                "下一步建议：回看上方错题的【参考答案+解析】，重学对应模块后再测一次。")


# ────────────────────────────────────────────────────────────
# 真实 LLM：OpenAI 兼容 /chat/completions（纯标准库 urllib 实现）
# ────────────────────────────────────────────────────────────
class OpenAICompatLLM(BaseLLM):
    is_live = True

    def __init__(self):
        self.key = os.environ["OPENAI_API_KEY"]
        self.base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def _chat(self, messages, temperature=0.5) -> str:
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
            {"role": "system", "content":
                "根据用户请求，从下列 skill 中选出最匹配的一个，只输出其 name；若都不合适输出 NONE。\n" + listing},
            {"role": "user", "content": query},
        ])
        name = out.strip().splitlines()[0].strip()
        for s in index:
            if s.name.lower() == name.lower():
                return s
        return None

    def generate_lesson(self, skill):
        return self._chat([
            {"role": "system", "content": "严格按以下技能说明的‘安排学习’步骤，用中文给出简洁分模块讲解：\n" + skill.load_body()},
            {"role": "user", "content": "我想学习谷歌 SEO 入门。"},
        ])

    def generate_questions(self, skill):
        raw = self._chat([
            {"role": "system", "content":
                "依据技能说明的‘三道题测试’，出 2 道单选 + 1 道简答，输出 JSON 数组，每个元素字段："
                "kind(choice|free), prompt(题干), options(单选为4个选项文本数组), "
                "answer(单选=正确选项原文/简答=参考答案), expected_groups(简答为同义词二维数组), explanation(解析)。仅输出 JSON。\n"
                + skill.load_body()},
            {"role": "user", "content": "出题。"},
        ])
        try:
            arr = json.loads(re.search(r"\[.*\]", raw, re.S).group(0))
            return [Question(q["kind"], q["prompt"], q.get("options", []),
                             q.get("answer", ""), [set(g) for g in q.get("expected_groups", [])],
                             q.get("explanation", "")) for q in arr]
        except Exception:
            return MockLLM().generate_questions(skill)  # 解析失败回退内置题库

    def grade(self, question, answer):
        out = self._chat([
            {"role": "system", "content":
                "判断考生答案是否正确。第一行只输出 PASS 或 FAIL，第二行给一句简短解析。\n"
                f"题目：{question.display()}\n参考：{question.answer}"},
            {"role": "user", "content": f"考生答案：{answer}"},
        ])
        ok = "PASS" in out.upper()
        reason = out.splitlines()[1].strip() if len(out.splitlines()) > 1 else question.explanation
        return ok, (f"{'✓ 正确' if ok else '✗ 有误'}。{reason}")

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
