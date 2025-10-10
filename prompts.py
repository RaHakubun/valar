"""
LLM提示词定义
参考ComfyBench的multi-agent架构，设计片段-需求匹配提示词
"""

# ============================================================================
# 需求分解提示词
# ============================================================================

NEED_DECOMPOSITION_PROMPT = """你是一个ComfyUI工作流专家。请将用户的需求分解为原子需求列表。

用户需求: {user_request}

分解规则：
1. 每个原子需求应该是一个独立的、不可再分的功能单元
2. 明确描述要实现什么功能
3. 指定类别（generation/editing/upscaling/style_transfer等）
4. 指定模态（image/video/3d）
5. 标注依赖关系（如果需要前一个需求的输出）
6. 提取约束条件（如风格、尺寸、模型等）

输出JSON格式：
{{
    "atomic_needs": [
        {{
            "need_id": "need_1",
            "description": "生成粘土风格的人物肖像",
            "category": "generation",
            "modality": "image",
            "priority": 10,
            "dependencies": [],
            "constraints": {{
                "style": "clay",
                "subject": "portrait",
                "model": "flux"
            }}
        }},
        {{
            "need_id": "need_2",
            "description": "将图像进行4倍超分辨率处理",
            "category": "upscaling",
            "modality": "image",
            "priority": 5,
            "dependencies": ["need_1"],
            "constraints": {{
                "scale": 4
            }}
        }}
    ]
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 工作流意图提取提示词
# ============================================================================

WORKFLOW_INTENT_EXTRACTION_PROMPT = """你是一个ComfyUI工作流专家。请分析以下工作流，提取其意图和功能。

工作流代码:
{workflow_code}

工作流节点类型: {node_types}

请提取：
1. 主要任务类型（如text-to-image, image-to-image, upscaling等）
2. 模态（image/video/3d）
3. 风格（如有，如anime, realistic, clay等）
4. 操作类型（generation/editing/upscaling/style_transfer）
5. 关键词列表（用于检索）
6. 自然语言描述（一句话概括工作流功能）

