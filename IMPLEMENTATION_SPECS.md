# 实施规格说明

## 📋 模型清单

### 1. Embedding模型（召回）
```
模型名称: text-embedding-3-large
提供商: OpenAI
用途: 工作流意图向量化、需求向量化
API调用: 需要API Key
维度: 3072
```

### 2. Reranker模型（重排序）
```
模型名称: cross-encoder/mmarco-mMiniLMv2-L12-H384-V1
来源: HuggingFace
用途: 精确重排候选工作流
部署方式: 本地部署
模型大小: ~470MB
支持: 多语言
```

使用方式：
```python
from sentence_transformers import CrossEncoder

model = CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-V1')
scores = model.predict([
    (atomic_need.description, candidate.intent.description)
    for candidate in candidates
])
```

### 3. LLM模型（需求分解、意图提取、代码生成）

#### 主力LLM（通过API调用）
```
模型: GPT-4 / GPT-4-turbo / Claude-3.5-Sonnet
用途:
  - 需求分解（UserRequest → AtomicNeed列表）
  - 工作流意图自动标注
  - 片段-需求匹配判断
  - 缺失片段代码生成（最后手段）
API调用: 用户自行配置
```

### 4. 可选：本地Code LLM（如果需要离线）
```
模型: Qwen2.5-Coder-7B-Instruct
来源: 阿里云/HuggingFace
用途: 代码片段生成辅助
部署: 可选本地部署
模型大小: ~15GB (FP16)
```

---

## 💻 代码表示的优势和应用

### 为什么用代码表示？（ComfyBench论文观点）

1. **LLM友好** - 大多数LLM在代码上训练过，理解更好
2. **可读性强** - 人类和LLM都更容易理解
3. **结构清晰** - 依赖关系一目了然
4. **可组合性** - 代码片段天然适合拼接

### JSON vs Code对比

#### JSON表示（原生格式）
```json
{
  "3": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "a beautiful landscape",
      "clip": ["1", 0]
    }
  }
}
```
- ❌ 难以理解依赖关系
- ❌ 需要理解节点ID引用
- ❌ LLM容易产生幻觉

#### Code表示（我们使用的）
```python
model, clip, vae = CheckpointLoaderSimple(ckpt_name="model.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="a beautiful landscape")
latent = KSampler(model=model, positive=conditioning, ...)
image = VAEDecode(samples=latent, vae=vae)
```
- ✅ 依赖关系清晰（变量引用）
- ✅ 数据流一目了然
- ✅ LLM理解更准确
- ✅ 便于拼接和修改

### 在我们系统中的应用

#### 1. 工作流存储（阶段0）
```python
@dataclass
class WorkflowEntry:
    workflow_json: Dict        # 原始JSON（用于执行）
    workflow_code: str         # 代码表示（用于理解和拼接）
    intent: WorkflowIntent
    intent_embedding: List[float]
```

#### 2. 工作流拆分（阶段2.1）
**输入**：完整工作流的代码表示
**输出**：代码片段列表

```python
# 输入
code = """
model, clip, vae = CheckpointLoaderSimple(ckpt_name="model.safetensors")
conditioning_pos = CLIPTextEncode(clip=clip, text="beautiful landscape")
conditioning_neg = CLIPTextEncode(clip=clip, text="ugly, blurry")
latent_empty = EmptyLatentImage(width=512, height=512, batch_size=1)
latent = KSampler(model=model, positive=conditioning_pos, negative=conditioning_neg, latent_image=latent_empty, seed=42, steps=20)
image = VAEDecode(samples=latent, vae=vae)
_ = SaveImage(images=image, filename_prefix="output")
"""

# 拆分为片段
fragments = [
    # 片段1: 模型加载
    "model, clip, vae = CheckpointLoaderSimple(ckpt_name='model.safetensors')",
    
    # 片段2: 正面提示词编码
    "conditioning_pos = CLIPTextEncode(clip=clip, text='beautiful landscape')",
    
    # 片段3: 负面提示词编码
    "conditioning_neg = CLIPTextEncode(clip=clip, text='ugly, blurry')",
    
    # 片段4: 潜在图像初始化
    "latent_empty = EmptyLatentImage(width=512, height=512, batch_size=1)",
    
    # 片段5: 采样生成
    "latent = KSampler(model=model, positive=conditioning_pos, negative=conditioning_neg, latent_image=latent_empty, seed=42, steps=20)",
    
    # 片段6: 解码
    "image = VAEDecode(samples=latent, vae=vae)",
    
    # 片段7: 保存
    "_ = SaveImage(images=image, filename_prefix='output')"
]
```

