# 基于工作流检索-适配-合成的ComfyUI生成系统 - 详细设计方案

## 🎯 系统总览

```
┌────────────────────────────────────────────────────────────┐
│                     用户需求输入                            │
│    "生成一个粘土风格的人物肖像，并进行4倍超分"              │
└──────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  阶段0: 工作流库 (Existing Workflows Library)             │
│  • 存储结构                                               │
│  • 意图标注                                               │
│  • 向量索引                                               │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  阶段1: 需求匹配                                          │
│  1.1 需求分解 → 原子需求列表                              │
│  1.2 意图匹配 → Candidate Workflows                       │
│  1.3 需求对齐 → 匹配/未匹配标记                           │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  阶段2: 工作流框架级别智能适配（代码片段形式）            │
│  2.1 拆分工作流 → 原子需求映射 → 重组拼接                │
│  2.2 缺失部分生成 → 节点匹配 → 代码片段合成              │
│  2.3 完整性检查 → 语义检查 + 语法检查                     │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  阶段3: 可执行工作流合成                                  │
│  3.1 工作流框架(Code) → JSON转换                         │
│  3.2 参数补全                                             │
│  3.3 执行验证                                             │
└──────────────────────────────────────────────────────────┘
```

---

## 📚 阶段0: 工作流库（Existing Workflows Library）

### 0.1 数据结构设计

#### 核心数据模型

```python
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class WorkflowComplexity(Enum):
    VANILLA = "vanilla"      # 简单，单一功能
    COMPLEX = "complex"      # 复杂，多功能组合
    CREATIVE = "creative"    # 创新，需要理解原理

@dataclass
class AtomicCapability:
    """原子能力：工作流中不可再分的功能单元"""
    capability_id: str              # 如 "text_encoding_clip"
    description: str                # "使用CLIP模型进行文本编码"
    category: str                   # "encoding", "generation", "upscaling"...
    
    # 代码表示
    code_snippet: str               # Python-like代码片段
    
    # 节点信息
    node_ids: List[str]             # 涉及的节点ID
    node_types: List[str]           # 节点类型列表
    
    # 输入输出协议
    inputs: Dict[str, str]          # {"clip": "CLIP", "text": "STRING"}
    outputs: Dict[str, str]         # {"conditioning": "CONDITIONING"}
    
    # 依赖关系
    depends_on: List[str]           # 依赖的其他capability_id

@dataclass
class WorkflowIntent:
    """工作流意图"""
    primary_task: str               # "text-to-image"
    modality: str                   # "image", "video", "3d"
    style: Optional[str]            # "clay", "anime", "realistic"
    operation: str                  # "generation", "editing", "upscaling"
    
    # 自然语言描述
    description: str                # "生成粘土风格的人物肖像"
    keywords: List[str]             # ["粘土", "人物", "肖像", "生成"]
    
    # 原子能力组合
    required_capabilities: List[str]  # 必需的能力
    optional_capabilities: List[str]  # 可选的能力

@dataclass
class WorkflowEntry:
    """工作流库中的一个条目"""
    workflow_id: str
    
    # 三种表示
    workflow_json: Dict[str, Any]   # 原始JSON
    workflow_code: str              # Python-like代码
    workflow_dag: Dict[str, Any]    # DAG分析结果
    
    # 意图和能力
    intent: WorkflowIntent
    atomic_capabilities: List[AtomicCapability]
    
    # 元数据
    complexity: WorkflowComplexity
    node_count: int
    source: str                     # "comfybench", "openart", "manual"
    tags: List[str]
    
    # 统计信息
    usage_count: int
    success_rate: float
    avg_execution_time: float
    
    # 向量表示（用于检索）
    intent_embedding: Optional[List[float]] = None
    capability_embedding: Optional[List[float]] = None
```

#### 存储结构

```
data/
├── workflow_library/
│   ├── workflows/                    # 工作流JSON
│   │   ├── text_to_image_basic_001.json
│   │   ├── clay_style_portrait_002.json
│   │   └── ...
│   ├── metadata/                     # 元数据
│   │   ├── text_to_image_basic_001.meta.json
│   │   └── ...
│   ├── embeddings/                   # 向量表示
│   │   └── embeddings.faiss
│   ├── index/                        # 索引
│   │   ├── intent_index.json         # 意图索引
│   │   ├── capability_index.json     # 能力索引
│   │   └── node_type_index.json      # 节点类型索引
│   └── library.db                    # SQLite数据库（可选）
```

### 0.2 工作流采集和标注

#### 数据来源

1. **ComfyBench Curriculum Workflows**（20个）
   - 高质量、已验证
   - 覆盖基础功能

2. **社区平台爬取**
   - OpenArt.ai（过滤高评分）
   - ComfyWorkflows.com
   - Civitai（带工作流的图片）

3. **手工精选**
   - 特定领域的优秀工作流

#### 自动标注流程

```python
def auto_annotate_workflow(workflow_json: Dict) -> WorkflowEntry:
    """自动标注工作流"""
    
    # 1. 基础信息提取
    dag_info = analyze_dag(workflow_json)
    code_repr = json_to_code(workflow_json)
    
    # 2. 意图提取（使用GPT-4）
    intent_prompt = f"""
    分析以下ComfyUI工作流，提取其意图：
    
    工作流节点类型: {get_node_types(workflow_json)}
    工作流结构: {dag_info['summary']}
    
    请提取：
    1. 主要任务（如text-to-image）
    2. 模态（image/video/3d）
    3. 风格（如有）
    4. 操作类型（generation/editing/upscaling）
    5. 关键词列表
    6. 自然语言描述
    """
    
    intent = gpt4_extract_intent(intent_prompt)
    
    # 3. 原子能力提取（基于规则+LLM）
    capabilities = extract_atomic_capabilities(workflow_json, dag_info)
    
    # 4. 向量化
    intent_embedding = embed_text(intent.description)
    capability_text = " ".join([c.description for c in capabilities])
    capability_embedding = embed_text(capability_text)
    
    return WorkflowEntry(
        workflow_id=generate_id(),
        workflow_json=workflow_json,
        workflow_code=code_repr,
        workflow_dag=dag_info,
        intent=intent,
        atomic_capabilities=capabilities,
        intent_embedding=intent_embedding,
        capability_embedding=capability_embedding,
        # ... 其他字段
    )
```

