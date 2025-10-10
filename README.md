# ComfyUI工作流检索-适配-合成系统

基于**检索-适配-合成**范式的ComfyUI工作流生成系统，论文核心思路实现。

## 🎯 核心思想

不同于从零生成工作流，我们的系统：
1. **检索**现有工作流
2. **动态拆分**为代码片段
3. **智能匹配**需求
4. **算法拼接**（借鉴前作，保证高Pass Rate）

## 📁 项目结构

```
.
├── config.yaml.template      # 配置文件模板（复制为config.yaml并填写API key）
├── prompts.py                 # LLM提示词定义
├── main.py                    # 双向解析器（已有）
├── core/                      # 核心模块
│   ├── __init__.py
│   ├── data_structures.py     # 数据结构
│   ├── utils.py               # 工具函数
│   ├── llm_client.py          # LLM客户端
│   ├── need_decomposer.py     # 需求分解
│   ├── code_splitter.py       # 代码拆分
│   ├── fragment_matcher.py    # 片段-需求匹配（待实现）
│   ├── workflow_assembler.py  # 工作流拼接（待实现）
│   └── vector_search.py       # 向量检索（待实现）
├── previouswork/              # 前作代码（参考，不修改）
│   ├── function2dagcode.py
│   ├── dag_encode.py
│   ├── nodes.yaml
│   └── ...
├── data/                      # 数据目录
│   └── workflow_library/      # 工作流库
└── crawler/                   # 爬虫（已有）
```

## 🚀 快速开始

### 1. 配置API

```bash
# 复制配置模板
cp config.yaml.template config.yaml

# 编辑config.yaml，填写：
# - OpenAI API Key（用于embedding和LLM）
# - Reranker模型路径（本地部署）
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `openai` - OpenAI API
- `sentence-transformers` - Reranker模型
- `faiss-cpu` - 向量检索
- `pyyaml` - 配置文件

### 3. 下载Reranker模型

```python
from sentence_transformers import CrossEncoder

# 下载模型到本地
model = CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-V1')
model.save('./models/reranker')
```

## 📚 核心模块说明

### 阶段0: 工作流库

```python
from core.data_structures import WorkflowEntry, WorkflowIntent

# 工作流条目（简化设计，无预标注）
entry = WorkflowEntry(
    workflow_id="wf_001",
    workflow_json={...},           # 原始JSON
    workflow_code="...",           # 代码表示（主要用于理解和拼接）
    intent=WorkflowIntent(...),    # 整体意图描述
    intent_embedding=[...],        # 向量（用于检索）
)
```

### 阶段1: 需求匹配

```python
from core.need_decomposer import NeedDecomposer
from core.llm_client import LLMClient
from core.utils import load_config

config = load_config('config.yaml')
llm_client = LLMClient(config)

# 1.1 需求分解
decomposer = NeedDecomposer(llm_client)
decomposed = decomposer.decompose("生成粘土风格人物肖像并4倍超分")

# 1.2 意图匹配（向量召回）
# 1.3 重排序
# ... (待实现)
```

### 阶段2: 动态适配

```python
from core.code_splitter import CodeSplitter

# 2.1 代码拆分（运行时动态拆分）
splitter = CodeSplitter(llm_client, node_defs, strategy="hybrid")
fragments = splitter.split(workflow_entry)

# 2.2 片段-需求匹配（LLM判断，满足意图优先）
# 2.3 拼接（借鉴前作算法）
# ... (待实现)
```

### 阶段3: 合成

```python
# 3.1 Code → JSON转换（使用已有的双向解析器）
from main import parse_code_to_prompt

workflow_json = parse_code_to_prompt(framework_code)

# 3.2 参数补全
# ... (待实现)
```

## 🎨 设计亮点

### 1. 代码表示为核心

**为什么？**（参考ComfyBench论文）
- LLM在代码上训练过，理解更好
- 依赖关系清晰（变量引用）
- 便于拼接和修改

```python
# Code表示（易读）
model, clip, vae = CheckpointLoaderSimple(ckpt_name="flux.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="portrait")
```

vs

```json
// JSON表示（难读）
{
  "3": {"inputs": {"clip": ["1", 0], "text": "portrait"}, ...}
}
```

### 2. 动态拆分 vs 预标注

**我们的选择：动态拆分**

| 方案 | 优点 | 缺点 |
|-----|------|------|
| 预标注原子能力 | 快速查询 | 标注成本高，不够灵活 |
| 动态拆分（我们） | 灵活，低成本 | 需要好的拆分算法 |

### 3. 片段-需求匹配：满足意图 > 语义相似

传统：计算embedding余弦相似度
**我们**：使用LLM判断"是否能满足功能意图"

```python
# 提示词关键点（见prompts.py）
"""
评判标准：
1. 功能意图是否一致（权重70%）
2. 输入输出类型是否匹配（权重20%）
3. 约束条件是否满足（权重10%）
"""
```

### 4. 算法拼接保证高Pass Rate

**借鉴前作的严谨算法**：
- 基于类型匹配自动连接
- 节点ID偏移避免冲突
- DAG结构验证

（实现在 `core/workflow_assembler.py`，待完成）

## 📝 当前进度

- [x] 配置文件模板
- [x] 核心数据结构
- [x] LLM客户端
- [x] 工具函数（借鉴前作类型系统）
- [x] LLM提示词设计
- [x] 需求分解模块
- [x] 代码拆分模块
- [ ] 片段-需求匹配模块
- [ ] 向量检索和Reranker
- [ ] 工作流拼接模块
- [ ] 参数补全
- [ ] 端到端集成
- [ ] 评估和优化

## 🔧 开发指南

### 添加新的LLM提示词

在 `prompts.py` 中添加：

```python
YOUR_NEW_PROMPT = """
你是ComfyUI专家。请...

输入: {input_var}

输出JSON格式:
{{
    "result": "..."
}}
"""
```

### 扩展节点定义

使用前作的节点定义文件：`previouswork/nodes.yaml`

### 测试

```bash
# 单元测试
pytest tests/

# 端到端测试
python examples/e2e_test.py
```

## 📊 评估指标

在ComfyBench上评估：
- **Pass Rate**: 可执行工作流占比
- **Resolve Rate**: 正确实现需求占比
- **Token Usage**: LLM调用成本
- **Execution Time**: 生成时间

## 📖 参考资料

- **ComfyBench论文**: 多Agent架构，代码表示优势
- **ComfyUI-R1论文**: 数据收集方法，端到端推理
- **实验室前作**: 严谨的拼接算法，高Pass Rate保证
- **"生态化"思想**: 结构池概念，协议优先

## 👥 贡献

欢迎贡献代码和想法！

## 📄 许可

MIT License
