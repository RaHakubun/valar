#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键重建workflow_library
自动清空 → 重新导入 → 验证
"""

import os
import sys
import subprocess
from clean_workflow_library import clean_workflow_library, show_library_stats


def rebuild_library(source_dir='workflowbench/', confirm=True):
    """
    重建workflow_library
    
    Args:
        source_dir: workflow源目录
        confirm: 是否需要确认
    """
    
    print("=" * 80)
    print("Workflow Library 重建工具")
    print("=" * 80)
    
    # 检查源目录
    if not os.path.exists(source_dir):
        print(f"\n❌ 错误: 源目录不存在: {source_dir}")
        print("请指定一个包含workflow JSON文件的目录")
        return False
    
    # 统计源文件
    json_files = [f for f in os.listdir(source_dir) if f.endswith('.json')]
    if not json_files:
        print(f"\n❌ 错误: {source_dir} 中没有找到JSON文件")
        return False
    
    print(f"\n📁 源目录: {source_dir}")
    print(f"📊 发现 {len(json_files)} 个workflow JSON文件")
    
    # 显示当前状态
    print("\n" + "-" * 80)
    print("当前Library状态:")
    print("-" * 80)
    show_library_stats()
    
    # 确认
    if confirm:
        print("\n" + "⚠️  " * 20)
        print("即将执行以下操作:")
        print("  1. 清空现有workflow_library")
        print("  2. 从 workflowbench/ 重新导入所有workflow")
        print("  3. 生成向量索引和metadata")
        print("⚠️  " * 20)
        response = input("\n确认继续? (输入 'YES' 继续): ")
        if response != 'YES':
            print("\n❌ 已取消")
            return False
    
    print("\n" + "=" * 80)
    print("开始重建...")
    print("=" * 80)
    
    # 步骤1: 清空
    print("\n[1/3] 清空现有数据...")
    clean_workflow_library(confirm=False)
    
    # 步骤2: 重新导入
    print("\n[2/3] 导入workflow...")
    try:
        result = subprocess.run(
            ['python', 'recorder.py', '--batch', source_dir],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0:
            print(f"❌ 导入失败:")
            print(result.stderr)
            return False
        
        print(result.stdout)
        
    except subprocess.TimeoutExpired:
        print("❌ 导入超时（超过5分钟）")
        return False
    except Exception as e:
        print(f"❌ 导入出错: {e}")
        return False
    
    # 步骤3: 验证
    print("\n[3/3] 验证结果...")
    show_library_stats()
    
    print("\n" + "=" * 80)
    print("✅ 重建完成!")
    print("=" * 80)
    print("\n可以开始使用了:")
    print("  python test_driver_generate.py")
    print()
    
    return True


def quick_rebuild():
    """快速重建（无需确认）"""
    print("⚠️  快速重建模式（无需确认）\n")
    return rebuild_library(confirm=False)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Workflow Library 重建工具')
    parser.add_argument(
        '--source',
        default='workflowbench/',
        help='workflow源目录 (默认: workflowbench/)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重建，无需确认'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='快速重建（同--force）'
    )
    
    args = parser.parse_args()
    
    confirm = not (args.force or args.quick)
    success = rebuild_library(source_dir=args.source, confirm=confirm)
    
    sys.exit(0 if success else 1)