#### 原子能力提取算法

```python
def extract_atomic_capabilities(
    workflow_json: Dict,
    dag_info: Dict
) -> List[AtomicCapability]:
    """
    从工作流中提取原子能力
    
    策略：
    1. 基于节点类型聚类（如所有CLIP相关节点）
    2. 基于功能语义（如"文本编码"、"采样生成"）
    3. 基于输入输出边界
    """
    
    capabilities = []
    
    # 1. 识别关键节点模式
    patterns = {
        "text_encoding": ["CLIPTextEncode", "CLIPTextEncodeSDXL"],
        "image_generation": ["KSampler", "SamplerCustom"],
        "image_decoding": ["VAEDecode"],
        "upscaling": ["UpscaleModelLoader", "ImageUpscaleWithModel"],
        "controlnet": ["ControlNetLoader", "ControlNetApply"],
        # ... 更多模式
    }
    
    for pattern_name, node_types in patterns.items():
        matched_nodes = find_nodes_by_types(workflow_json, node_types)
        
        if matched_nodes:
            # 提取这个模式的完整子图
            subgraph = extract_subgraph(
                workflow_json, 
                matched_nodes, 
                dag_info
            )
            
            # 生成代码片段
            code_snippet = subgraph_to_code(subgraph)
            
            # 分析输入输出
            inputs, outputs = analyze_io(subgraph, dag_info)
            
            capability = AtomicCapability(
                capability_id=f"{pattern_name}_{matched_nodes[0]}",
                description=get_pattern_description(pattern_name),
                category=get_pattern_category(pattern_name),
                code_snippet=code_snippet,
                node_ids=matched_nodes,
                node_types=node_types,
                inputs=inputs,
                outputs=outputs,
                depends_on=find_dependencies(subgraph, dag_info)
            )
            
            capabilities.append(capability)
    
    return capabilities
```

### 0.3 工作流库管理

```python
class WorkflowLibrary:
    """工作流库管理类"""
    
    def __init__(self, library_path: str):
        self.library_path = library_path
        self.entries: Dict[str, WorkflowEntry] = {}
        self.vector_index = None  # FAISS索引
        
        self._load_library()
    
    def add_workflow(self, workflow_json: Dict, metadata: Dict = None):
        """添加新工作流"""
        entry = auto_annotate_workflow(workflow_json)
        
        if metadata:
            entry.update(metadata)
        
        self.entries[entry.workflow_id] = entry
        self._update_index(entry)
        self._save_entry(entry)
    
    def search_by_intent(
        self, 
        query: str, 
        top_k: int = 10
    ) -> List[WorkflowEntry]:
        """基于意图检索工作流"""
        query_embedding = embed_text(query)
        
        # 向量检索
        distances, indices = self.vector_index.search(
            query_embedding.reshape(1, -1), 
            top_k * 2  # 多召回一些候选
        )
        
        candidates = [self.entries[self._id_map[idx]] for idx in indices[0]]
        
        # 重排序
        ranked = self._rerank(query, candidates, top_k)
        
        return ranked
    
    def search_by_capability(
        self,
        required_capabilities: List[str]
    ) -> List[WorkflowEntry]:
        """基于能力检索工作流"""
        results = []
        
        for entry in self.entries.values():
            entry_caps = set(c.capability_id for c in entry.atomic_capabilities)
            required_caps = set(required_capabilities)
            
            # 计算覆盖度
            coverage = len(entry_caps & required_caps) / len(required_caps)
            
            if coverage > 0.5:  # 至少覆盖50%
                results.append((coverage, entry))
        
        # 按覆盖度排序
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [entry for _, entry in results]
    
    def _rerank(
        self, 
        query: str, 
        candidates: List[WorkflowEntry], 
        top_k: int
    ) -> List[WorkflowEntry]:
        """重排序：综合考虑语义、功能覆盖度、成功率等"""
        
        scores = []
        for candidate in candidates:
            # 1. 语义相似度（已在向量检索中体现）
            semantic_score = 1.0  # 归一化后的距离
            
            # 2. 复杂度匹配（简单需求优先简单工作流）
            complexity_score = self._complexity_match(query, candidate)
            
            # 3. 成功率
            success_score = candidate.success_rate
            
            # 4. 使用频率
            popularity_score = np.log1p(candidate.usage_count) / 10
            
            # 综合得分
            total_score = (
                0.5 * semantic_score +
                0.2 * complexity_score +
                0.2 * success_score +
                0.1 * popularity_score
            )
            
            scores.append((total_score, candidate))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        return [candidate for _, candidate in scores[:top_k]]
```

---

## 🎯 阶段1: 需求匹配

### 1.1 需求分解

#### 目标
将用户的自然语言需求分解为原子需求列表

#### 输入输出

```python
@dataclass
class UserRequest:
    """用户需求"""
    raw_text: str  # "生成一个粘土风格的人物肖像，并进行4倍超分"
    context: Optional[Dict] = None  # 可选的上下文信息

@dataclass
class AtomicNeed:
    """原子需求"""
    need_id: str
    description: str            # "生成粘土风格人物肖像"
    category: str              # "generation", "upscaling", "editing"
    modality: str              # "image", "video", "3d"
    priority: int              # 优先级 1-10
    dependencies: List[str]    # 依赖的其他need_id
    
    # 约束条件
    constraints: Dict[str, Any]  # {"style": "clay", "subject": "portrait"}
    
    # 可选：期望的原子能力
    expected_capabilities: List[str]

@dataclass
class DecomposedNeeds:
    """分解后的需求"""
    atomic_needs: List[AtomicNeed]
    dependency_graph: Dict[str, List[str]]  # DAG结构
    execution_order: List[str]              # 拓扑排序后的执行顺序
```

#### 实现算法

