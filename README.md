# SEO Learner —— 一个“被 skill 驱动”的学习程序

这个项目把 **谷歌 SEO 入门学习** 做成一个由 [Agent Skill](skills/seo-tutor/SKILL.md) 驱动的命令行程序，
用来演示一个核心问题：**skill 到底是什么、如何在程序里被“发现 / 触发 / 加载 / 执行”**。

skill 的工作流：**检测用户要学习 → 安排学习 → 三道题测试 → 判定掌握并给出下一步**。

## 一、它是怎么工作的（5 步链路）

```
用户输入“我想学习谷歌 SEO”
        ↓
① 发现   扫描 skills/ 目录收集所有 SKILL.md            ← 真代码 skill_loader.discover()
② 索引   只解析每个 skill 的 name + description         ← 真代码 build_index()
③ 触发   由 LLM(或离线关键词打分)决定启用哪个 skill     ← llm.choose_skill()
④ 加载   读取命中 skill 的 SKILL.md 正文，喂给大模型     ← skill.load_body()
⑤ 执行   大模型按说明书：讲解 → 出题 → 判卷 → 给结果     ← agent.run()
```

> 关键点：**索引常驻、正文按需**。skill 本质是喂给大模型的“说明书文本”，
> 不是可被 `import` 的函数。真正被计算机执行的只有文件扫描/解析/读取，
> 以及“决定用哪个 skill、按说明书出题判卷”这些由大模型完成的推理。

## 二、两种运行模式（同一套代码）

| 模式 | 触发条件 | 说明 |
|------|----------|------|
| **离线模拟**（默认） | 无需任何 Key | 用内置课程内容跑通全流程，开箱即用 |
| **真实 LLM** | 设置 `OPENAI_API_KEY` | 出题/判卷改由大模型完成，可接任意 OpenAI 兼容服务 |

程序启动时自动判断：有 `OPENAI_API_KEY` 就走真实 LLM，否则回退离线模拟。

## 三、快速开始

```bash
# 1) 查看被“发现/索引”到的 skills
python src/main.py --list

# 2) 免交互跑通完整流程（内置示例答案：全对）
python src/main.py --demo

# 3) 交互模式：逐题作答
python src/main.py --query "我想学习谷歌 SEO"
```

### 启用真实 LLM（可选）

PowerShell：
```powershell
$env:OPENAI_API_KEY = "sk-你的密钥"
$env:OPENAI_MODEL   = "gpt-4o-mini"        # 可选
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"  # 可选，兼容其它服务商
python src/main.py --demo
```

## 四、目录结构

```
seo-learner/
├── skills/seo-tutor/SKILL.md   # ← 灵魂：教学 skill（说明书）
├── src/
│   ├── skill_loader.py         # ①②④ 发现 / 索引 / 加载 harness
│   ├── llm.py                  # ③⑤ 大模型后端：MockLLM + OpenAICompatLLM
│   ├── agent.py                # 编排：触发 skill 并跑完教学+测试闭环
│   └── main.py                 # 命令行入口
├── requirements.txt            # 纯标准库，无需安装
├── .env.example                # 真实 LLM 的可选配置样例
└── README.md
```

## 五、想加自己的 skill？

在 `skills/` 下新建一个文件夹，写一份带 frontmatter 的 `SKILL.md` 即可，
程序下次运行会自动“发现 / 索引”它——无需改任何代码，也无需注册。

```markdown
---
name: my-new-skill
description: 说明【做什么】+【什么时候用】，第三人称、含触发词。
---
# 正文：给 Agent 的分步指令
```

## 六、运行环境

- Python 3.10+（本项目在 3.13 验证通过）
- 无第三方依赖；`requirements.txt` 仅作说明。