输出JSON格式：
{{
    "task": "text-to-image",
    "modality": "image",
    "style": "clay",
    "operation": "generation",
    "keywords": ["文本生成图像", "粘土风格", "人物", "Flux模型"],
    "description": "使用Flux模型生成粘土风格的人物图像"
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 代码拆分提示词（核心创新）
# 参考ComfyBench的思路，但适配我们的检索-拼接范式
# ============================================================================

CODE_SPLITTING_PROMPT = """你是一个ComfyUI工作流专家。请将完整的工作流代码拆分为功能片段。

完整工作流代码:
{workflow_code}

拆分规则：
1. 每个片段应该是一个完整的功能单元（如"文本编码"、"图像生成"、"超分辨率"）
2. 片段之间通过变量传递数据
3. 识别片段的输入和输出类型
4. 保持片段的可复用性

常见的功能边界：
- 模型加载（CheckpointLoader, LoraLoader等）
- 文本编码（CLIPTextEncode）
- 图像初始化（EmptyLatentImage, LoadImage）
- 采样生成（KSampler）
- 图像解码（VAEDecode）
- 后处理（Upscale, ImageScale等）
- ControlNet应用
- 风格迁移

输出JSON格式：
{{
    "fragments": [
        {{
            "fragment_id": "frag_1",
            "description": "加载Flux模型和CLIP",
            "category": "model_loading",
            "code": "model, clip, vae = CheckpointLoaderSimple(ckpt_name=\\"flux_dev.safetensors\\")",
            "inputs": {{}},
            "outputs": {{
                "MODEL": "model",
                "CLIP": "clip", 
                "VAE": "vae"
            }}
        }},
        {{
            "fragment_id": "frag_2",
            "description": "CLIP文本编码",
            "category": "text_encoding",
            "code": "conditioning = CLIPTextEncode(clip=clip, text=\\"{{prompt}}\\")",
            "inputs": {{
                "CLIP": "clip",
                "STRING": "text"
            }},
            "outputs": {{
                "CONDITIONING": "conditioning"
            }}
        }}
    ]
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 片段功能描述生成（辅助）
# ============================================================================

FRAGMENT_DESCRIPTION_PROMPT = """你是ComfyUI工作流专家。请分析以下代码片段，生成简洁的功能描述。

代码片段:
{code_fragment}

请简洁回答（一句话）：
1. 这个代码片段的主要功能是什么？
2. 输入数据类型有哪些？（如IMAGE, TEXT, MODEL, CONDITIONING等）
3. 输出数据类型是什么？

输出JSON格式：
{{
    "function": "使用CLIP模型对文本进行编码",
    "inputs": ["CLIP", "STRING"],
    "outputs": ["CONDITIONING"]
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 片段-需求匹配判断（核心）
# 这里的关键是"满足意图"而非"语义相似"
# ============================================================================

FRAGMENT_NEED_MATCHING_PROMPT = """你是ComfyUI工作流专家。请判断给定的代码片段是否能够满足用户的原子需求。

用户的原子需求:
描述: {need_description}
类别: {need_category}
模态: {need_modality}
约束条件: {need_constraints}

候选代码片段:
{code_fragment}

片段功能: {fragment_function}

评判标准（重要）：
1. **功能意图是否一致**（最重要，权重70%）
   - 片段是否能实现需求描述的功能？
   - 不需要完全相同，只要能达到目标即可
   - 例如：需求是"生成图像"，KSampler可以满足

2. **输入输出类型是否匹配**（权重20%）
   - 片段的输入能否从上下文获得？
   - 片段的输出是否是需求期望的类型？

3. **约束条件是否满足**（权重10%）
   - 如风格、尺寸、模型等特定要求
   - 如果约束可以通过修改参数满足，也算满足

请回答：
1. 这个代码片段是否能满足用户需求？（是/否）
2. 匹配置信度？（0-1之间的浮点数，综合考虑上述三个因素）
3. 匹配理由（解释为什么匹配或不匹配）
4. 如果不能完全满足，缺少什么功能？

输出JSON格式：
{{
    "matched": true,
    "confidence": 0.85,
    "reason": "该片段使用KSampler进行图像生成，能够满足'生成粘土风格人物肖像'的核心功能。虽然代码中没有明确指定粘土风格，但可以通过修改提示词参数来实现。",
    "missing_features": []
}}

或者（不匹配的情况）：
{{
    "matched": false,
    "confidence": 0.3,
    "reason": "该片段是VAEDecode（图像解码），而需求是'4倍超分辨率'，功能不一致。",
    "missing_features": ["upscaling"]
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 片段组合可行性判断
# ============================================================================

FRAGMENT_COMBINATION_PROMPT = """你是ComfyUI工作流专家。请判断两个代码片段是否可以前后拼接。

片段A（前）:
{fragment_a_code}
输出类型: {fragment_a_outputs}

片段B（后）:
{fragment_b_code}
输入类型: {fragment_b_inputs}

ComfyUI的类型系统：
- MODEL: 扩散模型
- CLIP: CLIP文本编码器
- VAE: VAE编码器/解码器
- CONDITIONING: 条件向量（文本编码后）
- LATENT: 潜在空间表示
- IMAGE: 图像张量
- MASK: 遮罩
- STRING: 字符串
- INT: 整数
- FLOAT: 浮点数

请回答：
1. 这两个片段能否拼接？（是/否）
2. 如果可以，连接点在哪里？（哪个变量连接到哪个参数）
3. 是否需要类型转换？
4. 拼接后的代码是什么？

输出JSON格式：
{{
    "compatible": true,
    "connection_points": [
        {{
            "fragment_a_var": "image",
            "fragment_a_type": "IMAGE",
            "fragment_b_param": "image",
            "fragment_b_type": "IMAGE"
        }}
    ],
    "type_conversion_needed": false,
    "reason": "片段A输出IMAGE类型的image变量，片段B需要IMAGE类型的image参数，类型完全匹配",
    "combined_code": "片段A的代码\\n片段B的代码（将input_image替换为image）"
}}

或者（不兼容的情况）：
{{
    "compatible": false,
    "reason": "片段A输出LATENT类型，但片段B需要IMAGE类型输入，需要插入VAEDecode节点进行转换",
    "missing_conversion": "VAEDecode"
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 缺失片段代码生成
# ============================================================================

MISSING_FRAGMENT_GENERATION_PROMPT = """你是ComfyUI工作流专家。请生成代码片段来实现以下功能。

需求描述: {need_description}
类别: {need_category}
模态: {need_modality}
约束条件: {need_constraints}

可用的ComfyUI节点类型（参考）:
{available_node_types}

上下文信息：
- 上一个片段的输出: {previous_outputs}
- 下一个片段的输入: {next_inputs}

请生成Python风格的ComfyUI代码片段。

代码要求：
1. 使用函数调用风格（不是JSON）
2. 变量命名清晰
3. 参数使用具体值（字符串用引号，数字直接写）
4. 如果有占位符，使用{{变量名}}格式
5. 确保输入输出与上下文兼容

示例格式：
```python
# 输入: clip (CLIP), text (STRING)
conditioning = CLIPTextEncode(clip=clip, text="{{prompt}}")
# 输出: conditioning (CONDITIONING)
```

只返回代码和注释，不要其他解释。
"""

# ============================================================================
# 工作流完整性检查提示词
# ============================================================================

WORKFLOW_COMPLETENESS_CHECK_PROMPT = """你是ComfyUI工作流专家。请检查工作流是否完整且合理。

工作流代码:
{workflow_code}

检查要点：
1. 是否有明确的起始节点（如CheckpointLoader, LoadImage等）
2. 是否有明确的结束节点（如SaveImage, PreviewImage等）
3. 数据流是否连贯（每个节点的输入是否有来源）
4. 是否缺少关键节点（如生成流程缺少KSampler）
5. 逻辑是否合理（如先解码再编码）

输出JSON格式：
{{
    "is_complete": true,
    "is_reasonable": true,
    "issues": [],
    "suggestions": []
}}

或者（有问题的情况）：
{{
    "is_complete": false,
    "is_reasonable": true,
    "issues": [
        "缺少SaveImage节点，工作流没有输出",
        "KSampler的latent_image输入未连接"
    ],
    "suggestions": [
        "在最后添加SaveImage节点",
        "在KSampler前添加EmptyLatentImage或LoadImage"
    ]
}}

只返回JSON，不要其他内容。
"""

# ============================================================================
# 参数补全提示词
# ============================================================================

PARAMETER_COMPLETION_PROMPT = """你是ComfyUI工作流专家。请为工作流中的占位符参数填充合适的值。

工作流代码:
{workflow_code}

用户原始需求: {user_request}

需要补全的参数类型：
1. 提示词（text参数）- 从用户需求中提取关键描述
2. 模型名称（ckpt_name参数）- 根据需求选择合适的模型
3. 图像尺寸（width, height）- 根据需求或使用默认值
4. 采样参数（steps, cfg, sampler_name等）- 使用合理默认值

输出JSON格式：
{{
    "parameters": {{
        "text": "a beautiful clay style portrait of a person, highly detailed",
        "ckpt_name": "flux_dev.safetensors",
        "width": 1024,
        "height": 1024,
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal"
    }}
}}

只返回JSON，不要其他内容。
"""
