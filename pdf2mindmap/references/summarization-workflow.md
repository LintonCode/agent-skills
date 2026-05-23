# LLM Summarization Workflow for PDF Chapters

When the text extraction from PDF produces empty or poor-quality content (e.g., only page numbers, no body text), use LLM summarization instead.

## Trigger Conditions
- Extracted chapter content is < 50 chars (indicates TOC-only extraction)
- User explicitly requests summarized/structured output
- Document is academic, legal, or technical (structured learning material)

## Workflow

1. **Extract full chapter text** using PyMuPDF (read all pages in chapter range)
2. **Clean the text**: remove page numbers, footnote markers [n], citation references
3. **Read the full chapter content** as the agent
4. **Generate structured Markdown** using the summarization prompt below
5. **Write the Markdown** to the output file
6. **Generate mindmap HTML** with markmap

## Summarization Prompt Template

```
你是一位专业的读书笔记助手。请阅读以下章节内容，生成结构化的思维导图素材。

要求：
1. 用 Markdown 层级格式输出，# 表示一级标题（章节名），## 表示二级标题（小节名），### 表示三级标题（子小节名）
2. 每个要点前用 ★ 标注重要性：★★★ = 核心概念，★★ = 重要，★ = 补充
3. 用 ◯ 标注需要记忆的关键点
4. 提取核心定义、分类、特征、关系、对比、案例
5. 保持原文的逻辑结构，不要遗漏重要内容
6. 用简洁的语言，适合做成思维导图
7. 只输出 Markdown 内容，不要输出其他说明文字

章节标题：{chapter_title}
章节内容：
{chapter_text}
```

## Example Output Format

```markdown
# 第四章 知识产权的主体

## 一、 主体概述 ★◯
知识产权主体即为各类知识产权的所有人（著作权人、专利权人、商标权人等）。
- **权利角度**：权利所有人
- **法律关系角度**：权利人 + 义务人
- **主体类型**：自然人、法人、非法人组织、国家（一定条件下）

### 主体资格概说 ★◯
- **资格来源**：由国家法律直接规定
- **两大基本原则**：
  - 法律地位平等（人格独立的必要前提）
  - 主体人格独立（地位平等的具体表现）

## 二、 原始主体 ★★★◯
**原始取得含义**：财产权的第一次产生，不依靠原所有人的权利而取得财产权。
```

## Key Principles
- ★ 标记优先级，帮助学习者区分核心概念和补充内容
- ◯ 标记记忆点，对应考试中需要背诵的内容
- 保留原文的逻辑结构（章节→小节→子小节）
- 提取对比、分类、定义等结构化信息
- 语言简洁，适合直接作为思维导图节点
