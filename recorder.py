#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ComfyUI工作流记录器
用于向工作流库添加新的工作流JSON文件
"""

import json
import os
import sys
import argparse
from typing import Dict, Any, Optional, List
from core.workflow_library import WorkflowLibrary
from core.llm_client import LLMClient
from core.vector_search import VectorIndex
from core.utils import load_config, load_json, save_json
from main import parse_prompt_to_code  # 从已有的双向解析器导入


class WorkflowRecorder:
    """
    工作流记录器
    用于管理向工作流库添加新的工作流
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化工作流记录器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(config_path)
        if not self.config:
            raise ValueError(f"无法加载配置文件: {config_path}")
        
        # 初始化LLM客户端（用于意图提取和embedding）
        self.llm_client = LLMClient(self.config)
        
        # 初始化向量索引
        # 根据embedding模型决定维度
        embedding_model = self.config.get('openai', {}).get('embedding_model', 'text-embedding-3-large')
        if 'ada-002' in embedding_model:
            dimension = 1536  # text-embedding-ada-002的维度
        elif '3-small' in embedding_model:
            dimension = 1536  # text-embedding-3-small
        else:
            dimension = 3072  # text-embedding-3-large的维度
        
        self.vector_index = VectorIndex(dimension=dimension)
        
        # 初始化工作流库
        library_config = self.config.get('workflow_library', {})
        library_path = library_config.get('data_path', './data/workflow_library')
        vector_index_path = library_config.get('vector_index_path', './data/workflow_library/embeddings.faiss')
        
        self.workflow_library = WorkflowLibrary(
            data_path=library_path,
            llm_client=self.llm_client,
            vector_index=self.vector_index,
            vector_index_path=vector_index_path
        )
        
        print(f"工作流库初始化完成，当前包含 {len(self.workflow_library.workflows)} 个工作流")
    
    def add_workflow_from_json(self, workflow_path: str, description: Optional[str] = None,tags: Optional[List[str]] = None,source: str = "manual") -> bool:
        """
        从JSON文件添加工作流到库
        
        Args:
            workflow_path: 工作流JSON文件路径
            description: 工作流描述（如果None则自动生成）
            tags: 标签列表
            source: 来源标识
            
        Returns:
            添加是否成功
        """
        try:
            # 加载工作流JSON
            print(f"加载工作流文件: {workflow_path}")
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_json = json.load(f)
            
            # 转换为代码表示
            print("转换为代码表示...")
            try:
                workflow_code = parse_prompt_to_code(workflow_json)
            except Exception as e:
                print(f"代码转换失败，使用JSON字符串作为代码表示: {e}")
                workflow_code = f"# 从JSON转换失败\n# 原始JSON: {json.dumps(workflow_json, ensure_ascii=False)[:200]}..."
            
            # 准备元数据
            metadata = {
                'source': source,
                'tags': tags or []
            }
            
            if description:
                metadata['description'] = description
            
            # 添加到工作流库
            workflow_entry = self.workflow_library.add_workflow(
                workflow_json=workflow_json,
                workflow_code=workflow_code,
                metadata=metadata,
                auto_annotate=description is None  # 如果没有提供描述，则自动标注
            )
            
            print(f"成功添加工作流到库: {workflow_entry.workflow_id}")
            print(f"工作流描述: {workflow_entry.intent.description}")
            print(f"节点数量: {workflow_entry.node_count}")
            
            return True
            
        except Exception as e:
            print(f"添加工作流失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def add_workflow_from_dict(
        self, 
        workflow_json: Dict[str, Any],
        workflow_code: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "manual"
    ) -> bool:
        """
        从字典添加工作流到库
        
        Args:
            workflow_json: 工作流JSON
            workflow_code: 工作流代码表示
            description: 工作流描述
            tags: 标签列表
            source: 来源标识
            
        Returns:
            添加是否成功
        """
        try:
            # 如果没有提供代码表示，则从JSON转换
            if not workflow_code:
                print("转换为代码表示...")
                try:
                    workflow_code = parse_prompt_to_code(workflow_json)
                except Exception as e:
                    print(f"代码转换失败，使用JSON字符串作为代码表示: {e}")
                    workflow_code = f"# 从JSON转换失败\n# 原始JSON: {json.dumps(workflow_json, ensure_ascii=False)[:200]}..."
            
            # 准备元数据
            metadata = {
                'source': source,
                'tags': tags or []
            }
            
            if description:
                metadata['description'] = description
            
            # 添加到工作流库
            workflow_entry = self.workflow_library.add_workflow(
                workflow_json=workflow_json,
                workflow_code=workflow_code,
                metadata=metadata,
                auto_annotate=description is None
            )
            
            print(f"成功添加工作流到库: {workflow_entry.workflow_id}")
            print(f"工作流描述: {workflow_entry.intent.description}")
            print(f"节点数量: {workflow_entry.node_count}")
            
            return True
            
        except Exception as e:
            print(f"添加工作流失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def batch_add_workflows(self, workflow_dir: str, file_pattern: str = "*.json") -> int:
        """
        批量添加工作流
        
        Args:
            workflow_dir: 工作流文件目录
            file_pattern: 文件匹配模式
            
        Returns:
            成功添加的工作流数量
        """
        import glob
        
        if file_pattern.endswith(".json"):
            pattern = os.path.join(workflow_dir, file_pattern)
        else:
            pattern = os.path.join(workflow_dir, "*.json")
            
        workflow_files = glob.glob(pattern)
        success_count = 0
        
        print(f"找到 {len(workflow_files)} 个工作流文件")
        
        for workflow_file in workflow_files:
            print(f"\n处理文件: {workflow_file}")
            if self.add_workflow_from_json(workflow_file, source="batch"):
                success_count += 1
        
        print(f"\n批量添加完成: {success_count}/{len(workflow_files)} 个成功")
        return success_count
    
    def get_library_stats(self):
        """获取库统计信息"""
        stats = self.workflow_library.get_statistics()
        print("\n工作流库统计信息:")
        print(f"  总数量: {stats['total_count']}")
        print(f"  平均节点数: {stats['avg_node_count']:.2f}")
        print(f"  来源分布: {stats['by_source']}")
        print(f"  复杂度分布: {stats['by_complexity']}")
        print(f"  热门标签: {stats['top_tags'][:10]}")


def main():
    """主函数 - 命令行使用"""
    parser = argparse.ArgumentParser(description='ComfyUI工作流记录器')
    parser.add_argument('--add', '-a', type=str, 
                        help='添加单个工作流JSON文件')
    parser.add_argument('--batch', '-b', type=str,
                        help='批量添加目录下的所有JSON工作流文件')
    parser.add_argument('--stats', '-s', action='store_true',
                        help='显示工作流库统计信息')
    parser.add_argument('--config', '-c', type=str, default='config.yaml',
                        help='配置文件路径')
    parser.add_argument('--description', '-d', type=str,
                        help='工作流描述（用于单个添加）')
    parser.add_argument('--tags', '-t', type=str,
                        help='标签列表，用逗号分隔（例如: tag1,tag2,tag3）')
    
    args = parser.parse_args()
    
    try:
        # 创建记录器
        recorder = WorkflowRecorder(args.config)
        
        if args.stats:
            # 显示统计信息
            recorder.get_library_stats()
        
        elif args.add:
            # 添加单个工作流
            tags = args.tags.split(',') if args.tags else None
            recorder.add_workflow_from_json(
                workflow_path=args.add,
                description=args.description,
                tags=tags,
                source="manual"
            )
        
        elif args.batch:
            # 批量添加工作流
            recorder.batch_add_workflows(args.batch)
        
        else:
            # 显示帮助
            parser.print_help()
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()