```python
class NeedDecomposer:
    """需求分解器"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.decomposition_prompt = self._load_prompt()
    
    def decompose(self, request: UserRequest) -> DecomposedNeeds:
        """分解需求"""
        
        # 1. 使用LLM进行初步分解
        prompt = self._build_decomposition_prompt(request.raw_text)
        llm_output = self.llm.generate(prompt)
        
        # 2. 解析LLM输出
        atomic_needs = self._parse_llm_output(llm_output)
        
        # 3. 构建依赖图
        dependency_graph = self._build_dependency_graph(atomic_needs)
        
        # 4. 拓扑排序（确定执行顺序）
        execution_order = self._topological_sort(dependency_graph)
        
        # 5. 验证和优化
        atomic_needs = self._validate_and_optimize(atomic_needs)
        
        return DecomposedNeeds(
            atomic_needs=atomic_needs,
            dependency_graph=dependency_graph,
            execution_order=execution_order
        )
    
    def _build_decomposition_prompt(self, raw_text: str) -> str:
        """构建分解提示词"""
        return f"""
你是一个ComfyUI工作流专家。请将用户需求分解为原子需求。

用户需求: {raw_text}

请分解为原子需求，每个原子需求应该：
1. 是一个独立的、不可再分的功能单元
2. 明确描述要做什么
3. 指定类别（generation/editing/upscaling等）
4. 指定模态（image/video/3d）
5. 指定依赖关系（如果需要前一个需求的输出）

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
            "constraints": {{"style": "clay", "subject": "portrait"}}
        }},
        {{
            "need_id": "need_2",
            "description": "将图像进行4倍超分辨率处理",
            "category": "upscaling",
            "modality": "image",
            "priority": 5,
            "dependencies": ["need_1"],
            "constraints": {{"scale": 4}}
        }}
    ]
}}
"""
    
    def _build_dependency_graph(
        self, 
        atomic_needs: List[AtomicNeed]
    ) -> Dict[str, List[str]]:
        """构建依赖图"""
        graph = {need.need_id: [] for need in atomic_needs}
        
        for need in atomic_needs:
            for dep in need.dependencies:
                graph[dep].append(need.need_id)
        
        return graph
    
    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """拓扑排序"""
        # 计算入度
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1
        
        # Kahn算法
        queue = [node for node in graph if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(graph):
            raise ValueError("存在循环依赖！")
        
        return result
```

### 1.2 意图匹配 → Candidate Workflows

#### 目标
将EWF（工作流库）中的工作流意图匹配到原子需求上

#### 实现算法

```python
class IntentMatcher:
    """意图匹配器"""
    
    def __init__(self, workflow_library: WorkflowLibrary):
        self.library = workflow_library
    
    def match(
        self, 
        atomic_needs: List[AtomicNeed],
        top_k_per_need: int = 5
    ) -> Dict[str, List[WorkflowEntry]]:
        """
        为每个原子需求匹配候选工作流
        
        返回: {need_id: [candidate_workflow_1, ...]}
        """
        
        candidates_per_need = {}
        
        for need in atomic_needs:
            # 构建查询
            query = self._build_query_from_need(need)
            
            # 1. 基于意图检索（向量相似度）
            intent_matches = self.library.search_by_intent(
                query, 
                top_k=top_k_per_need * 2
            )
            
            # 2. 基于能力检索（功能匹配）
            if need.expected_capabilities:
                capability_matches = self.library.search_by_capability(
                    need.expected_capabilities
                )
            else:
                capability_matches = []
            
            # 3. 合并和去重
            all_candidates = self._merge_candidates(
                intent_matches, 
                capability_matches
            )
            
            # 4. 精细化筛选
            filtered = self._filter_by_constraints(all_candidates, need)
            
            # 5. 重排序
            ranked = self._rank_candidates(filtered, need, top_k_per_need)
            
            candidates_per_need[need.need_id] = ranked
        
        return candidates_per_need
    
    def _build_query_from_need(self, need: AtomicNeed) -> str:
        """从原子需求构建查询字符串"""
        query_parts = [need.description]
        
        # 添加约束信息
        if need.constraints:
            for key, value in need.constraints.items():
                query_parts.append(f"{key}: {value}")
        
        return " ".join(query_parts)
    
    def _filter_by_constraints(
        self,
        candidates: List[WorkflowEntry],
        need: AtomicNeed
    ) -> List[WorkflowEntry]:
        """基于约束条件过滤候选工作流"""
        
        filtered = []
        for candidate in candidates:
            # 检查模态匹配
            if candidate.intent.modality != need.modality:
                continue
            
            # 检查类别匹配
            if candidate.intent.operation != need.category:
                continue
            
            # 检查约束条件（如风格）
            if "style" in need.constraints:
                if candidate.intent.style != need.constraints["style"]:
                    # 允许一定的灵活性
                    if not self._style_compatible(
                        candidate.intent.style, 
                        need.constraints["style"]
                    ):
                        continue
            
            filtered.append(candidate)
        
        return filtered
    
    def _rank_candidates(
        self,
        candidates: List[WorkflowEntry],
        need: AtomicNeed,
        top_k: int
    ) -> List[WorkflowEntry]:
        """重排序候选工作流"""
        
        scores = []
        for candidate in candidates:
            # 综合得分
            score = self._calculate_match_score(candidate, need)
            scores.append((score, candidate))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scores[:top_k]]
    
    def _calculate_match_score(
        self,
        candidate: WorkflowEntry,
        need: AtomicNeed
    ) -> float:
        """计算匹配得分"""
        
        score = 0.0
        
        # 1. 语义相似度（余弦相似度）
        if candidate.intent_embedding:
            need_embedding = embed_text(need.description)
            semantic_sim = cosine_similarity(
                need_embedding,
                candidate.intent_embedding
            )
            score += 0.4 * semantic_sim
        
        # 2. 能力覆盖度
        if need.expected_capabilities:
            candidate_caps = set(
                c.capability_id for c in candidate.atomic_capabilities
            )
            expected_caps = set(need.expected_capabilities)
            coverage = len(candidate_caps & expected_caps) / len(expected_caps)
            score += 0.3 * coverage
        
        # 3. 复杂度匹配（优先简单的）
        complexity_penalty = {
            WorkflowComplexity.VANILLA: 0,
            WorkflowComplexity.COMPLEX: -0.1,
            WorkflowComplexity.CREATIVE: -0.2
        }
        score += complexity_penalty.get(candidate.complexity, 0)
        
        # 4. 成功率
        score += 0.2 * candidate.success_rate
        
        # 5. 节点数量（越少越好，但不能太少）
        node_score = 1.0 / (1.0 + abs(candidate.node_count - 10) / 10)
        score += 0.1 * node_score
        
        return score
```

