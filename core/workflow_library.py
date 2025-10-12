"""
工作流库管理模块
负责工作流的存储、索引、检索和管理
"""

import os
import json
from typing import Dict, List, Optional, Any, Tuple
from core.data_structures import WorkflowEntry, WorkflowIntent, WorkflowComplexity
from core.llm_client import LLMClient
from core.vector_search import VectorIndex
from core.utils import generate_workflow_id, extract_node_types_from_json, save_json, load_json
import prompts


class WorkflowLibrary:
    """工作流库"""
    
    def __init__(
        self,
        data_path: str,
        llm_client: Optional[LLMClient] = None,
        vector_index: Optional[VectorIndex] = None,
        vector_index_path: Optional[str] = None
    ):
        """
        初始化工作流库
        
        Args:
            data_path: 数据存储路径
            llm_client: LLM客户端（用于意图提取和embedding）
            vector_index: 向量索引
            vector_index_path: 向量索引保存路径
        """
        self.data_path = data_path
        self.llm = llm_client
        self.vector_index = vector_index
        self.vector_index_path = vector_index_path or os.path.join(data_path, 'embeddings.faiss')
        
        # 工作流字典
        self.workflows: Dict[str, WorkflowEntry] = {}
        
        # 索引
        self.tag_index: Dict[str, List[str]] = {}  # {tag: [workflow_ids]}
        self.category_index: Dict[str, List[str]] = {}  # {category: [workflow_ids]}
        
        # 创建目录
        os.makedirs(data_path, exist_ok=True)
        os.makedirs(os.path.join(data_path, 'workflows'), exist_ok=True)
        os.makedirs(os.path.join(data_path, 'metadata'), exist_ok=True)
        
        # 加载已有工作流
        self._load_library()
        
        # 加载向量索引
        self._load_vector_index()
    
    def add_workflow(
        self,
        workflow_json: Dict[str, Any],
        workflow_code: str,
        intent: Optional[WorkflowIntent] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_annotate: bool = True
    ) -> WorkflowEntry:
        """
        添加工作流到库
        
        Args:
            workflow_json: 工作流JSON
            workflow_code: 工作流代码
            intent: 工作流意图（如果None且auto_annotate=True则自动提取）
            metadata: 元数据
            auto_annotate: 是否自动标注意图
            
        Returns:
            工作流条目
        """
        # 生成ID
        workflow_id = generate_workflow_id()
        
        # 提取意图（如果需要）
        if intent is None and auto_annotate and self.llm:
            intent = self._extract_intent(workflow_json, workflow_code)
        elif intent is None:
            # 默认意图
            intent = WorkflowIntent(
                task="unknown",
                description="未标注的工作流",
                keywords=[],
                modality="image",
                operation="generation"
            )
        
        # 生成embedding
        intent_embedding = None
        if self.llm:
            intent_embedding = self.llm.embed(intent.description)
        
        # 创建工作流条目
        entry = WorkflowEntry(
            workflow_id=workflow_id,
            workflow_json=workflow_json,
            workflow_code=workflow_code,
            intent=intent,
            intent_embedding=intent_embedding,
            source=metadata.get('source', 'unknown') if metadata else 'unknown',
            complexity=WorkflowComplexity(metadata.get('complexity', 'vanilla')) if metadata else WorkflowComplexity.VANILLA,
            tags=metadata.get('tags', []) if metadata else [],
            node_count=len(workflow_json)
        )
        
        # 保存到内存
        self.workflows[workflow_id] = entry
        
        # 更新索引
        self._update_indexes(entry)
        
        # 添加到向量索引
        if self.vector_index and intent_embedding:
            self.vector_index.add_workflow(entry)
            # 保存向量索引
            self._save_vector_index()
        
        # 持久化
        self._save_workflow(entry)
        
        return entry
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowEntry]:
        """
        获取工作流
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流条目或None
        """
        return self.workflows.get(workflow_id)
    
    def search_by_tags(self, tags: List[str]) -> List[WorkflowEntry]:
        """
        根据标签搜索
        
        Args:
            tags: 标签列表
            
        Returns:
            工作流列表
        """
        workflow_ids = set()
        
        for tag in tags:
            if tag in self.tag_index:
                workflow_ids.update(self.tag_index[tag])
        
        return [self.workflows[wid] for wid in workflow_ids if wid in self.workflows]
    
    def search_by_category(self, category: str) -> List[WorkflowEntry]:
        """
        根据类别搜索
        
        Args:
            category: 类别
            
        Returns:
            工作流列表
        """
        workflow_ids = self.category_index.get(category, [])
        return [self.workflows[wid] for wid in workflow_ids if wid in self.workflows]
    
    def list_all(self) -> List[WorkflowEntry]:
        """
        列出所有工作流
        
        Returns:
            工作流列表
        """
        return list(self.workflows.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取库统计信息
        
        Returns:
            统计信息
        """
        return {
            'total_count': len(self.workflows),
            'by_complexity': self._count_by_complexity(),
            'by_source': self._count_by_source(),
            'avg_node_count': self._avg_node_count(),
            'top_tags': self._top_tags(10)
        }
    
    def _extract_intent(
        self,
        workflow_json: Dict[str, Any],
        workflow_code: str
    ) -> WorkflowIntent:
        """
        使用LLM提取工作流意图
        
        Args:
            workflow_json: 工作流JSON
            workflow_code: 工作流代码
            
        Returns:
            工作流意图
        """
        node_types = extract_node_types_from_json(workflow_json)
        
        prompt = prompts.WORKFLOW_INTENT_EXTRACTION_PROMPT.format(
            workflow_code=workflow_code,
            node_types=', '.join(node_types)
        )
        
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长分析工作流功能。",
            json_mode=True,
            temperature=0.3
        )
        
        parsed = self.llm.parse_json_response(response)
        
        if parsed:
            return WorkflowIntent(
                task=parsed.get('task', 'unknown'),
                description=parsed.get('description', ''),
                keywords=parsed.get('keywords', []),
                modality=parsed.get('modality', 'image'),
                operation=parsed.get('operation', 'generation'),
                style=parsed.get('style')
            )
        else:
            # 回退到简单规则
            return self._rule_based_intent(node_types)
    
    def _rule_based_intent(self, node_types: List[str]) -> WorkflowIntent:
        """
        基于规则的简单意图提取
        
        Args:
            node_types: 节点类型列表
            
        Returns:
            工作流意图
        """
        # 简单规则
        if 'KSampler' in node_types:
            task = 'text-to-image'
            operation = 'generation'
        elif any('Upscale' in t for t in node_types):
            task = 'upscaling'
            operation = 'upscaling'
        elif 'ControlNet' in ' '.join(node_types):
            task = 'image-to-image'
            operation = 'editing'
        else:
            task = 'unknown'
            operation = 'generation'
        
        return WorkflowIntent(
            task=task,
            description=f"ComfyUI {task} workflow",
            keywords=node_types[:5],
            modality='image',
            operation=operation
        )
    
    def _update_indexes(self, entry: WorkflowEntry):
        """
        更新索引
        
        Args:
            entry: 工作流条目
        """
        # 标签索引
        for tag in entry.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            self.tag_index[tag].append(entry.workflow_id)
        
        # 类别索引
        category = entry.intent.operation
        if category not in self.category_index:
            self.category_index[category] = []
        self.category_index[category].append(entry.workflow_id)
    
    def _save_workflow(self, entry: WorkflowEntry):
        """
        持久化工作流
        
        Args:
            entry: 工作流条目
        """
        # 保存JSON
        json_path = os.path.join(
            self.data_path,
            'workflows',
            f'{entry.workflow_id}.json'
        )
        save_json(entry.workflow_json, json_path)
        
        # 保存元数据
        metadata = {
            'workflow_id': entry.workflow_id,
            'workflow_code': entry.workflow_code,
            'intent': {
                'task': entry.intent.task,
                'description': entry.intent.description,
                'keywords': entry.intent.keywords,
                'modality': entry.intent.modality,
                'operation': entry.intent.operation,
                'style': entry.intent.style
            },
            'intent_embedding': entry.intent_embedding,  # 保存embedding
            'source': entry.source,
            'complexity': entry.complexity.value,
            'tags': entry.tags,
            'node_count': entry.node_count,
            'usage_count': entry.usage_count,
            'success_rate': entry.success_rate,
            'avg_execution_time': entry.avg_execution_time
        }
        
        metadata_path = os.path.join(
            self.data_path,
            'metadata',
            f'{entry.workflow_id}.meta.json'
        )
        save_json(metadata, metadata_path)
    
    def _load_library(self):
        """加载已有工作流"""
        metadata_dir = os.path.join(self.data_path, 'metadata')
        workflows_dir = os.path.join(self.data_path, 'workflows')
        
        if not os.path.exists(metadata_dir):
            return
        
        for filename in os.listdir(metadata_dir):
            if not filename.endswith('.meta.json'):
                continue
            
            metadata_path = os.path.join(metadata_dir, filename)
            workflow_id = filename.replace('.meta.json', '')
            
            try:
                # 加载元数据
                metadata = load_json(metadata_path)
                
                # 加载JSON
                json_path = os.path.join(workflows_dir, f'{workflow_id}.json')
                workflow_json = load_json(json_path)
                
                # 构建意图
                intent_data = metadata['intent']
                intent = WorkflowIntent(
                    task=intent_data['task'],
                    description=intent_data['description'],
                    keywords=intent_data['keywords'],
                    modality=intent_data['modality'],
                    operation=intent_data['operation'],
                    style=intent_data.get('style')
                )
                
                # 创建条目
                entry = WorkflowEntry(
                    workflow_id=workflow_id,
                    workflow_json=workflow_json,
                    workflow_code=metadata['workflow_code'],
                    intent=intent,
                    intent_embedding=metadata.get('intent_embedding'),  # 从文件加载
                    source=metadata.get('source', 'unknown'),
                    complexity=WorkflowComplexity(metadata.get('complexity', 'vanilla')),
                    tags=metadata.get('tags', []),
                    node_count=metadata.get('node_count', 0),
                    usage_count=metadata.get('usage_count', 0),
                    success_rate=metadata.get('success_rate', 1.0),
                    avg_execution_time=metadata.get('avg_execution_time', 0.0)
                )
                
                self.workflows[workflow_id] = entry
                self._update_indexes(entry)
                
                # 注意：不要重复添加到vector_index，因为已经从.faiss文件加载了
                
            except Exception as e:
                print(f"加载工作流 {workflow_id} 失败: {e}")
    
    def _count_by_complexity(self) -> Dict[str, int]:
        """按复杂度统计"""
        counts = {}
        for workflow in self.workflows.values():
            key = workflow.complexity.value
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    def _count_by_source(self) -> Dict[str, int]:
        """按来源统计"""
        counts = {}
        for workflow in self.workflows.values():
            key = workflow.source
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    def _avg_node_count(self) -> float:
        """平均节点数"""
        if not self.workflows:
            return 0.0
        total = sum(w.node_count for w in self.workflows.values())
        return total / len(self.workflows)
    
    def _top_tags(self, n: int) -> List[Tuple[str, int]]:
        """最常用标签"""
        tag_counts = {tag: len(wids) for tag, wids in self.tag_index.items()}
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_tags[:n]
    
    def _save_vector_index(self):
        """保存向量索引"""
        if self.vector_index and self.vector_index.index.ntotal > 0:
            try:
                self.vector_index.save(self.vector_index_path)
                print(f"[DEBUG] 向量索引已保存到: {self.vector_index_path}")
            except Exception as e:
                print(f"[WARN] 保存向量索引失败: {e}")
    
    def _load_vector_index(self):
        """加载向量索引"""
        if self.vector_index and os.path.exists(self.vector_index_path):
            try:
                self.vector_index.load(self.vector_index_path)
                print(f"[DEBUG] 向量索引已加载，包含 {self.vector_index.index.ntotal} 个向量")
            except Exception as e:
                print(f"[WARN] 加载向量索引失败: {e}，将使用新索引")
