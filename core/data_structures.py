"""
核心数据结构定义
基于论文思路，简化设计，去除预标注的原子能力
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class WorkflowComplexity(Enum):
    """工作流复杂度"""
    VANILLA = "vanilla"      # 简单，单一功能
    COMPLEX = "complex"      # 复杂，多功能组合
    CREATIVE = "creative"    # 创新，需要理解原理


@dataclass
class WorkflowIntent:
    """
    工作流意图（简化版）
    只存储整体意图，不预标注原子能力
    """
    task: str                           # "text-to-image", "upscaling"等
    description: str                    # 自然语言描述
    keywords: List[str]                 # 关键词列表
    modality: str                       # "image", "video", "3d"
    operation: str                      # "generation", "editing", "upscaling"
    style: Optional[str] = None         # "clay", "anime", "realistic"等


@dataclass
class WorkflowEntry:
    """
    工作流库中的条目（简化版）
    只存储工作流+意图，不预标注原子能力
    """
    workflow_id: str
    
    # 两种表示（双向转换）
    workflow_json: Dict[str, Any]       # 原始JSON（执行用）
    workflow_code: str                  # 代码表示（理解和拼接用）
    
    # 意图（自动标注或人工标注）
    intent: WorkflowIntent
    
    # 向量表示（用于检索）
    intent_embedding: Optional[List[float]] = None
    
    # 元数据
    source: str = "unknown"             # "comfybench", "openart", "manual"
    complexity: WorkflowComplexity = WorkflowComplexity.VANILLA
    tags: List[str] = field(default_factory=list)
    node_count: int = 0
    
    # 统计信息
    usage_count: int = 0
    success_rate: float = 1.0
    avg_execution_time: float = 0.0


@dataclass
class AtomicNeed:
    """
    原子需求（需求分解后的最小单元）
    """
    need_id: str
    description: str                    # "生成粘土风格人物肖像"
    category: str                       # "generation", "upscaling"
    modality: str                       # "image", "video"
    priority: int = 5                   # 优先级 1-10
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他need_id
    constraints: Dict[str, Any] = field(default_factory=dict)  # 约束条件

# priority 表示每个原子任务在整体任务图中的优先级等级（priority level）。
# 虽然拓扑排序 (execution_order) 已经决定了“必须先后”的依赖顺序，
# 但在 同一层（无直接依赖关系） 的节点之间，系统仍然可能需要一个“执行权重”来决定谁先跑。
# 典型用途
# 1. 多任务并行调度
# 假设你的分解结果如下：
# {
#   "dependency_graph": {
#     "N1": [],
#     "N2": ["N1"],
#     "N3": ["N1"]
#   }
# }
# N2 和 N3 没有相互依赖，可以并行执行。
# 但如果你希望优先执行视频生成任务 (N2)，再执行配图任务 (N3)，就可以用：
# "N2": priority=8
# "N3": priority=3
# 执行引擎在分配 GPU 或线程池任务时，就能按优先级排队。

@dataclass
class DecomposedNeeds:
    """分解后的需求"""
    atomic_needs: List[AtomicNeed]
    dependency_graph: Dict[str, List[str]]  # DAG结构
    execution_order: List[str]              # 拓扑排序后的执行顺序


@dataclass
class WorkflowFragment:
    """
    工作流片段（运行时动态拆分）
    """
    fragment_id: str
    source_workflow_id: str
    
    # 代码表示（核心）
    code: str
    
    # 功能描述（运行时生成）
    description: str = ""
    category: str = "unknown"
    
    # 输入输出类型（运行时分析）
    inputs: Dict[str, str] = field(default_factory=dict)   # {"clip": "CLIP", "text": "STRING"}
    outputs: Dict[str, str] = field(default_factory=dict)  # {"conditioning": "CONDITIONING"}
    
    # 映射到的原子需求（匹配后填充）
    mapped_need_id: Optional[str] = None
    match_confidence: float = 0.0


@dataclass
class MatchResult:
    """匹配结果"""
    need_id: str
    matched: bool
    confidence: float                   # 匹配置信度 0-1
    
    # 如果匹配上
    selected_workflow: Optional[WorkflowEntry] = None
    alternative_workflows: List[WorkflowEntry] = field(default_factory=list)
    
    # 如果没匹配上
    reason: Optional[str] = None


@dataclass
class WorkflowFramework:
    """
    工作流框架（片段组合后的中间表示）
    """
    framework_id: str
    fragments: List[WorkflowFragment]
    execution_order: List[str]          # fragment_id的执行顺序
    
    # 代码表示
    framework_code: str
    
    # 验证结果
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