### 1.3 需求匹配 → 确定匹配/未匹配

#### 目标
初步确定哪些原子需求能匹配上工作流，哪些匹配不上

#### 实现算法

```python
@dataclass
class MatchResult:
    """匹配结果"""
    need_id: str
    matched: bool
    confidence: float           # 匹配置信度 0-1
    
    # 如果匹配上
    selected_workflow: Optional[WorkflowEntry] = None
    alternative_workflows: List[WorkflowEntry] = None
    
    # 如果没匹配上
    reason: Optional[str] = None
    missing_capabilities: List[str] = None

class NeedWorkflowMatcher:
    """需求-工作流匹配器"""
    
    def __init__(
        self,
        workflow_library: WorkflowLibrary,
        match_threshold: float = 0.6
    ):
        self.library = workflow_library
        self.match_threshold = match_threshold
        self.intent_matcher = IntentMatcher(workflow_library)
    
    def match_all(
        self,
        atomic_needs: List[AtomicNeed]
    ) -> List[MatchResult]:
        """为所有原子需求找匹配"""
        
        # 1. 批量获取候选工作流
        candidates_per_need = self.intent_matcher.match(
            atomic_needs,
            top_k_per_need=5
        )
        
        # 2. 对每个需求做匹配决策
        results = []
        for need in atomic_needs:
            candidates = candidates_per_need.get(need.need_id, [])
            match_result = self._decide_match(need, candidates)
            results.append(match_result)
        
        return results
    
    def _decide_match(
        self,
        need: AtomicNeed,
        candidates: List[WorkflowEntry]
    ) -> MatchResult:
        """决策是否匹配"""
        
        if not candidates:
            return MatchResult(
                need_id=need.need_id,
                matched=False,
                confidence=0.0,
                reason="没有找到候选工作流",
                missing_capabilities=need.expected_capabilities
            )
        
        # 选择得分最高的候选
        best_candidate = candidates[0]
        best_score = self.intent_matcher._calculate_match_score(
            best_candidate, need
        )
        
        # 判断是否超过阈值
        if best_score >= self.match_threshold:
            return MatchResult(
                need_id=need.need_id,
                matched=True,
                confidence=best_score,
                selected_workflow=best_candidate,
                alternative_workflows=candidates[1:]
            )
        else:
            # 分析为什么没匹配上
            missing_caps = self._analyze_missing_capabilities(
                need, best_candidate
            )
            
            return MatchResult(
                need_id=need.need_id,
                matched=False,
                confidence=best_score,
                reason=f"最佳匹配得分{best_score:.2f}低于阈值{self.match_threshold}",
                missing_capabilities=missing_caps
            )
    
    def _analyze_missing_capabilities(
        self,
        need: AtomicNeed,
        best_candidate: WorkflowEntry
    ) -> List[str]:
        """分析缺失的能力"""
        
        if not need.expected_capabilities:
            return []
        
        candidate_caps = set(
            c.capability_id for c in best_candidate.atomic_capabilities
        )
        expected_caps = set(need.expected_capabilities)
        
        missing = list(expected_caps - candidate_caps)
        return missing
```

---

## ⚙️ 阶段2: 工作流框架级别智能适配

### 2.1 拆分原有工作流 → 原子需求映射 → 重组拼接

#### 目标
将匹配上的工作流拆分为片段，与原子需求对应，然后重组拼接

#### 核心数据结构

```python
@dataclass
class WorkflowFragment:
    """工作流片段"""
    fragment_id: str
    source_workflow_id: str
    
    # 代码表示
    code_snippet: str
    
    # 节点信息
    node_ids: List[str]         # 原始节点ID
    node_json: Dict[str, Any]   # 节点JSON
    
    # 映射到的原子需求
    mapped_need_id: Optional[str] = None
    
    # 输入输出
    inputs: Dict[str, str]      # {"image": "IMAGE", "text": "STRING"}
    outputs: Dict[str, str]     # {"result": "IMAGE"}
    
    # DAG信息
    internal_dependencies: Dict[str, List[str]]  # 片段内部依赖
    external_dependencies: List[str]             # 依赖其他片段

@dataclass
class WorkflowFramework:
    """工作流框架（代码片段组合）"""
    framework_id: str
    fragments: List[WorkflowFragment]
    execution_order: List[str]  # fragment_id的执行顺序
    
    # 代码表示
    framework_code: str
```

#### 实现算法