#### 3. 片段拼接（阶段2.3）
使用**前作的算法**，但操作对象是代码：

```python
# 片段A（来自工作流1）
fragment_a = """
model, clip, vae = CheckpointLoaderSimple(ckpt_name="flux.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="clay style portrait")
latent_empty = EmptyLatentImage(width=1024, height=1024, batch_size=1)
latent = KSampler(model=model, positive=conditioning, latent_image=latent_empty)
image = VAEDecode(samples=latent, vae=vae)
"""

# 片段B（来自工作流2）
fragment_b = """
upscale_model = UpscaleModelLoader(model_name="4x-UltraSharp.pth")
image_upscaled = ImageUpscaleWithModel(upscale_model=upscale_model, image=input_image)
"""

# 拼接：识别image是连接点
# 1. 分析A的输出：image (VAEDecode的输出)
# 2. 分析B的输入：image (ImageUpscaleWithModel的输入)
# 3. 重命名B中的input_image → image
# 4. 合并代码

combined = """
model, clip, vae = CheckpointLoaderSimple(ckpt_name="flux.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="clay style portrait")
latent_empty = EmptyLatentImage(width=1024, height=1024, batch_size=1)
latent = KSampler(model=model, positive=conditioning, latent_image=latent_empty)
image = VAEDecode(samples=latent, vae=vae)
# --- 拼接点 ---
upscale_model = UpscaleModelLoader(model_name="4x-UltraSharp.pth")
image_upscaled = ImageUpscaleWithModel(upscale_model=upscale_model, image=image)
"""
```

#### 4. 代码 ↔ JSON转换（阶段3）
- **阶段2全程使用代码表示**（便于理解和拼接）
- **阶段3转换为JSON**（用于执行）

```python
# 使用已有的双向解析器
workflow_json = parse_code_to_prompt(combined_code)

# 执行
execute_comfyui_workflow(workflow_json)
```

---

## 🎯 片段-需求匹配的提示词设计

### 参考ComfyBench的多Agent架构

ComfyBench使用了两个关键Agent：
1. **PlanAgent** - 全局规划
2. **RetrievalAgent** - 检索和学习

我们的关键点：**满足意图** > 语义相似度

### 我们的提示词设计

#### Prompt 1: 片段功能描述生成

```python
FRAGMENT_DESCRIPTION_PROMPT = """
你是ComfyUI工作流专家。请分析以下代码片段，生成简洁的功能描述。

代码片段:
{code_fragment}

请回答：
1. 这个代码片段的主要功能是什么？（一句话）
2. 输入数据类型有哪些？（如IMAGE, TEXT, MODEL等）
3. 输出数据类型是什么？

只返回JSON格式：
{{
    "function": "使用CLIP模型对文本进行编码",
    "inputs": ["CLIP", "TEXT"],
    "outputs": ["CONDITIONING"]
}}
"""
```

#### Prompt 2: 片段-需求匹配判断（核心）

