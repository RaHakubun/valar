"""
端到端工作流生成器
整合所有模块，实现完整的生成流程
"""

from typing import Dict, Any, Optional, List
from core.data_structures import *
from core.llm_client import LLMClient
from core.need_decomposer import NeedDecomposer
from core.workflow_library import WorkflowLibrary
from core.vector_search import WorkflowRetriever, VectorIndex, Reranker
from core.code_splitter import CodeSplitter
from core.fragment_matcher import FragmentMatcher
from core.workflow_assembler import WorkflowAssembler, CodeToJsonConverter
from core.validator import WorkflowValidator, WorkflowJsonValidator
from core.parameter_completer import ParameterCompleter
from core.utils import load_config, load_node_definitions
import os


class ComfyUIWorkflowGenerator:
    """ComfyUI工作流生成器（主类）"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化生成器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = load_config(config_path)
        
        if not self.config:
            raise ValueError("配置文件加载失败，请检查config.yaml")
        
        # 加载节点定义
        node_defs_path = self.config.get('node_definitions', {}).get(
            'yaml_path',
            './previouswork/nodes.yaml'
        )
        self.node_defs = load_node_definitions(node_defs_path)
        
        # 初始化LLM客户端
        self.llm_client = LLMClient(self.config)
        
        # 初始化向量索引
        self.vector_index = VectorIndex()
        
        # 初始化Reranker
        reranker_config = self.config.get('reranker', {})
        reranker_model = reranker_config.get('model_name', 'cross-encoder/mmarco-mMiniLMv2-L12-H384-V1')
        self.reranker = Reranker(reranker_model)
        
        # 初始化工作流库
        library_path = self.config.get('workflow_library', {}).get('data_path', './data/workflow_library')
        self.workflow_library = WorkflowLibrary(
            data_path=library_path,
            llm_client=self.llm_client,
            vector_index=self.vector_index
        )
        
        # 初始化检索器
        self.retriever = WorkflowRetriever(
            llm_client=self.llm_client,
            vector_index=self.vector_index,
            reranker=self.reranker,
            workflow_library=self.workflow_library.workflows
        )
        
        # 初始化各个组件
        self.need_decomposer = NeedDecomposer(self.llm_client)
        
        code_split_strategy = self.config.get('code_splitting', {}).get('strategy', 'hybrid')
        self.code_splitter = CodeSplitter(
            llm_client=self.llm_client,
            node_defs=self.node_defs,
            strategy=code_split_strategy
        )
        
        matching_threshold = self.config.get('fragment_matching', {}).get('matching_threshold', 0.65)
        self.fragment_matcher = FragmentMatcher(
            llm_client=self.llm_client,
            matching_threshold=matching_threshold
        )
        
        self.workflow_assembler = WorkflowAssembler(self.node_defs)
        self.code_to_json_converter = CodeToJsonConverter(self.node_defs)
        
        self.validator = WorkflowValidator(self.node_defs, self.llm_client)
        self.json_validator = WorkflowJsonValidator(self.node_defs)
        
        self.parameter_completer = ParameterCompleter(self.llm_client)
    
    def generate(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        save_intermediate: bool = False
    ) -> Dict[str, Any]:
        """
        完整生成流程
        
        Args:
            user_request: 用户需求
            context: 上下文信息（如输入文件路径）
            save_intermediate: 是否保存中间结果
            
        Returns:
            可执行的工作流JSON
        """
        context = context or {}
        intermediate_results = {}
        
        print(f"[阶段0] 用户需求: {user_request}")
        
        # ===== 阶段1: 需求匹配 =====
        print("\n[阶段1] 需求匹配")
        
        # 1.1 需求分解
        print("  1.1 需求分解...")
        decomposed = self.need_decomposer.decompose(user_request)
        print(f"  → 分解为 {len(decomposed.atomic_needs)} 个原子需求:")
        for need in decomposed.atomic_needs:
            print(f"    - {need.description} ({need.category})")
        
        intermediate_results['decomposed_needs'] = decomposed
        
        # 1.2 向量检索
        print("  1.2 向量检索...")
        retrieval_config = self.config.get('workflow_library', {}).get('retrieval', {})
        top_k_rerank = retrieval_config.get('top_k_rerank', 10)
        
        retrieved_workflows = self.retriever.retrieve_for_all_needs(
            decomposed.atomic_needs,
            top_k_per_need=top_k_rerank
        )
        
        total_retrieved = sum(len(wfs) for wfs in retrieved_workflows.values())
        print(f"  → 检索到 {total_retrieved} 个候选工作流")
        
        intermediate_results['retrieved_workflows'] = retrieved_workflows
        
        # ===== 阶段2: 工作流框架适配 =====
        print("\n[阶段2] 工作流框架适配")
        
        # 2.1 代码拆分
        print("  2.1 代码拆分...")
        all_fragments = []
        for need_id, workflows in retrieved_workflows.items():
            for workflow in workflows:
                fragments = self.code_splitter.split(workflow)
                all_fragments.extend(fragments)
        
        print(f"  → 拆分为 {len(all_fragments)} 个代码片段")
        
        intermediate_results['fragments'] = all_fragments
        
        # 2.2 片段-需求匹配
        print("  2.2 片段-需求匹配...")
        fragment_need_mapping = self.fragment_matcher.match_fragments_to_needs(
            all_fragments,
            decomposed.atomic_needs
        )
        
        matched_count = sum(len(frags) for frags in fragment_need_mapping.values())
        print(f"  → 匹配成功 {matched_count} 个片段")
        
        for need_id, fragments in fragment_need_mapping.items():
            need = next(n for n in decomposed.atomic_needs if n.need_id == need_id)
            if fragments:
                print(f"    - {need.description}: {len(fragments)} 个候选片段")
            else:
                print(f"    - {need.description}: ⚠️ 未找到匹配")
        
        intermediate_results['fragment_matching'] = fragment_need_mapping
        
        # 2.3 拼接
        print("  2.3 工作流拼接...")
        # 为每个需求选择最佳片段
        selected_fragments = []
        for need_id in decomposed.execution_order:
            fragments = fragment_need_mapping.get(need_id, [])
            if fragments:
                # 选择置信度最高的
                best_fragment = max(fragments, key=lambda f: f.match_confidence)
                selected_fragments.append(best_fragment)
            else:
                print(f"    ⚠️ 需求 {need_id} 无匹配片段，跳过")
        
        if not selected_fragments:
            raise ValueError("没有可用的片段来构建工作流")
        
        framework = self.workflow_assembler.assemble(
            selected_fragments,
            decomposed.atomic_needs,
            decomposed.execution_order
        )
        
        print(f"  → 拼接完成，包含 {len(framework.fragments)} 个片段")
        
        intermediate_results['framework'] = framework
        
        # 2.4 验证
        print("  2.4 框架验证...")
        is_valid, errors = self.validator.validate(framework)
        
        if errors:
            print(f"  ⚠️ 发现 {len(errors)} 个问题:")
            for error in errors[:5]:  # 只显示前5个
                print(f"    - {error}")
        else:
            print("  ✓ 验证通过")
        
        # ===== 阶段3: 可执行工作流合成 =====
        print("\n[阶段3] 可执行工作流合成")
        
        # 3.1 代码转JSON
        print("  3.1 代码→JSON转换...")
        workflow_json = self.code_to_json_converter.convert(framework.framework_code)
        print(f"  → 生成 {len(workflow_json)} 个节点")
        
        intermediate_results['workflow_json_before_completion'] = workflow_json
        
        # 3.2 参数补全
        print("  3.2 参数补全...")
        workflow_json = self.parameter_completer.complete(
            workflow_json,
            user_request,
            context
        )
        print("  ✓ 参数补全完成")
        
        # 3.3 最终验证
        print("  3.3 最终验证...")
        is_valid, errors = self.json_validator.validate_json(workflow_json)
        
        if errors:
            print(f"  ⚠️ 发现 {len(errors)} 个问题:")
            for error in errors[:5]:
                print(f"    - {error}")
        else:
            print("  ✓ JSON验证通过")
        
        # 保存中间结果
        if save_intermediate:
            self._save_intermediate_results(intermediate_results, context)
        
        print("\n[完成] 工作流生成完毕")
        
        return workflow_json
    
    def _save_intermediate_results(
        self,
        intermediate_results: Dict[str, Any],
        context: Dict[str, Any]
    ):
        """保存中间结果"""
        log_dir = self.config.get('logging', {}).get('log_dir', './logs')
        os.makedirs(log_dir, exist_ok=True)
        
        import json
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(log_dir, f'generation_{timestamp}.json')
        
        # 转换为可序列化的格式
        serializable = {
            'decomposed_needs': [
                {
                    'need_id': n.need_id,
                    'description': n.description,
                    'category': n.category
                }
                for n in intermediate_results.get('decomposed_needs', DecomposedNeeds([], {}, [])).atomic_needs
            ],
            'fragment_count': len(intermediate_results.get('fragments', [])),
            'framework_code': intermediate_results.get('framework', WorkflowFramework('', [], [], '')).framework_code,
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        
        print(f"\n中间结果已保存到: {output_file}")


# 便捷函数
def generate_workflow(
    user_request: str,
    config_path: str = "config.yaml",
    context: Optional[Dict[str, Any]] = None,
    save_intermediate: bool = True
) -> Dict[str, Any]:
    """
    便捷函数：生成工作流
    
    Args:
        user_request: 用户需求
        config_path: 配置文件路径
        context: 上下文信息
        save_intermediate: 是否保存中间结果
        
    Returns:
        可执行的工作流JSON
    """
    generator = ComfyUIWorkflowGenerator(config_path)
    return generator.generate(user_request, context, save_intermediate)