```python
class WorkflowAdapter:
    """工作流适配器"""
    
    def __init__(self):
        # 从前作中提取的算法
        self.fragment_splitter = FragmentSplitter()
        self.fragment_assembler = FragmentAssembler()
        self.validator = WorkflowValidator()
    
    def adapt(
        self,
        atomic_needs: List[AtomicNeed],
        match_results: List[MatchResult]
    ) -> WorkflowFramework:
        """
        智能适配：拆分-映射-拼接
        """
        
        # 1. 拆分所有匹配上的工作流
        all_fragments = []
        for match in match_results:
            if match.matched:
                fragments = self.fragment_splitter.split(
                    match.selected_workflow
                )
                all_fragments.extend(fragments)
        
        # 2. 将片段映射到原子需求
        mapped_fragments = self._map_fragments_to_needs(
            all_fragments,
            atomic_needs
        )
        
        # 3. 选择最优片段组合
        selected_fragments = self._select_optimal_fragments(
            mapped_fragments,
            atomic_needs
        )
        
        # 4. 拼接片段
        framework = self.fragment_assembler.assemble(
            selected_fragments,
            atomic_needs
        )
        
        return framework
    
    def _map_fragments_to_needs(
        self,
        fragments: List[WorkflowFragment],
        atomic_needs: List[AtomicNeed]
    ) -> Dict[str, List[WorkflowFragment]]:
        """
        将片段映射到原子需求
        
        返回: {need_id: [fragment_1, fragment_2, ...]}
        """
        
        mapping = {need.need_id: [] for need in atomic_needs}
        
        for fragment in fragments:
            best_match = None
            best_score = 0
            
            for need in atomic_needs:
                # 计算片段与需求的相似度
                score = self._calculate_fragment_need_similarity(
                    fragment, need
                )
                
                if score > best_score:
                    best_score = score
                    best_match = need.need_id
            
            if best_match and best_score > 0.5:
                fragment.mapped_need_id = best_match
                mapping[best_match].append(fragment)
        
        return mapping
    
    def _select_optimal_fragments(
        self,
        mapped_fragments: Dict[str, List[WorkflowFragment]],
        atomic_needs: List[AtomicNeed]
    ) -> List[WorkflowFragment]:
        """
        为每个原子需求选择最优片段
        """
        
        selected = []
        
        for need in atomic_needs:
            candidates = mapped_fragments.get(need.need_id, [])
            
            if not candidates:
                # 没有匹配的片段，标记为需要生成
                selected.append(None)  # 占位
            else:
                # 选择最优片段（综合考虑复杂度、成功率等）
                best = self._rank_fragments(candidates, need)[0]
                selected.append(best)
        
        return selected

class FragmentSplitter:
    """片段拆分器"""
    
    def split(self, workflow: WorkflowEntry) -> List[WorkflowFragment]:
        """
        将工作流拆分为片段
        
        策略：
        1. 基于原子能力拆分（已标注）
        2. 基于功能边界拆分
        """
        
        fragments = []
        
        # 使用已标注的原子能力
        for capability in workflow.atomic_capabilities:
            fragment = WorkflowFragment(
                fragment_id=f"{workflow.workflow_id}_{capability.capability_id}",
                source_workflow_id=workflow.workflow_id,
                code_snippet=capability.code_snippet,
                node_ids=capability.node_ids,
                node_json=self._extract_nodes(
                    workflow.workflow_json,
                    capability.node_ids
                ),
                inputs=capability.inputs,
                outputs=capability.outputs,
                internal_dependencies=self._build_internal_deps(
                    capability.node_ids,
                    workflow.workflow_dag
                )
            )
            
            fragments.append(fragment)
        
        return fragments

class FragmentAssembler:
    """片段组装器（使用前作算法）"""
    
    def assemble(
        self,
        fragments: List[WorkflowFragment],
        atomic_needs: List[AtomicNeed]
    ) -> WorkflowFramework:
        """
        拼接片段成完整工作流框架
        
        关键：使用前作的拼接算法！
        """
        
        # 1. 确定执行顺序（基于原子需求的依赖图）
        execution_order = self._determine_execution_order(
            fragments, atomic_needs
        )
        
        # 2. 按顺序拼接（使用前作算法）
        assembled_json = {}
        offset = 0
        
        for i, fragment in enumerate(execution_order):
            if fragment is None:
                # 缺失片段，跳过（后续生成）
                continue
            
            # ID偏移（前作算法）
            fragment_json = update_node_numbers(
                fragment.node_json,
                offset
            )
            
            # 合并
            assembled_json = merge_dicts_update(
                assembled_json,
                fragment_json
            )
            
            # 处理依赖连接
            if i > 0 and execution_order[i-1] is not None:
                assembled_json = self._connect_fragments(
                    assembled_json,
                    execution_order[i-1],
                    fragment,
                    offset
                )
            
            offset = find_max_id(assembled_json)  # 前作算法
        
        # 3. 转换为代码表示
        framework_code = json_to_code(assembled_json)
        
        return WorkflowFramework(
            framework_id=generate_id(),
            fragments=[f for f in execution_order if f],
            execution_order=[f.fragment_id for f in execution_order if f],
            framework_code=framework_code
        )
    
    def _connect_fragments(
        self,
        assembled_json: Dict,
        prev_fragment: WorkflowFragment,
        curr_fragment: WorkflowFragment,
        offset: int
    ) -> Dict:
        """
        连接两个片段（处理输入输出）
        
        使用前作的连接逻辑：
        - 找到prev的输出节点
        - 找到curr的输入节点
        - 修改curr的输入连接指向prev的输出
        """
        
        # 找到prev的输出
        prev_output_types = set(prev_fragment.outputs.values())
        
        # 找到curr需要的输入
        curr_input_types = set(curr_fragment.inputs.values())
        
        # 匹配类型
        for output_type in prev_output_types:
            if output_type in curr_input_types:
                # 找到具体的输出节点ID
                prev_output_node = self._find_output_node_by_type(
                    prev_fragment,
                    output_type
                )
                
                # 找到具体的输入字段
                curr_input_field = self._find_input_field_by_type(
                    curr_fragment,
                    output_type
                )
                
                # 修改连接（前作的modify_node_input逻辑）
                assembled_json = modify_node_input(
                    assembled_json,
                    curr_fragment.node_json[curr_fragment.node_ids[0]]['class_type'],
                    curr_input_field,
                    str(int(prev_output_node) + offset - find_max_id(prev_fragment.node_json))
                )
        
        return assembled_json
```

### 2.2 未匹配需求生成 → 节点匹配 → 代码片段合成

#### 目标
对于没有匹配上工作流的原子需求，通过节点匹配生成代码片段

#### 实现算法

