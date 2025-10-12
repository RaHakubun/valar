#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键清空workflow_library的所有数据
包括：workflows、metadata、向量索引、节点元数据等
"""

import os
import shutil


def clean_workflow_library(library_path='./data/workflow_library', confirm=True):
    """
    清空workflow_library的所有数据
    
    Args:
        library_path: workflow_library路径
        confirm: 是否需要确认
    """
    
    print("=" * 80)
    print("清空Workflow Library")
    print("=" * 80)
    
    if not os.path.exists(library_path):
        print(f"❌ 路径不存在: {library_path}")
        return
    
    # 列出将要删除的内容
    items_to_delete = []
    
    # 1. workflows目录
    workflows_dir = os.path.join(library_path, 'workflows')
    if os.path.exists(workflows_dir):
        workflow_count = len([f for f in os.listdir(workflows_dir) if f.endswith('.json')])
        items_to_delete.append(f"  - workflows/ ({workflow_count} 个workflow)")
    
    # 2. metadata目录
    metadata_dir = os.path.join(library_path, 'metadata')
    if os.path.exists(metadata_dir):
        metadata_count = len([f for f in os.listdir(metadata_dir) if f.endswith('.meta.json')])
        items_to_delete.append(f"  - metadata/ ({metadata_count} 个metadata文件)")
    
    # 3. 向量索引文件
    vector_index_file = os.path.join(library_path, 'embeddings.faiss')
    if os.path.exists(vector_index_file):
        size_mb = os.path.getsize(vector_index_file) / 1024 / 1024
        items_to_delete.append(f"  - embeddings.faiss ({size_mb:.2f} MB)")
    
    # 4. 向量索引映射文件
    mapping_file = os.path.join(library_path, 'embeddings.faiss.mapping.json')
    if os.path.exists(mapping_file):
        items_to_delete.append(f"  - embeddings.faiss.mapping.json")
    
    # 5. 节点元数据
    node_meta_file = os.path.join(library_path, 'node_meta.json')
    if os.path.exists(node_meta_file):
        items_to_delete.append(f"  - node_meta.json")
    
    # 6. 节点统计
    node_stats_file = os.path.join(library_path, 'node_statistics.json')
    if os.path.exists(node_stats_file):
        items_to_delete.append(f"  - node_statistics.json")
    
    # 7. code目录（如果存在）
    code_dir = os.path.join(library_path, 'code')
    if os.path.exists(code_dir):
        code_count = len([f for f in os.listdir(code_dir) if f.endswith('.py')])
        items_to_delete.append(f"  - code/ ({code_count} 个代码文件)")
    
    if not items_to_delete:
        print("\n✅ Workflow library已经是空的")
        return
    
    # 显示将要删除的内容
    print("\n将要删除以下内容:")
    for item in items_to_delete:
        print(item)
    
    # 确认
    if confirm:
        print("\n" + "⚠️  " * 20)
        print("警告: 此操作不可逆！所有workflow数据将被永久删除！")
        print("⚠️  " * 20)
        response = input("\n确认删除? (输入 'YES' 继续): ")
        if response != 'YES':
            print("\n❌ 已取消")
            return
    
    # 开始删除
    print("\n开始清理...")
    deleted_count = 0
    
    # 删除workflows目录
    if os.path.exists(workflows_dir):
        shutil.rmtree(workflows_dir)
        os.makedirs(workflows_dir)
        print("  ✓ 清空 workflows/")
        deleted_count += 1
    
    # 删除metadata目录
    if os.path.exists(metadata_dir):
        shutil.rmtree(metadata_dir)
        os.makedirs(metadata_dir)
        print("  ✓ 清空 metadata/")
        deleted_count += 1
    
    # 删除code目录
    if os.path.exists(code_dir):
        shutil.rmtree(code_dir)
        os.makedirs(code_dir)
        print("  ✓ 清空 code/")
        deleted_count += 1
    
    # 删除向量索引文件
    if os.path.exists(vector_index_file):
        os.remove(vector_index_file)
        print("  ✓ 删除 embeddings.faiss")
        deleted_count += 1
    
    # 删除映射文件
    if os.path.exists(mapping_file):
        os.remove(mapping_file)
        print("  ✓ 删除 embeddings.faiss.mapping.json")
        deleted_count += 1
    
    # 删除节点元数据
    if os.path.exists(node_meta_file):
        os.remove(node_meta_file)
        print("  ✓ 删除 node_meta.json")
        deleted_count += 1
    
    # 删除节点统计
    if os.path.exists(node_stats_file):
        os.remove(node_stats_file)
        print("  ✓ 删除 node_statistics.json")
        deleted_count += 1
    
    print("\n" + "=" * 80)
    print(f"✅ 清理完成！共删除 {deleted_count} 项")
    print("=" * 80)
    print("\n现在可以重新导入workflow:")
    print("  python recorder.py --add <workflow.json>")
    print("  python recorder.py --batch workflowbench/")
    print()


def show_library_stats(library_path='./data/workflow_library'):
    """显示当前library的统计信息"""
    
    print("=" * 80)
    print("Workflow Library 统计")
    print("=" * 80)
    
    if not os.path.exists(library_path):
        print(f"❌ 路径不存在: {library_path}")
        return
    
    # workflows
    workflows_dir = os.path.join(library_path, 'workflows')
    workflow_count = 0
    if os.path.exists(workflows_dir):
        workflow_count = len([f for f in os.listdir(workflows_dir) if f.endswith('.json')])
    
    # metadata
    metadata_dir = os.path.join(library_path, 'metadata')
    metadata_count = 0
    if os.path.exists(metadata_dir):
        metadata_count = len([f for f in os.listdir(metadata_dir) if f.endswith('.meta.json')])
    
    # 向量索引
    vector_index_file = os.path.join(library_path, 'embeddings.faiss')
    vector_index_size = 0
    vector_index_exists = False
    if os.path.exists(vector_index_file):
        vector_index_exists = True
        vector_index_size = os.path.getsize(vector_index_file) / 1024 / 1024
    
    # 节点元数据
    node_meta_file = os.path.join(library_path, 'node_meta.json')
    node_meta_exists = os.path.exists(node_meta_file)
    
    print(f"\n📊 统计信息:")
    print(f"  - Workflows: {workflow_count} 个")
    print(f"  - Metadata: {metadata_count} 个")
    print(f"  - 向量索引: {'存在' if vector_index_exists else '不存在'} ({vector_index_size:.2f} MB)" if vector_index_exists else "  - 向量索引: 不存在")
    print(f"  - 节点元数据: {'存在' if node_meta_exists else '不存在'}")
    
    if workflow_count == 0:
        print("\n💡 Library为空，可以开始导入workflow")
    else:
        print(f"\n✅ Library包含 {workflow_count} 个workflow")
    
    print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--stats':
            # 显示统计信息
            show_library_stats()
        elif sys.argv[1] == '--clean':
            # 清空（需要确认）
            clean_workflow_library(confirm=True)
        elif sys.argv[1] == '--force':
            # 强制清空（无需确认）
            print("⚠️  强制清空模式（无需确认）")
            clean_workflow_library(confirm=False)
        else:
            print("使用方法:")
            print("  python clean_workflow_library.py --stats   # 显示统计")
            print("  python clean_workflow_library.py --clean   # 清空（需确认）")
            print("  python clean_workflow_library.py --force   # 强制清空（无需确认）")
    else:
        # 默认显示统计并询问是否清空
        show_library_stats()
        print("\n" + "-" * 80)
        response = input("是否要清空library? (输入 'yes' 继续): ")
        if response.lower() == 'yes':
            clean_workflow_library(confirm=True)
        else:
            print("已取消")
