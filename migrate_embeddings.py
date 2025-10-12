#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
迁移脚本：为现有workflow添加embedding到metadata
这样下次加载时就不需要重新生成了
"""

import os
import json
from core.llm_client import LLMClient
from core.utils import load_config

print("=" * 80)
print("Embedding迁移脚本")
print("=" * 80)

# 加载配置
config = load_config('config.yaml')
llm_client = LLMClient(config)

# 工作流库路径
workflow_lib_path = './data/workflow_library'
metadata_dir = os.path.join(workflow_lib_path, 'metadata')

if not os.path.exists(metadata_dir):
    print(f"错误: 找不到metadata目录: {metadata_dir}")
    exit(1)

# 获取所有metadata文件
metadata_files = [f for f in os.listdir(metadata_dir) if f.endswith('.meta.json')]
print(f"\n找到 {len(metadata_files)} 个workflow")

# 统计
updated_count = 0
skipped_count = 0
error_count = 0

for i, filename in enumerate(metadata_files, 1):
    metadata_path = os.path.join(metadata_dir, filename)
    workflow_id = filename.replace('.meta.json', '')
    
    print(f"\n[{i}/{len(metadata_files)}] 处理: {workflow_id}")
    
    try:
        # 加载metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 检查是否已有embedding
        if 'intent_embedding' in metadata and metadata['intent_embedding'] is not None:
            print(f"  ✓ 已有embedding，跳过")
            skipped_count += 1
            continue
        
        # 生成embedding
        description = metadata['intent']['description']
        print(f"  描述: {description}")
        print(f"  生成embedding...")
        
        embedding = llm_client.embed(description)
        
        if embedding:
            # 更新metadata
            metadata['intent_embedding'] = embedding
            
            # 保存
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print(f"  ✅ 已更新 (维度: {len(embedding)})")
            updated_count += 1
        else:
            print(f"  ❌ embedding生成失败")
            error_count += 1
            
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        error_count += 1

print("\n" + "=" * 80)
print("迁移完成")
print("=" * 80)
print(f"✅ 更新: {updated_count}")
print(f"⏭  跳过: {skipped_count}")
print(f"❌ 失败: {error_count}")
print(f"📊 总计: {len(metadata_files)}")
print("\n下次启动driver时将直接从文件加载embedding，无需重新生成！")