```python
class FragmentGenerator:
    """片段生成器（用于未匹配的需求）"""
    
    def __init__(self, node_library: Dict):
        self.node_library = node_library  # 节点知识库
        self.pattern_templates = self._load_pattern_templates()
    
    def generate_fragment(
        self,
        need: AtomicNeed
    ) -> WorkflowFragment:
        """
        为未匹配的原子需求生成片段
        
        策略：
        1. 基于需求类别匹配模板
        2. 基于节点功能搜索
        3. 使用LLM辅助生成
        """
        
        # 1. 尝试匹配已知模板
        template = self._match_template(need)
        if template:
            return self._instantiate_template(template, need)
        
        # 2. 基于节点功能搜索
        relevant_nodes = self._search_nodes_by_function(need)
        if relevant_nodes:
            return self._compose_from_nodes(relevant_nodes, need)
        
        # 3. 使用LLM生成（最后手段）
        return self._llm_generate(need)
    
    def _match_template(self, need: AtomicNeed) -> Optional[Dict]:
        """匹配已知模板"""
        
        # 例如：超分辨率模板
        if need.category == "upscaling":
            scale = need.constraints.get("scale", 2)
            return self.pattern_templates["upscaling"].get(f"{scale}x")
        
        # 例如：文生图模板
        if need.category == "generation" and need.modality == "image":
            return self.pattern_templates["text_to_image"]["basic"]
        
        return None
    
    def _instantiate_template(
        self,
        template: Dict,
        need: AtomicNeed
    ) -> WorkflowFragment:
        """实例化模板"""
        
        # 替换模板中的参数
        code = template["code_template"]
        
        # 替换约束条件
        for key, value in need.constraints.items():
            placeholder = f"{{{{key}}}}"
            code = code.replace(placeholder, str(value))
        
        # 生成节点JSON
        node_json = code_to_json(code)
        
        return WorkflowFragment(
            fragment_id=f"generated_{need.need_id}",
            source_workflow_id="template",
            code_snippet=code,
            node_json=node_json,
            mapped_need_id=need.need_id,
            # ... 其他字段
        )
    
    def _search_nodes_by_function(
        self,
        need: AtomicNeed
    ) -> List[str]:
        """基于功能搜索相关节点"""
        
        # 在节点库中搜索
        query = f"{need.category} {need.modality}"
        
        relevant_nodes = []
        for node_name, node_info in self.node_library.items():
            # 计算语义相似度
            similarity = semantic_similarity(
                query,
                node_info["description"]
            )
            
            if similarity > 0.7:
                relevant_nodes.append(node_name)
        
        return relevant_nodes
    
    def _compose_from_nodes(
        self,
        node_types: List[str],
        need: AtomicNeed
    ) -> WorkflowFragment:
        """从节点组合生成片段"""
        
        # 使用前作的模块工作流构建逻辑
        # 参考yaml_to_workflow.py的生成逻辑
        
        # 1. 确定节点顺序
        ordered_nodes = self._determine_node_order(node_types, need)
        
        # 2. 生成代码
        code = self._generate_code_from_nodes(ordered_nodes, need)
        
        # 3. 转换为JSON
        node_json = code_to_json(code)
        
        return WorkflowFragment(
            fragment_id=f"composed_{need.need_id}",
            source_workflow_id="composition",
            code_snippet=code,
            node_json=node_json,
            mapped_need_id=need.need_id,
            # ... 其他字段
        )
    
    def _llm_generate(self, need: AtomicNeed) -> WorkflowFragment:
        """使用LLM生成片段（谨慎使用）"""
        
        prompt = f"""
生成一个ComfyUI工作流片段来实现以下需求：

需求描述: {need.description}
类别: {need.category}
模态: {need.modality}
约束: {need.constraints}

请生成Python风格的代码表示，格式如下：
model, clip, vae = CheckpointLoaderSimple(ckpt_name="model.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="prompt")
...

只返回代码，不要其他解释。
"""
        
        llm_code = self.llm.generate(prompt)
        
        # 验证生成的代码
        try:
            node_json = code_to_json(llm_code)
            
            return WorkflowFragment(
                fragment_id=f"llm_generated_{need.need_id}",
                source_workflow_id="llm",
                code_snippet=llm_code,
                node_json=node_json,
                mapped_need_id=need.need_id,
                # ... 其他字段
            )
        except Exception as e:
            raise ValueError(f"LLM生成的代码无效: {e}")
```

### 2.3 完整性检查 → 语义检查 + 语法检查

#### 目标
检查工作流框架是否完整、正确

#### 实现算法

```python
class WorkflowValidator:
    """工作流验证器"""
    
    def validate(self, framework: WorkflowFramework) -> Tuple[bool, List[str]]:
        """
        验证工作流框架
        
        返回: (is_valid, error_messages)
        """
        
        errors = []
        
        # 1. 语法检查
        syntax_errors = self._check_syntax(framework)
        errors.extend(syntax_errors)
        
        # 2. 语义检查
        semantic_errors = self._check_semantics(framework)
        errors.extend(semantic_errors)
        
        # 3. 完整性检查
        completeness_errors = self._check_completeness(framework)
        errors.extend(completeness_errors)
        
        return len(errors) == 0, errors
    
    def _check_syntax(self, framework: WorkflowFramework) -> List[str]:
        """
        语法检查
        
        检查项：
        1. DAG结构有效（无环）
        2. 节点ID唯一
        3. 节点类型有效
        4. 输入输出类型匹配
        """
        
        errors = []
        
        # 将代码转换为JSON
        try:
            workflow_json = code_to_json(framework.framework_code)
        except Exception as e:
            errors.append(f"代码转JSON失败: {e}")
            return errors
        
        # 1. DAG检查（使用前作算法）
        if not is_valid_dag(workflow_json):
            errors.append("DAG结构无效（存在环或不连通）")
        
        # 2. 节点ID唯一性
        node_ids = set()
        for node_id in workflow_json.keys():
            if node_id in node_ids:
                errors.append(f"重复的节点ID: {node_id}")
            node_ids.add(node_id)
        
        # 3. 节点类型有效性
        valid_node_types = set(self.node_library.keys())
        for node_id, node in workflow_json.items():
            if node['class_type'] not in valid_node_types:
                errors.append(f"无效的节点类型: {node['class_type']} (节点{node_id})")
        
        # 4. 类型匹配检查
        type_errors = self._check_type_compatibility(workflow_json)
        errors.extend(type_errors)
        
        return errors
    
    def _check_type_compatibility(self, workflow_json: Dict) -> List[str]:
        """检查类型兼容性"""
        
        errors = []
        
        for node_id, node in workflow_json.items():
            for input_name, input_value in node['inputs'].items():
                # 如果是节点连接
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_node_id, output_slot = input_value
                    
                    # 获取源节点的输出类型
                    source_node = workflow_json.get(str(source_node_id))
                    if not source_node:
                        errors.append(
                            f"节点{node_id}引用了不存在的节点{source_node_id}"
                        )
                        continue
                    
                    source_output_type = self._get_output_type(
                        source_node,
                        output_slot
                    )
                    
                    # 获取当前节点期望的输入类型
                    expected_input_type = self._get_expected_input_type(
                        node,
                        input_name
                    )
                    
                    # 检查兼容性
                    if not self._type_compatible(source_output_type, expected_input_type):
                        errors.append(
                            f"类型不匹配: 节点{source_node_id}的输出类型"
                            f"{source_output_type}与节点{node_id}的输入{input_name}"
                            f"期望类型{expected_input_type}不兼容"
                        )
        
        return errors
    
    def _check_semantics(self, framework: WorkflowFramework) -> List[str]:
        """
        语义检查
        
        检查项：
        1. 工作流逻辑合理性
        2. 必要节点存在（如SaveImage）
        3. 参数合理性
        """
        
        errors = []
        
        workflow_json = code_to_json(framework.framework_code)
        
        # 1. 检查是否有输出节点
        has_output = False
        output_node_types = ['SaveImage', 'SaveVideo', 'PreviewImage']
        
        for node in workflow_json.values():
            if node['class_type'] in output_node_types:
                has_output = True
                break
        
        if not has_output:
            errors.append("工作流缺少输出节点（SaveImage/SaveVideo等）")
        
        # 2. 检查逻辑链路完整性
        start_nodes, end_nodes = find_start_end_nodes(workflow_json)
        
        if not start_nodes:
            errors.append("工作流没有起始节点")
        
        if not end_nodes:
            errors.append("工作流没有结束节点")
        
        # 3. 检查参数合理性
        param_errors = self._check_parameters(workflow_json)
        errors.extend(param_errors)
        
        return errors
    
    def _check_completeness(self, framework: WorkflowFramework) -> List[str]:
        """
        完整性检查
        
        检查所有片段是否正确拼接
        """
        
        errors = []
        
        # 检查片段间的连接
        for i in range(len(framework.fragments) - 1):
            curr_fragment = framework.fragments[i]
            next_fragment = framework.fragments[i + 1]
            
            # 检查curr的输出是否被next消费
            curr_outputs = set(curr_fragment.outputs.values())
            next_inputs = set(next_fragment.inputs.values())
            
            # 应该至少有一个类型匹配
            if not (curr_outputs & next_inputs):
                errors.append(
                    f"片段{curr_fragment.fragment_id}和"
                    f"{next_fragment.fragment_id}之间没有数据流连接"
                )
        
        return errors
```

