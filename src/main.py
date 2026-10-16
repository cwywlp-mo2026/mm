# -*- coding: utf-8 -*-
"""
main.py —— 命令行入口

用法：
    python src/main.py                       # 交互：输入你的诉求，逐题作答
    python src/main.py --demo                # 免输入，用预置答案跑通全流程（验证用）
    python src/main.py --query "我想学谷歌SEO"
    python src/main.py --list                # 只列出已发现/索引的 skills

模式：默认离线模拟可直接运行；设置环境变量 OPENAI_API_KEY 后自动切换为真实 LLM。
"""

import argparse
import os
import sys

# 保证从任意目录运行时都能 import 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 控制台默认 GBK，无法编码 ✓/✅ 等字符；统一切到 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from llm import get_llm  # noqa: E402
from skill_loader import build_index  # noqa: E402
from agent import SEOAgent  # noqa: E402

DEFAULT_SKILLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")


def make_demo_answer_source(answers):
    it = iter(answers)
    return lambda: next(it)


def main():
    parser = argparse.ArgumentParser(description="谷歌 SEO 学习 Agent（skill 驱动）")
    parser.add_argument("--query", default="我想学习谷歌 SEO", help="用户诉求")
    parser.add_argument("--skills-dir", default=DEFAULT_SKILLS_DIR, help="skill 根目录")
    parser.add_argument("--demo", action="store_true", help="用预置答案免交互跑通")
    parser.add_argument("--list", action="store_true", help="只列出发现的 skills")
    args = parser.parse_args()

    index = build_index([args.skills_dir])

    if args.list:
        print(f"[discover] 在 {args.skills_dir} 索引到 {len(index)} 个 skill：\n")
        for s in index:
            print(f"  - {s.name}: {s.description[:60]}...")
        return

    llm = get_llm()
    agent = SEOAgent(llm, index)

    if args.demo:
        # 预置：Q1 答对 B、Q2 答对 B、Q3 答对（含 title/正文/alt 三个要点）
        answers = ["B", "B", "要放在 title 标题、正文首段，还有图片 alt 里"]
        source = make_demo_answer_source(answers)
        agent.run(args.query, source)
    else:
        def source():
            return input("你的回答：").strip()
        agent.run(args.query, source)


if __name__ == "__main__":
    main()
