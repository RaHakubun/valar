"""
向量检索模块
基于FAISS的向量检索 + Reranker重排序
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from .data_structures import WorkflowEntry, AtomicNeed
from .llm_client import LLMClient

try:
    import faiss
except ImportError:
    print("警告: faiss未安装，向量检索功能不可用")
    faiss = None

import requests
import json as json_module


class VectorIndex:
    """向量索引管理器"""
    
    def __init__(self, dimension: int = 3072):
        """
        初始化向量索引
        
        Args:
            dimension: 向量维度（OpenAI text-embedding-3-large为3072）
        """
        self.dimension = dimension
        
        if faiss is None:
            raise ImportError("请安装faiss: pip install faiss-cpu")
        
        # 使用L2距离的索引
        self.index = faiss.IndexFlatL2(dimension)
        
        # ID映射
        self.id_to_workflow = {}  # {索引位置: workflow_id}
        self.workflow_to_id = {}  # {workflow_id: 索引位置}
        
        self.current_index = 0
    
    def add_workflow(self, workflow: WorkflowEntry):
        """
        添加工作流到索引
        
        Args:
            workflow: 工作流条目
        """
        if workflow.intent_embedding is None:
            print(f"警告: 工作流 {workflow.workflow_id} 没有embedding")
            return
        
        # 转换为numpy数组
        embedding = np.array([workflow.intent_embedding], dtype='float32')
        
        # 添加到索引
        self.index.add(embedding)
        
        # 记录映射
        self.id_to_workflow[self.current_index] = workflow.workflow_id
        self.workflow_to_id[workflow.workflow_id] = self.current_index
        
        self.current_index += 1
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 50
    ) -> List[Tuple[int, float]]:
        """
        搜索最相似的工作流
        
        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            
        Returns:
            [(索引位置, 距离)] 列表
        """
        if self.index.ntotal == 0:
            return []
        
        # 转换为numpy数组
        query = np.array([query_embedding], dtype='float32')
        
        # 搜索
        distances, indices = self.index.search(query, min(top_k, self.index.ntotal))
        
        # 返回结果
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:  # FAISS返回-1表示无结果
                results.append((int(idx), float(distances[0][i])))
        
        return results
    
    def get_workflow_id(self, index: int) -> Optional[str]:
        """
        根据索引位置获取workflow_id
        
        Args:
            index: 索引位置
            
        Returns:
            workflow_id或None
        """
        return self.id_to_workflow.get(index)
    
    def save(self, file_path: str):
        """
        保存索引到文件
        
        Args:
            file_path: 文件路径
        """
        faiss.write_index(self.index, file_path)
        
        # 保存映射（使用json）
        import json
        mapping_path = file_path + '.mapping.json'
        with open(mapping_path, 'w') as f:
            json.dump({
                'id_to_workflow': self.id_to_workflow,
                'workflow_to_id': self.workflow_to_id,
                'current_index': self.current_index
            }, f)
    
    def load(self, file_path: str):
        """
        从文件加载索引
        
        Args:
            file_path: 文件路径
        """
        self.index = faiss.read_index(file_path)
        
        # 加载映射
        import json
        mapping_path = file_path + '.mapping.json'
        with open(mapping_path, 'r') as f:
            data = json.load(f)
            self.id_to_workflow = {int(k): v for k, v in data['id_to_workflow'].items()}
            self.workflow_to_id = data['workflow_to_id']
            self.current_index = data['current_index']


class Reranker:
    """重排序器 - 支持API和本地模型两种方式"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Reranker
        
        Args:
            config: reranker配置字典
        """
        self.config = config
        self.type = config.get('type', 'api')
        
        if self.type == 'api':
            # API模式
            self.api_url = config.get('api_url', 'https://api.siliconflow.cn/v1/rerank')
            self.api_key = config.get('api_key')
            self.model_name = config.get('model', 'Pro/BAAI/bge-reranker-v2-m3')
            self.max_chunks_per_doc = config.get('max_chunks_per_doc', 1024)
            self.overlap_tokens = config.get('overlap_tokens', 80)
            print(f"[Reranker] 使用API模式: {self.model_name}")
        else:
            # 本地模型模式（已废弃）
            raise NotImplementedError("本地reranker已废弃，请使用API模式")
    
    def rerank(
        self,
        query: str,
        candidates: List[WorkflowEntry],
        top_k: int = 10
    ) -> List[WorkflowEntry]:
        """
        重排序候选工作流
        
        Args:
            query: 查询文本
            candidates: 候选工作流列表
            top_k: 返回数量
            
        Returns:
            重排序后的工作流列表
        """
        if not candidates:
            print("[Reranker] 警告: 候选列表为空")
            return []
        
        print(f"[Reranker] 开始重排序: {len(candidates)} 个候选")
        
        try:
            if self.type == 'api':
                return self._rerank_api(query, candidates, top_k)
            else:
                raise NotImplementedError("本地reranker已废弃")
        except Exception as e:
            print(f"[Reranker] 错误: {e}, 使用原始顺序")
            import traceback
            traceback.print_exc()
            return candidates[:top_k]
    
    def _rerank_api(
        self,
        query: str,
        candidates: List[WorkflowEntry],
        top_k: int
    ) -> List[WorkflowEntry]:
        """使用API进行重排序"""
        # 构建 documents 列表（使用 workflow 的 intent.description）
        documents = [candidate.intent.description for candidate in candidates]
        
        # 构建 API 请求
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "top_n": min(top_k, len(documents)),  # 不超过候选数量
            "return_documents": True,
            "max_chunks_per_doc": self.max_chunks_per_doc,
            "overlap_tokens": self.overlap_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 调用API
        print(f"[Reranker] 调用API: {self.api_url}")
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"[Reranker] API错误: {response.status_code}")
            print(response.text)
            return candidates[:top_k]
        
        # 解析结果
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            print(f"[Reranker] API返回结果为空")
            return candidates[:top_k]
        
        print(f"[Reranker] API返回 {len(results)} 个结果")
        
        # 根据返回的索引重新排序
        reranked_candidates = []
        for item in results:
            index = item['index']
            score = item['relevance_score']
            
            if 0 <= index < len(candidates):
                reranked_candidates.append(candidates[index])
                if len(reranked_candidates) <= 3:  # 只打印前3个
                    print(f"  {len(reranked_candidates)}. {candidates[index].workflow_id}: {candidates[index].intent.description[:60]}... (得分: {score:.4f})")
        
        print(f"[Reranker] 重排序完成")
        return reranked_candidates[:top_k]


class WorkflowRetriever:
    """工作流检索器（整合向量检索和重排序）"""
    
    def __init__(
        self,
        llm_client: LLMClient,
        vector_index: VectorIndex,
        reranker: Reranker,
        workflow_library: Dict[str, WorkflowEntry]
    ):
        """
        初始化检索器
        
        Args:
            llm_client: LLM客户端（用于生成embedding）
            vector_index: 向量索引
            reranker: 重排序器
            workflow_library: 工作流库
        """
        self.llm = llm_client
        self.vector_index = vector_index
        self.reranker = reranker
        self.workflow_library = workflow_library
    
    def retrieve(
        self,
        atomic_need: AtomicNeed,
        top_k_recall: int = 9,
        top_k_rerank: int = 3
    ) -> List[WorkflowEntry]:
        """
        检索相关工作流
        
        Args:
            atomic_need: 原子需求
            top_k_recall: 向量召回数量
            top_k_rerank: 重排序后返回数量
            
        Returns:
            工作流列表
        """
        # 1. 生成查询embedding
        query_text = atomic_need.description
        query_embedding = self.llm.embed(query_text)
        
        if query_embedding is None:
            print("生成embedding失败")
            return []
        
        # 2. 向量召回
        search_results = self.vector_index.search(query_embedding, top_k_recall)
        
        # 3. 转换为WorkflowEntry对象
        candidates = []
        for index, distance in search_results:
            workflow_id = self.vector_index.get_workflow_id(index)
            if workflow_id and workflow_id in self.workflow_library:
                candidates.append(self.workflow_library[workflow_id])
        
        if not candidates:
            return []
        
        print(f"[VectorSearch] 向量检索返回 {len(candidates)} 个候选")
        
        # 4. 重排序（限制最多20个候选，避免reranker崩溃）
        max_rerank_candidates = 4
        if len(candidates) > max_rerank_candidates:
            print(f"[VectorSearch] 候选过多，只对前 {max_rerank_candidates} 个进行rerank")
            candidates = candidates[:max_rerank_candidates]
        
        reranked = self.reranker.rerank(query_text, candidates, top_k_rerank)
        
        return reranked
    
    def retrieve_for_all_needs(
        self,
        atomic_needs: List[AtomicNeed],
        top_k_per_need: int = 5
    ) -> Dict[str, List[WorkflowEntry]]:
        """
        为所有原子需求检索工作流
        
        Args:
            atomic_needs: 原子需求列表
            top_k_per_need: 每个需求返回的工作流数量
            
        Returns:
            {need_id: [workflows]} 映射
        """
        results = {}
        
        for need in atomic_needs:
            workflows = self.retrieve(
                need,
                top_k_recall=20,  # 降低召回数量，避免传给reranker过多
                top_k_rerank=top_k_per_need
            )
            results[need.need_id] = workflows
        
        return results
