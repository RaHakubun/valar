"""
使用示例
展示如何使用生成器
"""

from generator import generate_workflow, ComfyUIWorkflowGenerator
import json


def example_1_simple_generation():
    """示例1：简单使用"""
    print("=" * 60)
    print("示例1：简单生成工作流")
    print("=" * 60)
    
    # 用户需求
    user_request = "生成一个粘土风格的人物肖像"
    
    # 生成工作流
    workflow_json = generate_workflow(
        user_request=user_request,
        save_intermediate=True
    )
    
    # 保存结果
    with open('output_workflow.json', 'w', encoding='utf-8') as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    
    print(f"\n生成完成！工作流已保存到 output_workflow.json")
    print(f"包含 {len(workflow_json)} 个节点")


def example_2_with_context():
    """示例2：带上下文信息"""
    print("=" * 60)
    print("示例2：带上下文信息生成")
    print("=" * 60)
    
    user_request = "将这张图片进行4倍超分辨率处理"
    
    # 上下文信息
    context = {
        'input_file': 'input_image.png',
        'output_prefix': 'upscaled_image'
    }
    
    workflow_json = generate_workflow(
        user_request=user_request,
        context=context,
        save_intermediate=True
    )
    
    with open('output_workflow_upscale.json', 'w', encoding='utf-8') as f:
        json.dump(workflow_json, f, indent=2, ensure_ascii=False)
    
    print(f"\n生成完成！")


def example_3_custom_generator():
    """示例3：自定义生成器配置"""
    print("=" * 60)
    print("示例3：自定义配置")
    print("=" * 60)
    
    # 创建生成器实例
    generator = ComfyUIWorkflowGenerator(config_path="config.yaml")
    
    # 可以访问各个组件
    print(f"工作流库包含 {len(generator.workflow_library.workflows)} 个工作流")
    
    # 查看统计信息
    stats = generator.workflow_library.get_statistics()
    print(f"统计信息: {stats}")
    
    # 生成工作流
    user_request = "生成一个动漫风格的场景图"
    workflow_json = generator.generate(user_request, save_intermediate=True)
    
    print(f"\n生成完成！")


def example_4_add_workflow_to_library():
    """示例4：添加工作流到库"""
    print("=" * 60)
    print("示例4：添加工作流到库")
    print("=" * 60)
    
    from core.data_structures import WorkflowIntent
    
    generator = ComfyUIWorkflowGenerator(config_path="config.yaml")
    
    # 假设我们有一个工作流JSON和代码
    workflow_json = {
        "1": {
            "inputs": {"ckpt_name": "flux_dev.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        },
        # ... 更多节点
    }
    
    workflow_code = """
model, clip, vae = CheckpointLoaderSimple(ckpt_name="flux_dev.safetensors")
conditioning = CLIPTextEncode(clip=clip, text="a beautiful landscape")
"""
    
    # 手动指定意图
    intent = WorkflowIntent(
        task="text-to-image",
        description="基础的文本生成图像工作流",
        keywords=["文本", "图像", "生成"],
        modality="image",
        operation="generation"
    )
    
    # 添加到库
    entry = generator.workflow_library.add_workflow(
        workflow_json=workflow_json,
        workflow_code=workflow_code,
        intent=intent,
        metadata={
            'source': 'manual',
            'tags': ['basic', 'text-to-image']
        }
    )
    
    print(f"\n工作流已添加到库: {entry.workflow_id}")
    print(f"当前库包含 {len(generator.workflow_library.workflows)} 个工作流")


if __name__ == "__main__":
    print("\nComfyUI工作流生成器 - 使用示例\n")
    print("请先确保：")
    print("1. 已复制config.yaml.template为config.yaml并填写API密钥")
    print("2. 已下载Reranker模型")
    print("3. 工作流库中至少有一些工作流\n")
    
    choice = input("选择示例 (1-4, 或按Enter跳过): ").strip()
    
    if choice == '1':
        example_1_simple_generation()
    elif choice == '2':
        example_2_with_context()
    elif choice == '3':
        example_3_custom_generator()
    elif choice == '4':
        example_4_add_workflow_to_library()
    else:
        print("跳过示例执行")
        print("\n你可以直接调用:")
        print("  from generator import generate_workflow")
        print("  workflow = generate_workflow('你的需求')")