---

## 🔨 阶段3: 可执行工作流合成

### 3.1 工作流框架 → JSON转换

#### 目标
将工作流框架（代码表示）转换为可执行的JSON格式

#### 实现算法

```python
class WorkflowSynthesizer:
    """工作流合成器"""
    
    def synthesize(
        self,
        framework: WorkflowFramework,
        user_request: UserRequest,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        合成可执行工作流
        
        输入：
        - framework: 验证通过的工作流框架
        - user_request: 原始用户需求（用于参数补全）
        - context: 上下文信息（如输入文件路径）
        
        输出：
        - 可执行的JSON工作流
        """
        
        # 1. 代码 → JSON转换（使用已有的双向解析器）
        workflow_json = code_to_json(framework.framework_code)
        
        # 2. 参数补全和优化
        workflow_json = self._complete_parameters(
            workflow_json,
            user_request,
            context
        )
        
        # 3. 最终验证
        is_valid, errors = self._final_validation(workflow_json)
        if not is_valid:
            raise ValueError(f"最终验证失败: {errors}")
        
        return workflow_json
    
    def _complete_parameters(
        self,
        workflow_json: Dict,
        user_request: UserRequest,
        context: Optional[Dict]
    ) -> Dict:
        """
        参数补全
        
        补全内容：
        1. 提示词（从用户需求中提取）
        2. 文件路径（从上下文中获取）
        3. 默认参数（seed、步数等）
        """
        
        # 1. 补全提示词
        workflow_json = self._fill_prompts(workflow_json, user_request)
        
        # 2. 补全文件路径
        if context and "input_file" in context:
            workflow_json = self._fill_input_paths(
                workflow_json,
                context["input_file"]
            )
        
        # 3. 补全输出文件名
        workflow_json = self._fill_output_names(workflow_json, context)
        
        # 4. 补全默认参数
        workflow_json = self._fill_default_parameters(workflow_json)
        
        return workflow_json
    
    def _fill_prompts(
        self,
        workflow_json: Dict,
        user_request: UserRequest
    ) -> Dict:
        """填充提示词"""
        
        # 提取用户需求中的关键描述
        prompt = self._extract_prompt_from_request(user_request.raw_text)
        
        # 找到所有文本编码节点
        for node_id, node in workflow_json.items():
            if node['class_type'] in ['CLIPTextEncode', 'CLIPTextEncodeSDXL']:
                # 检查text字段是否为空或占位符
                if 'text' in node['inputs']:
                    current_text = node['inputs']['text']
                    if not current_text or current_text == "" or current_text.startswith("{"):
                        node['inputs']['text'] = prompt
        
        return workflow_json
    
    def _fill_input_paths(
        self,
        workflow_json: Dict,
        input_file: str
    ) -> Dict:
        """填充输入文件路径"""
        
        # 找到所有加载节点
        for node_id, node in workflow_json.items():
            if node['class_type'] in ['LoadImage', 'LoadVideo']:
                if 'image' in node['inputs']:
                    node['inputs']['image'] = input_file
                elif 'video' in node['inputs']:
                    node['inputs']['video'] = input_file
        
        return workflow_json
    
    def _fill_output_names(
        self,
        workflow_json: Dict,
        context: Optional[Dict]
    ) -> Dict:
        """填充输出文件名"""
        
        output_prefix = context.get("output_prefix", "comfyui_output") if context else "comfyui_output"
        
        # 找到所有保存节点
        for node_id, node in workflow_json.items():
            if node['class_type'] in ['SaveImage', 'SaveVideo']:
                if 'filename_prefix' in node['inputs']:
                    node['inputs']['filename_prefix'] = output_prefix
        
        return workflow_json
    
    def _fill_default_parameters(self, workflow_json: Dict) -> Dict:
        """填充默认参数"""
        
        # 为采样器设置默认参数
        for node_id, node in workflow_json.items():
            if node['class_type'] == 'KSampler':
                # seed（如果为空，使用随机）
                if 'seed' not in node['inputs'] or node['inputs']['seed'] == 0:
                    node['inputs']['seed'] = random.randint(0, 2**32 - 1)
                
                # steps（如果为空，使用默认20）
                if 'steps' not in node['inputs']:
                    node['inputs']['steps'] = 20
                
                # cfg（如果为空，使用默认7.0）
                if 'cfg' not in node['inputs']:
                    node['inputs']['cfg'] = 7.0
        
        return workflow_json
    
    def _final_validation(self, workflow_json: Dict) -> Tuple[bool, List[str]]:
        """最终验证"""
        
        errors = []
        
        # 1. 检查所有必需参数是否已填充
        for node_id, node in workflow_json.items():
            node_type = node['class_type']
            required_params = self._get_required_parameters(node_type)
            
            for param in required_params:
                if param not in node['inputs'] or node['inputs'][param] is None:
                    errors.append(
                        f"节点{node_id}({node_type})缺少必需参数: {param}"
                    )
        
        # 2. 再次检查DAG有效性
        if not is_valid_dag(workflow_json):
            errors.append("最终DAG结构无效")
        
        return len(errors) == 0, errors
```

