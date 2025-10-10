# 快速启动指南

## 🚀 5分钟上手

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `openai` - OpenAI API客户端
- `sentence-transformers` - Reranker模型
- `faiss-cpu` - 向量检索
- `pyyaml` - 配置文件
- `pytest` - 测试框架

### 2. 配置API

```bash
# 复制配置模板
cp config.yaml.template config.yaml

# 编辑config.yaml，填写你的OpenAI API Key
# 找到这一行：
#   api_key: "YOUR_OPENAI_API_KEY_HERE"
# 改为：
#   api_key: "sk-..."
```

### 3. 下载Reranker模型

```python
from sentence_transformers import CrossEncoder

# 下载模型到本地
model = CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-V1')
model.save('./models/reranker')
```

或者让系统自动下载（首次运行时）。

### 4. 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 看到绿色的PASSED就成功了！
```

### 5. 生成第一个工作流

```python
from generator import generate_workflow

# 简单使用
workflow_json = generate_workflow("生成一个粘土风格的人物肖像")

# 保存结果
import json
with open('my_workflow.json', 'w') as f:
    json.dump(workflow_json, f, indent=2)

print("✅ 工作流已生成！")
```

---

## 📖 详细步骤

### 步骤1: 准备工作流库

在使用之前，需要至少有一些工作流在库中。有三种方式：

#### 方式A: 使用爬虫（推荐）

```bash
# 爬取ComfyBench的示例工作流
python crawler/main.py --source github --max-count 20
```

#### 方式B: 手动添加

```python
from generator import ComfyUIWorkflowGenerator
from core.data_structures import WorkflowIntent

generator = ComfyUIWorkflowGenerator()

# 你的工作流JSON
workflow_json = {...}

# 你的工作流代码
workflow_code = """
model, clip, vae = CheckpointLoaderSimple(ckpt_name="model.safetensors")
...
"""

# 添加到库
intent = WorkflowIntent(
    task="text-to-image",
    description="基础文生图工作流",
    keywords=["文本", "图像"],
    modality="image",
    operation="generation"
)

generator.workflow_library.add_workflow(
    workflow_json=workflow_json,
    workflow_code=workflow_code,
    intent=intent,
    auto_annotate=False  # 已手动指定intent
)
```

#### 方式C: 让系统自动标注

```python
# 如果你只有JSON，系统可以自动提取意图
generator.workflow_library.add_workflow(
    workflow_json=workflow_json,
    workflow_code=workflow_code,
    auto_annotate=True  # 使用GPT-4自动提取意图
)
```

### 步骤2: 检查库状态

```python
from generator import ComfyUIWorkflowGenerator

generator = ComfyUIWorkflowGenerator()

# 查看统计
stats = generator.workflow_library.get_statistics()
print(f"工作流总数: {stats['total_count']}")
print(f"平均节点数: {stats['avg_node_count']:.1f}")
print(f"按来源: {stats['by_source']}")
```

### 步骤3: 生成工作流

```python
# 基础用法
workflow = generate_workflow("生成动漫风格的风景图")

# 带上下文
workflow = generate_workflow(
    "将这张图片超分",
    context={
        'input_file': 'input.png',
        'output_prefix': 'upscaled'
    }
)

# 保存中间结果（用于调试）
workflow = generate_workflow(
    "生成粘土风格人物",
    save_intermediate=True  # 会保存到logs/目录
)
```

### 步骤4: 查看日志

```bash
# 生成过程会有详细日志
[阶段0] 用户需求: 生成粘土风格人物肖像

[阶段1] 需求匹配
  1.1 需求分解...
  → 分解为 1 个原子需求:
    - 生成粘土风格人物肖像 (generation)
  1.2 向量检索...
  → 检索到 10 个候选工作流

[阶段2] 工作流框架适配
  2.1 代码拆分...
  → 拆分为 35 个代码片段
  2.2 片段-需求匹配...
  → 匹配成功 5 个片段
  2.3 工作流拼接...
  → 拼接完成，包含 5 个片段
  2.4 框架验证...
  ✓ 验证通过

[阶段3] 可执行工作流合成
  3.1 代码→JSON转换...
  → 生成 6 个节点
  3.2 参数补全...
  ✓ 参数补全完成
  3.3 最终验证...
  ✓ JSON验证通过

[完成] 工作流生成完毕
```

---

## 🔧 高级用法

### 自定义配置

```python
from generator import ComfyUIWorkflowGenerator

# 使用自定义配置文件
generator = ComfyUIWorkflowGenerator(config_path="my_config.yaml")

# 访问各个组件
print(f"库中有 {len(generator.workflow_library.workflows)} 个工作流")

