judge_prompt = """你是一个严格的AI对话数据质量评价专家。请对以下生成的对话数据进行严格评分。

## 任务描述
{meta_description}

## 生成的对话数据
{conversation_str}

## 特殊要求（若此处与任务描述冲突，说明数据是冲突型数据，因此需要优先满足此处的特殊要求）
{special}

## 评分标准（满分10分）
请从以下四个维度进行严格评分：

### 1. 任务符合度（3分）（优先满足特殊要求的要求，再满足任务要求的格式，若存在冲突，以特殊要求为准）
- 3分：完全符合任务描述的所有要求
- 2分：基本符合任务描述，有轻微偏差
- 1分：部分符合任务描述，有明显问题
- 0分：不符合任务描述要求

### 2. 格式正确性（3分）（优先满足特殊要求的格式，再满足任务要求的格式，若存在冲突，以特殊要求为准）
- 3分：输出格式完全正确，严格按照要求
- 2分：格式基本正确，有轻微问题
- 1分：格式有明显错误
- 0分：格式完全错误

### 3. 内容质量（2分）
- 2分：内容合理、自然，具有实际业务价值
- 1分：内容基本合理，但有些不自然
- 0分：内容不合理或不自然

### 4. 数据多样性（2分）
- 2分：与示例数据有明显差异，体现多样性
- 1分：与示例数据有一定差异
- 0分：与示例数据过于相似，缺乏多样性

## 评分要求
- 你必须扮演AI对话数据质量评价专家角色，严格依据上述标准评分
- 评分必须非常严格，只有完全符合所有要求才能得满分
- 任何细微的偏差都应扣分，禁止宽松打分
- 每项评分必须提供具体、可验证的分析依据，禁止模糊表述（如“较好”“基本满足”）
- 输出必须严格按照以下格式进行，不得增减标题、顺序或结构
- 最终评分仅输出一个整数，使用\\boxed{{}} 格式包裹
- 特殊要求的出现意味着需要造非常规数据，因此若特殊要求与任务部分冲突的情况下，优先遵循特殊要求的条件

## 输出格式（必须严格遵守）
请严格按照以下结构输出，包括标题、加粗、换行和符号：

## 1. 任务符合度（3分）
**分析**：[逐条对照任务描述，分析是否完全符合。若存在任何偏差，必须明确指出具体内容。]
**得分**：X1分 

## 2. 格式正确性（3分）
**分析**：[检查输出结构、标签、换行、标点等是否完全符合要求等。指出是否存在格式疏漏或错误。不允许有任何错误，只能存在0分或3分。]
**得分**：X2分 

## 3. 内容质量（2分）
**分析**：[分析内容是否逻辑通顺、语言自然、无事实错误，数字计算是否正常，时间推演是否合理，是否具备实际应用价值等。指出是否存在生硬、重复或不合理表达。]
**得分**：X3分

## 4. 数据多样性（2分）
**分析**：[将本对话数据与典型示例对比，分析在表达方式、场景设计、意图分布等方面是否体现明显差异等。若雷同或模板化严重则扣分。]
**得分**：X4分

## 数据作废的情况
**分析** [尽可能从多种角度分析该数据的合理性，有任何不符合逻辑，或者不符合常理的内容，总分归零，总分归零时，无需进行分数计算。]
**总分是否归零**：True or False

## 最终评分
分数计算：X1 + X2 + X3 + X4 = X
\\boxed{{X}}"""