```python
FRAGMENT_NEED_MATCHING_PROMPT = """
你是ComfyUI工作流专家。请判断给定的代码片段是否能够满足用户的原子需求。

用户的原子需求:
描述: {atomic_need.description}
类别: {atomic_need.category}
模态: {atomic_need.modality}
约束条件: {atomic_need.constraints}

候选代码片段:
{code_fragment}

片段功能描述: {fragment_description}
片段输入: {fragment_inputs}
片段输出: {fragment_outputs}

请回答：
1. 这个代码片段是否能满足用户需求？（是/否）
2. 匹配置信度？（0-1之间的浮点数）
3. 如果不能完全满足，缺少什么功能？

评判标准：
- 功能意图是否一致（最重要）
- 输入输出类型是否匹配
- 是否满足约束条件（如风格、尺寸等）
- 不需要完全相同，只要能达到目标即可

返回JSON格式：
{{
    "matched": true/false,
    "confidence": 0.85,
    "reason": "该片段使用CLIP进行文本编码，能够满足'文本转条件向量'的需求",
    "missing_features": []
}}
"""
```

#### Prompt 3: 片段组合可行性判断

```python
FRAGMENT_COMBINATION_PROMPT = """
你是ComfyUI工作流专家。请判断两个代码片段是否可以前后拼接。

片段A（前）:
{fragment_a_code}
输出: {fragment_a_outputs}

片段B（后）:
{fragment_b_code}  
输入: {fragment_b_inputs}

请回答：
1. 这两个片段能否拼接？（是/否）
2. 如果可以，连接点在哪里？（变量名）
3. 是否需要类型转换？

返回JSON格式：
{{
    "compatible": true/false,
    "connection_point": {{"fragment_a_var": "image", "fragment_b_var": "input_image"}},
    "type_conversion_needed": false,
    "reason": "片段A输出IMAGE类型，片段B输入IMAGE类型，类型匹配"
}}
"""
```

#### Prompt 4: 缺失功能代码生成（最后手段）

```python
MISSING_FRAGMENT_GENERATION_PROMPT = """
你是ComfyUI工作流专家。请生成代码片段来实现以下功能。

需求描述: {atomic_need.description}
类别: {atomic_need.category}
模态: {atomic_need.modality}
约束: {atomic_need.constraints}

可用的ComfyUI节点类型（参考）:
{available_node_types}

请生成Python风格的ComfyUI代码片段。

格式要求：
1. 使用函数调用风格
2. 变量命名清晰
3. 参数使用具体值（可以是占位符）
4. 注释说明输入输出类型

示例格式：
```python
# 输入: clip (CLIP), text (STRING)
conditioning = CLIPTextEncode(clip=clip, text="{{prompt}}")
# 输出: conditioning (CONDITIONING)
```

只返回代码，不要其他解释。
"""
```

---

## 🔧 核心算法：代码级工作流拆分

### 策略1: 基于语句的简单拆分

```python
def split_workflow_by_statements(code: str) -> List[str]:
    """
    按语句拆分（最简单）
    每个赋值语句作为一个片段
    """
    lines = code.strip().split('\n')
    fragments = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            fragments.append(line)
    
    return fragments
```

### 策略2: 基于功能语义的智能拆分（推荐）

```python
def split_workflow_by_semantics(code: str) -> List[Dict]:
    """
    基于功能语义拆分
    识别常见的功能模式
    """
    
    # 1. 解析代码为AST
    tree = ast.parse(code)
    
    # 2. 识别功能模式
    fragments = []
    current_fragment = []
    
    for node in tree.body:
        if isinstance(node, ast.Assign):
            func_name = node.value.func.id
            
            # 判断是否是新功能的开始
            if is_new_capability(func_name, current_fragment):
                # 保存当前片段
                if current_fragment:
                    fragments.append({
                        "code": "\n".join(current_fragment),
                        "category": infer_category(current_fragment)
                    })
                
                # 开始新片段
                current_fragment = [ast.unparse(node)]
            else:
                # 继续当前片段
                current_fragment.append(ast.unparse(node))
    
    # 保存最后一个片段
    if current_fragment:
        fragments.append({
            "code": "\n".join(current_fragment),
            "category": infer_category(current_fragment)
        })
    
    return fragments

def is_new_capability(func_name: str, current_fragment: List[str]) -> bool:
    """判断是否是新功能的开始"""
    
    # 功能边界节点类型
    boundary_nodes = [
        "CheckpointLoaderSimple",    # 模型加载
        "EmptyLatentImage",          # 新图像开始
        "LoadImage",                 # 图像加载
        "UpscaleModelLoader",        # 超分开始
        "ControlNetLoader",          # ControlNet开始
        # ... 更多
    ]
    
    if func_name in boundary_nodes:
        return True
    
    # 如果当前片段为空，任何节点都是开始
    if not current_fragment:
        return True
    
    return False

def infer_category(fragment_code: List[str]) -> str:
    """推断片段的功能类别"""
    
    code_text = " ".join(fragment_code)
    
    if "CheckpointLoader" in code_text:
        return "model_loading"
    elif "CLIPTextEncode" in code_text:
        return "text_encoding"
    elif "KSampler" in code_text:
        return "sampling"
    elif "VAEDecode" in code_text:
        return "decoding"
    elif "Upscale" in code_text:
        return "upscaling"
    elif "ControlNet" in code_text:
        return "controlnet"
    else:
        return "unknown"
```