# 调整参数
generator.fragment_matcher.matching_threshold = 0.7  # 提高匹配阈值
generator.code_splitter.strategy = "llm"  # 切换为LLM拆分
```

### 多步骤生成

```python
generator = ComfyUIWorkflowGenerator()

# 步骤1: 需求分解
decomposed = generator.need_decomposer.decompose("复杂的需求")
print(f"分解为 {len(decomposed.atomic_needs)} 个子需求")

# 步骤2: 手动调整需求
decomposed.atomic_needs[0].priority = 10  # 提高优先级

# 步骤3: 继续生成
# ... 后续步骤
```

### 批量生成

```python
requests = [
    "生成动漫风格场景",
    "图像超分4倍",
    "应用粘土风格滤镜"
]

for i, req in enumerate(requests):
    workflow = generate_workflow(req)
    
    with open(f'workflow_{i}.json', 'w') as f:
        json.dump(workflow, f)
    
    print(f"✅ {i+1}/{len(requests)} 完成")
```

---

## 🧪 开发和调试

### 运行特定测试

```bash
# 测试需求分解
pytest tests/test_need_decomposer.py -v

# 测试代码拆分
pytest tests/test_code_splitter.py -v

# 测试端到端
pytest tests/test_end_to_end.py -v -s  # -s显示print输出
```

### 查看覆盖率

```bash
pytest tests/ --cov=core --cov-report=html
# 打开 htmlcov/index.html 查看详细报告
```

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 会输出详细的调试信息
workflow = generate_workflow("测试需求")
```

### 查看中间结果

```python
# 启用保存中间结果
workflow = generate_workflow(
    "测试需求",
    save_intermediate=True
)

# 查看logs/目录下的JSON文件
# 包含：
# - 分解后的需求
# - 检索到的工作流
# - 拆分的片段
# - 拼接的代码
```

---

## 🐛 常见问题

### Q1: ImportError: No module named 'faiss'

```bash
pip install faiss-cpu
# 或GPU版本
pip install faiss-gpu
```

### Q2: OpenAI API错误

```
Error: Incorrect API key provided
```

检查config.yaml中的API密钥是否正确。

### Q3: 生成的工作流为空

可能原因：
1. 工作流库为空 → 先添加一些工作流
2. 需求匹配失败 → 降低matching_threshold
3. 向量索引未建立 → 重新加载库

### Q4: 测试失败

```bash
# 清除缓存重试
pytest tests/ --cache-clear

# 只运行失败的测试
pytest tests/ --lf
```

### Q5: 内存不足

如果处理大量工作流：
```python
# 使用较小的embedding模型
# 或减少top_k_recall数量
config['workflow_library']['retrieval']['top_k_recall'] = 20
```

---

## 📚 下一步

1. **添加更多工作流** - 库越大，生成质量越好
2. **调整提示词** - 在prompts.py中微调
3. **实验评估** - 在ComfyBench上测试Pass Rate
4. **优化性能** - 使用缓存、批处理等

---

## 🎯 完整示例

```python
#!/usr/bin/env python3
"""完整的使用示例"""

from generator import ComfyUIWorkflowGenerator
import json

def main():
    # 1. 初始化
    print("🚀 初始化生成器...")
    generator = ComfyUIWorkflowGenerator()
    
    # 2. 检查库状态
    stats = generator.workflow_library.get_statistics()
    print(f"📊 工作流库: {stats['total_count']} 个工作流")
    
    if stats['total_count'] == 0:
        print("⚠️  库为空，请先添加工作流")
        return
    
    # 3. 生成工作流
    print("\n🎨 开始生成...")
    user_request = "生成一个粘土风格的人物肖像，并进行4倍超分"
    
    try:
        workflow = generator.generate(
            user_request,
            save_intermediate=True
        )
        
        # 4. 保存结果
        output_file = 'generated_workflow.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 成功！工作流已保存到: {output_file}")
        print(f"📝 节点数: {len(workflow)}")
        
        # 5. 显示节点类型
        node_types = [
            node.get('class_type') 
            for node in workflow.values() 
            if isinstance(node, dict)
        ]
        print(f"🔧 节点类型: {', '.join(set(node_types))}")
        
    except Exception as e:
        print(f"\n❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
```

保存为 `run.py`，然后：

```bash
python run.py
```

---

## 🎉 恭喜！

你已经掌握了基本用法。现在可以：

- ✅ 生成ComfyUI工作流
- ✅ 调整配置和参数
- ✅ 运行测试验证
- ✅ 查看日志调试

更多信息请查看：
- `README.md` - 项目概览
- `tests/README.md` - 测试文档
- `DETAILED_DESIGN_PLAN.md` - 详细设计
- `IMPLEMENTATION_SPECS.md` - 实现规格