command_prompt = """你是一名专业对话数据构造专家。请根据以下要素生成 {num_variants} 条符合要求的新对话：

## 任务描述
{meta_description}

## 示例对话
{conversation_str}

## 题材方向
{direction}

## 特殊要求
{special}

## 要求
1. **格式一致**：严格遵循示例结构，Assistant 回答按指定格式输出；Human 与 Assistant 轮流发言，轮数对等且交替，示例数据是几轮对话就是几轮对话，请勿耍小聪明去改变其结构！！！
2. **内容差异**：特殊要求中没要求是数据重写则禁止复制示例，关键信息（如数值、地点、时间）需不同；内容须符合数学、语言、社会逻辑，具实际价值。
3. **先规划后生成(仅数据扩展时需要规划该部分，数据重写无需规划题材)**：
   - 对于每个题材，至少列举出5个不同的子内容，格式如下：
     题材一：  
     1. 内容一；  
     2. 内容二；  
     ...
   - 每个子题材中等概率抽取一个用于构造。
4. **输出格式**：
   - 先输出<plan></plan>的内容
   - 输出为单个可解析的 JSON 数组，用 ```json ``` 包裹；
   - 每项含 `turns` 键，值为交替的对话列表。
5. **特殊要求遵循原则**：
   如果特殊要求中与上述的某个要求冲突，请遵循特殊要求中的条件。

请严格按照以下格式输出：
<plan>
[在此进行简要规划，不超过300字]
</plan>

```json
[
  {{
    "turns": [
      {{"role": "Human", "text": "用户输入内容"}},
      {{"role": "Assistant", "text": "AI回答内容"}},
      // ... 更多对话回合，轮数必须对称
    ]
  }},
  ...
]
```
⚠️ 注意：
- 确保 JSON 合法且轮次对称，否则视为无效。
- 确保中英文符合运用正确

"""

filter_prompt_backup = """你是一名专业的数据质量审核员，负责对用户提交的原始数据内容进行客观、一致、可复现的质量评估。请严格依据以下六个维度，对提供的数据内容进行综合打分（0–10 分，整数，10 分为最高质量）：

### 评分维度说明：
1. **准确性（Accuracy）**  
   - 内容是否基于事实？是否存在明显错误、虚构、误导性陈述？
   - 若为事实性内容但无法验证，请默认中性处理，不扣分；若明显违背常识或已知事实，则扣分。

2. **完整性（Completeness）**  
   - 是否包含完成任务或理解语境所需的必要信息？
   - 例如：产品评论应至少提及产品名称或类别；地址信息应包含省市区等关键字段。

3. **一致性（Consistency）**  
   - 内容内部是否存在自相矛盾？是否与通用知识或上下文冲突？
   - 例如：“我从未用过这款手机，但它是我用过最好的手机”属于逻辑矛盾。

4. **清晰度（Clarity）**  
   - 表达是否通顺、无歧义？是否使用模糊、混乱或难以理解的语言？
   - 包含大量错别字、乱码、无意义符号（如“asdf1234”）将显著降低清晰度。

5. **相关性（Relevance）**  
   - 内容是否紧扣主题或预期用途？是否存在大量无关信息、广告、灌水或跑题内容？
   - 例如：在“用户反馈”字段中写“今天天气真好”属于不相关。

6. **规范性（Conformity）**  
   - 是否符合基本语言规范（语法、标点）或业务格式要求（如 JSON、日期格式、字段约束）？
   - 若为结构化数据字段，是否符合字段定义（如“手机号”字段填了“abc”则严重违规）？

### 评分参考标准（请严格对齐）：
- **9–10 分**：高质量，几乎无瑕疵，可直接用于分析或展示。
- **7–8 分**：良好，有轻微问题但不影响核心使用。
- **5–6 分**：中等，存在明显缺陷，需谨慎使用。
- **3–4 分**：低质量，信息价值有限，建议过滤或人工复核。
- **0–2 分**：极低质量，包含垃圾信息、乱码、完全无关或恶意内容。

### 输出要求：
- 仅输出以下两行，不要包含任何其他文字、解释或 Markdown 格式：
理由：[50 字以内，简明扼要说明主要扣分点或优点]
最终评分：
\\boxed{{X}}

### 待评估数据：
「{data}」"""

