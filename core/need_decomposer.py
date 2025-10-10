"""
需求分解模块
使用LLM将用户需求分解为原子需求
"""

from typing import List, Dict, Any
from .data_structures import AtomicNeed, DecomposedNeeds
from .llm_client import LLMClient
from .utils import generate_need_id
import prompts


class NeedDecomposer:
    """需求分解器"""
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化需求分解器
        
        Args:
            llm_client: LLM客户端
        """
        self.llm = llm_client
    
    def decompose(self, user_request: str) -> DecomposedNeeds:
        """
        分解用户需求
        
        Args:
            user_request: 用户需求文本
            
        Returns:
            分解后的需求
        """
        # 构建提示词
        prompt = prompts.NEED_DECOMPOSITION_PROMPT.format(
            user_request=user_request
        )
        
        # 调用LLM
        response = self.llm.chat(
            prompt=prompt,
            system_message="你是ComfyUI工作流专家，擅长需求分析和分解。",
            json_mode=True
        )
        
        # 解析响应
        parsed = self.llm.parse_json_response(response)
        if not parsed or 'atomic_needs' not in parsed:
            print("需求分解失败，使用默认单一需求")
            return self._fallback_decomposition(user_request)
        
        # 构建AtomicNeed对象
        atomic_needs = []
        for need_data in parsed['atomic_needs']:
            atomic_need = AtomicNeed(
                need_id=need_data.get('need_id', generate_need_id()),
                description=need_data.get('description', ''),
                category=need_data.get('category', 'unknown'),
                modality=need_data.get('modality', 'image'),
                priority=need_data.get('priority', 5),
                dependencies=need_data.get('dependencies', []),
                constraints=need_data.get('constraints', {})
            )
            atomic_needs.append(atomic_need)
        
        # 构建依赖图
        dependency_graph = self._build_dependency_graph(atomic_needs)
        
        # 拓扑排序
        execution_order = self._topological_sort(dependency_graph)
        
        return DecomposedNeeds(
            atomic_needs=atomic_needs,
            dependency_graph=dependency_graph,
            execution_order=execution_order
        )
    
    def _fallback_decomposition(self, user_request: str) -> DecomposedNeeds:
        """
        回退方案：将整个需求作为单一原子需求
        
        Args:
            user_request: 用户需求
            
        Returns:
            单一需求的分解结果
        """
        need_id = generate_need_id()
        atomic_need = AtomicNeed(
            need_id=need_id,
            description=user_request,
            category='generation',
            modality='image',
            priority=10,
            dependencies=[],
            constraints={}
        )
        
        return DecomposedNeeds(
            atomic_needs=[atomic_need],
            dependency_graph={need_id: []},
            execution_order=[need_id]
        )
    
    def _build_dependency_graph(self, atomic_needs: List[AtomicNeed]) -> Dict[str, List[str]]:
        """
        构建依赖图
        
        Args:
            atomic_needs: 原子需求列表
            
        Returns:
            依赖图 {need_id: [dependent_need_ids]}
        """
        graph = {need.need_id: [] for need in atomic_needs}
        
        for need in atomic_needs:
            for dep in need.dependencies:
                if dep in graph:
                    graph[dep].append(need.need_id)
        
        return graph
    
    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        拓扑排序（Kahn算法）
        
        Args:
            graph: 依赖图
            
        Returns:
            执行顺序
        """
        # 计算入度
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1
        
        # 找到所有入度为0的节点
        queue = [node for node in graph if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否存在环
        if len(result) != len(graph):
            print("警告: 依赖图中存在环！")
            # 返回所有节点（忽略依赖关系）
            return list(graph.keys())
        
        return result