---

## 🔄 完整流程示例

```python
class ComfyUIWorkflowGenerator:
    """ComfyUI工作流生成系统主类"""
    
    def __init__(self, config: Dict):
        # 初始化各个组件
        self.workflow_library = WorkflowLibrary(config['library_path'])
        self.need_decomposer = NeedDecomposer(config['llm_client'])
        self.need_matcher = NeedWorkflowMatcher(self.workflow_library)
        self.workflow_adapter = WorkflowAdapter()
        self.fragment_generator = FragmentGenerator(config['node_library'])
        self.workflow_validator = WorkflowValidator()
        self.workflow_synthesizer = WorkflowSynthesizer()
    
    def generate(
        self,
        user_request: UserRequest,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        完整生成流程
        """
        
        # === 阶段1: 需求匹配 ===
        
        # 1.1 需求分解
        decomposed = self.need_decomposer.decompose(user_request)
        atomic_needs = decomposed.atomic_needs
        
        # 1.2 & 1.3 意图匹配 + 确定匹配/未匹配
        match_results = self.need_matcher.match_all(atomic_needs)
        
        # === 阶段2: 工作流框架级别适配 ===
        
        # 2.1 拆分-映射-拼接
        framework = self.workflow_adapter.adapt(
            atomic_needs,
            match_results
        )
        
        # 2.2 生成缺失片段
        for i, match in enumerate(match_results):
            if not match.matched:
                # 生成缺失的片段
                generated_fragment = self.fragment_generator.generate_fragment(
                    atomic_needs[i]
                )
                
                # 插入到框架中
                framework.fragments.insert(i, generated_fragment)
        
        # 重新组装（插入了新片段后）
        framework = self.workflow_adapter.fragment_assembler.assemble(
            framework.fragments,
            atomic_needs
        )
        
        # 2.3 完整性检查
        is_valid, errors = self.workflow_validator.validate(framework)
        
        if not is_valid:
            # 尝试修复或报告错误
            raise ValueError(f"工作流框架验证失败: {errors}")
        
        # === 阶段3: 可执行工作流合成 ===
        
        # 3.1 转换为JSON + 参数补全
        workflow_json = self.workflow_synthesizer.synthesize(
            framework,
            user_request,
            context
        )
        
        return workflow_json

# 使用示例
def main():
    # 配置
    config = {
        'library_path': './data/workflow_library',
        'llm_client': OpenAIClient(api_key="..."),
        'node_library': load_node_library('./data/node_meta.json')
    }
    
    # 初始化生成器
    generator = ComfyUIWorkflowGenerator(config)
    
    # 用户需求
    request = UserRequest(
        raw_text="生成一个粘土风格的人物肖像，并进行4倍超分"
    )
    
    # 生成工作流
    workflow_json = generator.generate(request)
    
    # 保存
    with open('output_workflow.json', 'w') as f:
        json.dump(workflow_json, f, indent=2)
    
    print("工作流生成完成！")

if __name__ == "__main__":
    main()
```

---

## 📅 实施计划（8-10周）

### Week 1-2: 基础设施
- [ ] 设计和实现数据结构（WorkflowEntry, AtomicCapability等）
- [ ] 建立工作流库存储系统
- [ ] 从前作提取拼接算法
- [ ] 完善双向解析器（JSON ↔ Code）

### Week 3-4: 工作流库构建
- [ ] 爬取ComfyBench的20个curriculum workflows
- [ ] 爬取社区工作流（OpenArt, Civitai）
- [ ] 实现自动标注流程（意图提取、能力提取）
- [ ] 人工审核和补充
- [ ] 构建向量索引

### Week 5-6: 需求匹配（阶段1）
- [ ] 实现NeedDecomposer（需求分解）
- [ ] 实现IntentMatcher（意图匹配）
- [ ] 实现NeedWorkflowMatcher（匹配决策）
- [ ] 端到端测试

### Week 7-8: 工作流适配（阶段2核心）
- [ ] 实现FragmentSplitter（工作流拆分）
- [ ] 实现片段-需求映射算法
- [ ] 实现FragmentAssembler（拼接算法）
- [ ] 实现FragmentGenerator（缺失片段生成）
- [ ] 实现WorkflowValidator（验证器）

### Week 9: 工作流合成（阶段3）
- [ ] 实现WorkflowSynthesizer（参数补全）
- [ ] 实现最终验证
- [ ] 端到端集成测试

### Week 10: 评估和优化
- [ ] 在ComfyBench上评估
- [ ] Pass Rate统计
- [ ] 与ComfyAgent、R1对比
- [ ] Bug修复和优化

---

这是一个完整、详细、可执行的设计方案。关键点：

1. ✅ **严格遵循你的三阶段框架**
2. ✅ **复用前作的严谨算法**（保证高Pass Rate）
3. ✅ **融合ComfyBench和生态化思想**
4. ✅ **每个步骤都有具体算法和数据结构**
5. ✅ **可直接编码实现**

需要我展开哪个具体模块的实现吗？
