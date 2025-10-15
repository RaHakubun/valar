#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试driver.py的完整生成流程（带详细中间输出）
"""

from driver import ComfyUIWorkflowGenerator
import json

print("=" * 80)
print("ComfyUI工作流生成系统演示")
print("=" * 80)

# 初始化
generator = ComfyUIWorkflowGenerator('config.yaml')
print("系统初始化完成\n")

# 测试需求
test_request = "生成一个粘土风格的人物肖像"

print("--- 演示 ---")
print(f"需求: {test_request}")

# 生成工作流
result = generator.generate_workflow(test_request)

# 保存结果
if result.get('workflow_json'):
    output_file = 'generated_workflow.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result['workflow_json'], f, indent=2, ensure_ascii=False)
    
    print(f"\n" + "=" * 80)
    print(f"✅ 工作流已生成并保存到: {output_file}")
    print(f"   节点数: {len(result['workflow_json'])}")
    print("=" * 80)
else:
    print(f"\n" + "=" * 80)
    print("❌ 工作流生成失败")
    print("=" * 80)
