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


def demo_answer(q):
    """demo：单选题自动选正确答案；简答题故意只答一点，用来演示错题会打印参考答案+解析。"""
    if q.kind == "choice":
        ans = q.letter_of(q.answer)
    else:
        ans = "title 标题"
    print(f"你的回答：{ans}")
    return ans


def main():
    parser = argparse.ArgumentParser(description="谷歌 SEO 学习 Agent（skill 驱动）")
    parser.add_argument("--query", default="我想学习谷歌 SEO", help="用户诉求")
    parser.add_argument("--skills-dir", default=DEFAULT_SKILLS_DIR, help="skill 根目录")
    parser.add_argument("--demo", action="store_true", help="自动作答，免交互跑通")
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
        agent.run(args.query, demo_answer)
    else:
        def interactive(q):
            return input("你的回答：").strip()
        agent.run(args.query, interactive)


if __name__ == "__main__":
    main()
