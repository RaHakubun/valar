# ComfyUI工作流记录器 (recorder.py) 使用说明

## 简介

`recorder.py` 是专门用于向工作流库添加新工作流的工具，与主驱动程序 `driver.py` 分离，专注于工作流的管理和扩充功能。

## 主要功能

1. **添加单个工作流** - 从JSON文件添加单个工作流到库中
2. **批量添加工作流** - 从目录中批量添加多个工作流
3. **查看库统计信息** - 获取工作流库的统计信息

## 使用方法

### 命令行使用

```bash
# 添加单个工作流文件
python recorder.py --add path/to/workflow.json

# 添加工作流并指定描述和标签
python recorder.py --add path/to/workflow.json --description "生成粘土风格图像" --tags "clay,generation,portrait"

# 批量添加目录中的所有JSON工作流
python recorder.py --batch path/to/workflow/directory

# 查看工作流库统计信息
python recorder.py --stats

# 指定配置文件
python recorder.py --add path/to/workflow.json --config my_config.yaml
```

### 参数说明

- `--add` 或 `-a`: 添加单个工作流JSON文件
- `--batch` 或 `-b`: 批量添加目录下的所有JSON工作流文件
- `--stats` 或 `-s`: 显示工作流库统计信息
- `--config` 或 `-c`: 配置文件路径（默认为 config.yaml）
- `--description` 或 `-d`: 工作流描述（用于单个添加）
- `--tags` 或 `-t`: 标签列表，用逗号分隔（例如: `tag1,tag2,tag3`）

### 程序中调用

```python
from recorder import WorkflowRecorder

# 创建记录器实例
recorder = WorkflowRecorder(config_path='config.yaml')

# 添加单个工作流
recorder.add_workflow_from_json(
    workflow_path='path/to/workflow.json',
    description='生成粘土风格的肖像',
    tags=['clay', 'portrait', 'generation'],
    source='manual'
)

# 添加工作流从字典
recorder.add_workflow_from_dict(
    workflow_json=your_workflow_dict,
    workflow_code=your_code_repr,  # 可选，如不提供会自动生成
    description='工作流描述',
    tags=['tag1', 'tag2']
)

# 批量添加
success_count = recorder.batch_add_workflows('path/to/workflows/')

# 获取统计信息
stats = recorder.get_library_stats()
```

## 工作流格式要求

添加的工作流必须是有效的 ComfyUI 工作流JSON格式，例如：

```json
{
  "1": {
    "class_type": "EmptyLatentImage",
    "inputs": {
      "width": 512,
      "height": 512,
      "batch_size": 1
    }
  },
  "2": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "a beautiful landscape",
      "clip": ["4", 1]
    }
  },
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["4", 0],
      "positive": ["2", 0],
      "negative": ["6", 0],
      "latent_image": ["1", 0],
      "seed": 12345,
      "steps": 20,
      "cfg": 7.0
    }
  },
  ...
}
```

## 自动处理功能

1. **代码转换** - 自动将JSON工作流转换为代码表示
2. **意图提取** - 使用LLM自动提取工作流意图（如果未提供描述）
3. **Embedding生成** - 生成向量表示用于检索
4. **自动标注** - 为工作流添加标签和元数据

## 输出信息

成功添加工作流后，系统会输出：
- 工作流ID
- 工作流描述
- 节点数量
- 存储位置信息

## 配置文件

需要在 `config.yaml` 中配置API密钥和工作流库路径：

```yaml
# OpenAI API配置（用于LLM调用）
openai:
  api_key: "YOUR_API_KEY_HERE"
  chat_model: "gpt-4-turbo"
  embedding_model: "text-embedding-3-large"

# Gemini API配置（用于Embedding）
gemini:
  api_key: "YOUR_GEMINI_API_KEY_HERE"
  api_base: "https://xiaoai.plus/v1"
  embedding_model: "gemini-embedding-001"

# 工作流库配置
workflow_library:
  data_path: "./data/workflow_library"
```