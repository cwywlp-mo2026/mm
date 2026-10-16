# -*- coding: utf-8 -*-
"""
agent.py —— 迷你 Agent：把 skill 真正“跑”起来

一个完整对话回合经历（对应前 5 步机制）：
    发现/索引  → build_index()
    触发决策   → llm.choose_skill()
    加载正文   → skill.load_body()（在生成/出题时才发生）
    执行说明书 → generate_lesson / generate_questions / grade / summarize
"""

from typing import Callable, Optional


class SEOAgent:
    def __init__(self, llm, index):
        self.llm = llm
        self.index = index

    # ── 触发：决定这次要不要用某个 skill ──────────────
    def trigger(self, query: str):
        return self.llm.choose_skill(query, self.index)

    # ── 运行教学闭环 ────────────────────────────────
    # answer_source: 一个返回下一次用户作答的函数（交互模式=input，demo=预置队列）
    def run(self, query: str, answer_source: Callable[[], str],
            echo: Optional[Callable[[str], None]] = None):
        echo = echo or print
        mode = "真实 LLM" if self.llm.is_live else "离线模拟"
        echo(f"[mode] {mode}")
        echo(f"[user] {query}")

        skill = self.trigger(query)
        if skill is None:
            echo("\n未命中任何 skill → 用通用方式回答（这里没有实现闲聊，仅演示触发）。")
            return None

        echo(f"\n[trigger] 命中 skill：{skill.name}  ({skill.path})")
        echo(f"[load]    读取 SKILL.md 正文 {len(skill.load_body())} 字符")

        echo("\n" + self.llm.generate_lesson(skill))

        echo("\n———— 三道题测试 ————")
        questions = self.llm.generate_questions(skill)
        correct = 0
        for q in questions:
            echo("\n" + q.prompt)
            ans = answer_source()
            echo(f"> 你的回答：{ans}")
            ok, feedback = self.llm.grade(q, ans)
            correct += int(ok)
            echo(feedback)

        pass_ = correct >= 2
        echo("\n———— 结果 ————")
        echo(self.llm.summarize(correct, len(questions), pass_))
        return {"skill": skill.name, "correct": correct, "total": len(questions), "pass": pass_}