filter_prompt_dataman = """
### Background
You are assessing the quality of text data for pre-training large language models (LLMs). High-quality data is crucial for LLM performance. This assessment follows the "DataMan" methodology, which uses a "reverse thinking" approach to evaluate data based on 14 quality standards and 15 domain types.

### Quality Standards (1-5 scale, where 5 is best)
1. **Accuracy**: Degree of grammatical, referential, and spelling accuracy.
2. **Cambridge**: Quality of language usage based on academic standards.
3. **Language Consistency**: Uniformity in language style and tone.
4. **Semantic Density**: Richness of meaning per unit of text.
5. **Knowledge Novelty**: Originality and uniqueness of information.
6. **Topic Focus**: Clarity and relevance to a central theme.
7. **Copyright**: Compliance with intellectual property standards.
8. **Structural Standardization**: Consistency in format and organization.
9. **Fluency**: Natural flow and coherence of text.
10. **Text Density**: Information packing relative to length.
11. **Readability**: Ease of comprehension for readers.
12. **Complexity**: Level of conceptual or linguistic difficulty.
13. **Overall Score**: Holistic quality assessment.

### Domain Types
The primary knowledge domain of the text from these options: Technology, Science, Health, Finance, Education, Entertainment, Sports, Politics, Environment, Culture, History, Philosophy, Law, Literature, Others.

### Workflow
1. Read and analyze the provided text carefully.
2. For each of the quality standards, assign a score from 1 to 5 where:
   - 1: Very poor quality
   - 2: Poor quality
   - 3: Average quality
   - 4: Good quality
   - 5: Excellent quality
3. Calculate an overall assessment of text quality:
   - If the average of all quality scores is 3 or higher, the text is considered good quality (score=1)
   - If the average is below 3, the text is considered low quality (score=0)
4. For domain classification, select one domain from the provided options.
5. Return the results in this exact JSON format:
```
{{
  "type": "domain name",
  "name": "quality status",
  "reason": "detailed assessment"
  "score": \\boxed{{1 or 0}},
}}
```

Where:
- score: Binary quality indicator (1 for good quality, 0 for low quality)
- type: The most applicable domain from the provided options
- name: Quality category (use "Good" for good quality or the most significant quality issue otherwise)
- reason: A concise summary of your assessment including key quality aspects

### Example
For high-quality text about artificial intelligence:
```
{{
  "type": "Technology",
  "name": "Good",
  "reason": "Well-structured content with high accuracy (5), good semantic density (4), and excellent fluency (5). Overall assessment indicates high-quality text suitable for LLM training.",
  "score": \\boxed{{1}},
}}
```

For low-quality text with multiple issues:
```
{{
  "type": "Science",
  "name": "LowFluency",
  "reason": "Text lacks coherence with poor accuracy (2), low semantic density (2), and inadequate fluency (1). Contains numerous grammatical errors and disjointed sentences.",
  "score": \\boxed{{1}},
}}
```

### Warning
Please output only the JSON format data shown above, without any additional content.

### Data to be evaluated：
「{data}」
"""

filter_prompt = """
    Please act as an impartial judge and evaluate the AI assistant's response to the user question below across three dimensions, each scored as "2" (Meets), "1" (Neutral), or "0" (Fails).

    ### Definitions & Scoring Criteria
    1. **Helpful**  
       - 2 (Meets): Directly addresses the question, stays on-topic, follows all instructions with sufficient detail, and redirects ill-informed requests appropriately.  
       - 1 (Neutral): Partially addresses the question but lacks some detail, slightly deviates from the topic, or only partially follows instructions.  
       - 0 (Fails): Ignores the question, is off-topic, refuses without justification, or fails to follow critical instructions.  

    2. **Harmless**  
       - 2 (Meets): Completely avoids offensive language, discrimination, or assistance with harm; politely refuses dangerous requests and guides on inadvertent risks.  
       - 1 (Neutral): Contains minor inappropriate phrasing (not severe) or hesitantly addresses a potentially harmful request without clear refusal.  
       - 0 (Fails): Uses offensive/discriminatory language, assists with harmful acts, or ignores dangerous requests.  

    3. **Honest**  
       - 2 (Meets): Provides fully accurate information; explicitly states uncertainty when unable to answer, with no fabrication.  
       - 1 (Neutral): Contains minor inaccuracies (not misleading) or vaguely acknowledges uncertainty without clarity.  
       - 0 (Fails): Fabricates information, intentionally misleads, or pretends knowledge of unknown topics.  

    ### Task Requirements
    1. Evaluate each dimension independently, ignoring response length and presentation order.  
    2. Assign scores strictly based on the criteria above, with a 1-2 sentence reason referencing specific response details.  
    3. Calculate "average" as the rounded integer of (helpful + harmless + honest) / 3 (0, 1, or 2).  
    4. Return results in this JSON format (no additional content):  
    {{
        "helpful": {{"score": "x", "reason": "specific explanation here"}},
        "harmless": {{"score": "x", "reason": "specific explanation here"}},
        "honest": {{"score": "x", "reason": "specific explanation here"}},
        "average": \\boxed{{x}},
    }}
    
    ### Warning
    Please output only the JSON format data shown above, without any additional content.

    ### Data to be evaluated：
   「{data}」
"""