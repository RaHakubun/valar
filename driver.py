#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ComfyUI工作流检索-适配-合成系统驱动器
完整实现从需求分解到工作流生成的端到端流程
"""

import json
import os
import sys
import logging
from typing import Dict, List, Optional, Any, Tuple
from core.data_structures import (
    AtomicNeed, DecomposedNeeds, WorkflowFragment, WorkflowFramework
)
from core.need_decomposer import NeedDecomposer
from core.code_splitter import CodeSplitter
from core.fragment_matcher import FragmentMatcher
from core.workflow_assembler import WorkflowAssembler, CodeToJsonConverter
from core.workflow_library import WorkflowLibrary
from core.vector_search import VectorIndex, Reranker, WorkflowRetriever
from core.llm_client import LLMClient
from core.utils import load_config, load_node_definitions
from main import parse_code_to_prompt  # 从已有的双向解析器导入


class ComfyUIWorkflowGenerator:
    """
    ComfyUI工作流生成系统主类
    实现完整的检索-适配-合成流程
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化工作流生成器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = load_config(config_path)
        if not self.config:
            raise ValueError(f"无法加载配置文件: {config_path}")
        
        # 设置日志
        self._setup_logging()
        
        # 初始化LLM客户端
        self.llm_client = LLMClient(self.config)
        
        # 加载节点定义
        node_defs_path = self.config.get('node_definitions', {}).get('yaml_path', './previouswork/nodes.yaml')
        self.node_defs = load_node_definitions(node_defs_path)
        
        # 初始化各组件
        self._initialize_components()
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get('logging', {})
        level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_dir = log_config.get('log_dir', './logs')
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 配置日志
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'workflow_generator.log'), encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def _initialize_components(self):
        """初始化所有组件"""
        try:
            # 1. 需求分解器
            self.need_decomposer = NeedDecomposer(self.llm_client)
            self.logger.info("需求分解器初始化完成")
            
            # 2. 工作流库（包含vector_index）
            library_config = self.config.get('workflow_library', {})
            library_path = library_config.get('data_path', './data/workflow_library')
            vector_index_path = library_config.get('vector_index_path', './data/workflow_library/embeddings.faiss')
            
            # 初始化向量索引（根据embedding模型决定维度）
            embedding_model = self.config.get('openai', {}).get('embedding_model', 'text-embedding-3-large')
            if 'ada-002' in embedding_model:
                dimension = 1536
            elif '3-small' in embedding_model:
                dimension = 1536
            else:
                dimension = 3072
            
            vector_index = VectorIndex(dimension=dimension)
            
            # 初始化工作流库
            self.workflow_library = WorkflowLibrary(
                data_path=library_path,
                llm_client=self.llm_client,
                vector_index=vector_index,
                vector_index_path=vector_index_path
            )
            self.logger.info(f"工作流库初始化完成，包含 {len(self.workflow_library.workflows)} 个工作流")
            self.logger.info(f"向量索引包含 {vector_index.index.ntotal} 个向量")
            
            # 3. 检索器（使用workflow_library中的vector_index）
            reranker_config = self.config.get('reranker', {})
            reranker = Reranker(config=reranker_config)
            self.workflow_retriever = WorkflowRetriever(
                llm_client=self.llm_client,
                vector_index=self.workflow_library.vector_index,  # 使用已加载的索引
                reranker=reranker,
                workflow_library=self.workflow_library.workflows
            )
            self.logger.info("检索器初始化完成")
            
            # 4. 代码拆分器
            split_config = self.config.get('code_splitting', {})
            self.code_splitter = CodeSplitter(
                llm_client=self.llm_client,
                node_defs=self.node_defs,
                strategy=split_config.get('strategy', 'hybrid')
            )
            self.logger.info("代码拆分器初始化完成")
            
            # 5. 片段匹配器
            match_config = self.config.get('fragment_matching', {})
            self.fragment_matcher = FragmentMatcher(
                llm_client=self.llm_client,
                matching_threshold=match_config.get('matching_threshold', 0.65),
                use_llm=match_config.get('use_llm', True)
            )
            self.logger.info("片段匹配器初始化完成")
            
            # 6. 工作流拼接器
            self.workflow_assembler = WorkflowAssembler(self.node_defs)
            self.logger.info("工作流拼接器初始化完成")
            
            # 7. 代码到JSON转换器
            self.code_to_json_converter = CodeToJsonConverter(self.node_defs)
            self.logger.info("代码到JSON转换器初始化完成")
            
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            raise
    
    def generate_workflow(self, user_request: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        生成工作流的主流程
        
        Args:
            user_request: 用户需求
            context: 上下文信息（可选）
            
        Returns:
            生成的工作流JSON
        """
        self.logger.info(f"开始处理用户需求: {user_request}")
        
        try:
            # 阶段1: 需求匹配
            print("\n" + "="*80)
            print("阶段1: 需求分解")
            print("="*80)
            self.logger.info("阶段1: 需求分解...")
            decomposed_needs = self.need_decomposer.decompose(user_request)
            self.logger.info(f"分解结果: {len(decomposed_needs.atomic_needs)}个原子需求")
            
            print(f"\n分解为 {len(decomposed_needs.atomic_needs)} 个原子需求:")
            for i, need in enumerate(decomposed_needs.atomic_needs, 1):
                print(f"{i}. {need}")
                # print(f"   - 类别: {need.category}")
                # print(f"   - 优先级: {need.priority}")
                # print(f"   - 依赖: {need.dependencies}")
            #思考过程没有放入AtomicNeeds里面
            # 为每个原子需求检索候选工作流
            print("\n" + "="*80)
            print("阶段1: 检索候选工作流")
            print("="*80)
            self.logger.info("阶段1: 检索候选工作流...")
            candidate_workflows = self.workflow_retriever.retrieve_for_all_needs(
                decomposed_needs.atomic_needs,
                top_k_per_need=5
            )
            
            print(f"\n检索结果:")
            for need in decomposed_needs.atomic_needs:
                candidates = candidate_workflows.get(need.need_id, [])
                print(f"\n需求: {need.description}")
                print(f"找到 {len(candidates)} 个候选工作流:")
                for i, wf in enumerate(candidates[:3], 1):  # 只显示前3个
                    print(f"  {i}. {wf.workflow_id}: {wf.intent.description}")
                    print(wf)
            
            # 阶段2: 工作流框架级别智能适配
            print("\n" + "="*80)
            print("阶段2: 工作流拆分和匹配")
            print("="*80)
            all_fragments = []
            
            self.logger.info("阶段2: 工作流拆分和匹配...")
            for need in decomposed_needs.atomic_needs:
                need_candidates = candidate_workflows.get(need.need_id, [])
                
                if not need_candidates:
                    self.logger.warning(f"需求 '{need.description}' 未找到匹配的工作流")
                    continue
                
                self.logger.info(f"需求 '{need.description}' 找到 {len(need_candidates)} 个候选工作流")
                
                # 拆分最优候选工作流为片段
                best_candidate = need_candidates[0]  # 最优工作流
                fragments = self.code_splitter.split(best_candidate)
                self.logger.info(f"拆分为 {len(fragments)} 个片段")
                
                all_fragments.extend(fragments)
            
            # 将片段匹配到原子需求
            self.logger.info("阶段2: 片段-需求匹配...")
            fragment_need_mapping = self.fragment_matcher.match_fragments_to_needs(
                all_fragments,
                decomposed_needs.atomic_needs
            )
            
            # 收集所有匹配的片段
            matched_fragments = []
            for need_id, fragments in fragment_need_mapping.items():
                if fragments:
                    self.logger.info(f"需求 {need_id} 匹配到 {len(fragments)} 个片段")
                    matched_fragments.extend(fragments[:1])  # 取置信度最高的一个
                else:
                    self.logger.warning(f"需求 {need_id} 未匹配到片段")
            
            # 阶段2.2: 拼接工作流框架
            print("\n" + "="*80)
            print("阶段2: 拼接工作流框架")
            print("="*80)
            self.logger.info("阶段2: 拼接工作流框架...")
            if matched_fragments:
                framework = self.workflow_assembler.assemble(
                    matched_fragments,
                    decomposed_needs.atomic_needs,
                    decomposed_needs.execution_order
                )
                
                print(f"\n生成的工作流框架 ({len(matched_fragments)} 个片段):")
                print("```python")
                print(framework.framework_code)
                print("```")
                self.logger.info(f"生成的工作流框架:\n{framework.framework_code}")
            else:
                # 如果没有匹配片段，生成一个简单的响应
                self.logger.warning("未找到匹配的片段，生成默认框架")
                framework = WorkflowFramework(
                    framework_id="default_framework",
                    fragments=[],
                    execution_order=[],
                    framework_code="# 未找到匹配的工作流片段"
                )
            
            # 阶段3: 可执行工作流合成（代码转JSON）
            print("\n" + "="*80)
            print("阶段3: 合成可执行工作流")
            print("="*80)
            self.logger.info("阶段3: 合成可执行工作流...")
            if framework.framework_code and framework.framework_code.strip():
                try:
                    workflow_json = self.code_to_json_converter.convert(framework.framework_code)
                    print(f"\n✅ 成功转换为JSON格式")
                    print(f"   - 节点数: {len(workflow_json)}")
                    print(f"   - 节点类型: {', '.join(set(n.get('class_type', '?') for n in workflow_json.values() if isinstance(n, dict)))}")
                    self.logger.info(f"成功转换为JSON格式，包含 {len(workflow_json)} 个节点")
                except Exception as e:
                    print(f"\n❌ 代码转JSON失败: {e}")
                    self.logger.error(f"代码转JSON失败: {e}")
                    import traceback
                    traceback.print_exc()
                    workflow_json = {}
            else:
                workflow_json = {}
            
            # 最终输出
            result = {
                "user_request": user_request,
                "decomposed_needs": [
                    {
                        "need_id": need.need_id,
                        "description": need.description,
                        "category": need.category,
                        "constraints": need.constraints
                    } for need in decomposed_needs.atomic_needs
                ],
                "workflow_json": workflow_json,
                "framework_code": framework.framework_code,
                "success": len(workflow_json) > 0
            }
            
            self.logger.info(f"工作流生成完成，成功状态: {result['success']}")
            return result
            
        except Exception as e:
            self.logger.error(f"生成工作流时发生错误: {e}", exc_info=True)
            # 返回错误结果
            return {
                "user_request": user_request,
                "decomposed_needs": [],
                "workflow_json": {},
                "framework_code": "",
                "success": False,
                "error": str(e)
            }
    
    def generate_from_json(self, user_request: str, context: Optional[Dict] = None) -> str:
        """
        生成工作流并返回JSON字符串
        
        Args:
            user_request: 用户需求
            context: 上下文信息（可选）
            
        Returns:
            JSON格式的工作流
        """
        result = self.generate_workflow(user_request, context)
        return json.dumps(result, ensure_ascii=False, indent=2)


def main():
    """主函数 - 命令行使用"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ComfyUI工作流生成器')
    parser.add_argument('--request', '-r', type=str, required=True,
                        help='用户需求描述')
    parser.add_argument('--config', '-c', type=str, default='config.yaml',
                        help='配置文件路径')
    parser.add_argument('--output', '-o', type=str, default='generated_workflow.json',
                        help='输出文件路径')
    
    args = parser.parse_args()
    
    try:
        # 创建生成器
        generator = ComfyUIWorkflowGenerator(args.config)
        
        # 生成工作流
        result = generator.generate_workflow(args.request)
        
        # 保存结果
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result["workflow_json"], f, ensure_ascii=False, indent=2)
        
        print(f"\n工作流已生成并保存到: {args.output}")
        print(f"节点数量: {len(result['workflow_json'])}")
        print(f"成功状态: {'成功' if result['success'] else '失败'}")
        
        if 'error' in result:
            print(f"错误信息: {result['error']}")
            
    except Exception as e:
        logging.error(f"命令行运行错误: {e}", exc_info=True)
        sys.exit(1)


def demo():
    """演示函数"""
    print("=== ComfyUI工作流生成系统演示 ===\n")
    
    # 示例需求
    demo_requests = [
        "生成一个粘土风格的人物肖像，并进行4倍超分",
        "生成一只猫咪的图像，使用Flux模型",
        "将图片进行超分辨率处理，放大4倍",
    ]
    
    # 创建生成器
    try:
        generator = ComfyUIWorkflowGenerator()
        print("系统初始化完成\n")
        
        for i, request in enumerate(demo_requests, 1):
            print(f"--- 演示 {i} ---")
            print(f"需求: {request}")
            
            result = generator.generate_workflow(request)
            print(f"工作流节点数: {len(result['workflow_json'])}")
            print(f"框架代码行数: {len(result['framework_code'].split()) if result['framework_code'] else 0}")
            print(f"成功: {result['success']}")
            print()
            
    except Exception as e:
        print(f"演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 命令行模式
        main()
    else:
        # 演示模式
        demo()