### 策略3: 混合策略（实际使用）

```python
def split_workflow_hybrid(code: str, atomic_needs: List[AtomicNeed]) -> List[Dict]:
    """
    混合策略：
    1. 先按语义粗拆
    2. 根据原子需求动态调整
    """
    
    # 1. 粗拆
    coarse_fragments = split_workflow_by_semantics(code)
    
    # 2. 根据需求调整
    refined_fragments = []
    for fragment in coarse_fragments:
        # 检查是否能一对一匹配某个需求
        matched = False
        for need in atomic_needs:
            if can_satisfy_need(fragment, need):
                refined_fragments.append({
                    **fragment,
                    "matched_need": need.need_id
                })
                matched = True
                break
        
        if not matched:
            # 进一步细拆
            sub_fragments = further_split(fragment)
            refined_fragments.extend(sub_fragments)
    
    return refined_fragments
```

---

## 📊 简化后的完整数据流

```
用户需求
    ↓
[LLM] 需求分解
    ↓
原子需求列表 [need_1, need_2, ...]
    ↓
[OpenAI Embedding] 向量化
    ↓
[FAISS检索] 召回候选工作流 (top-50)
    ↓
[Reranker] 重排序 (top-10)
    ↓
最终候选工作流（完整工作流，代码表示）
    ↓
【运行时动态拆分】
对每个候选工作流:
  split_workflow_by_semantics(workflow.code)
  → 代码片段列表
    ↓
【片段-需求匹配】
使用LLM提示词判断：
  for each fragment:
    for each need:
      matched, confidence = llm_match(fragment, need)
    ↓
【片段选择和拼接】
使用前作算法：
  1. 转换为JSON: code_to_json(fragment.code)
  2. ID偏移: update_node_numbers()
  3. 智能连接: merge_two_flow()
  4. 合并: merge_dicts_update()
    ↓
【缺失片段生成】
对未匹配的需求:
  使用LLM生成代码片段
    ↓
【验证】
语法检查 + 语义检查
    ↓
【合成】
Code → JSON + 参数补全
    ↓
可执行工作流JSON
```

---

## 🎯 关键决策总结

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 原子能力 | ❌ 不预标注 | 动态拆分更灵活 |
| 工作流表示 | ✅ 代码为主 | LLM友好，便于拼接 |
| Embedding | OpenAI API | 效果好，官方支持 |
| Reranker | mmarco-mMiniLMv2 | 多语言，本地部署 |
| 片段匹配 | LLM提示词 | 满足意图优先 |
| 拼接算法 | 前作算法 | 严谨，高Pass Rate |

---

## 📝 下一步行动

1. **搭建基础架构**
   - 实现代码-JSON双向转换器的完善
   - 搭建向量检索系统（FAISS）
   - 集成Reranker模型

2. **数据准备**
   - 爬取工作流（ComfyBench + 社区）
   - 标注整体意图（GPT-4辅助）
   - 构建向量索引

3. **核心算法实现**
   - 代码级工作流拆分算法
   - 片段-需求匹配（LLM）
   - 前作拼接算法迁移

需要我开始实现哪个模块？
