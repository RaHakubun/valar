# ComfyUI工作流检索-适配-合成系统 - Driver使用说明

## 简介

`driver.py` 是本项目的主要入口文件，用于驱动整个 ComfyUI 工作流生成系统。该系统实现了从用户需求分解到工作流适配与合成的完整链路：

1. **需求分解** - 将用户自然语言需求分解为原子需求
2. **工作流检索** - 从工作流库中检索相关工作流
3. **工作流适配** - 对检索到的工作流进行拆分和片段匹配
4. **工作流合成** - 将适配的片段拼接成最终的工作流

## 使用方法

### 命令行使用

```bash
# 基本用法
python driver.py --request "生成一个粘土风格的人物肖像，并进行4倍超分" --output output_workflow.json

# 指定配置文件
python driver.py --request "生成一只猫咪的图像，使用Flux模型" --config config.yaml --output my_workflow.json
```

参数说明：
- `--request` 或 `-r`: 用户需求描述（必需）
- `--config` 或 `-c`: 配置文件路径（默认为 config.yaml）
- `--output` 或 `-o`: 输出文件路径（默认为 generated_workflow.json）

### 程序中调用

```python
from driver import ComfyUIWorkflowGenerator

# 创建生成器实例
generator = ComfyUIWorkflowGenerator(config_path='config.yaml')

# 生成工作流
result = generator.generate_workflow("生成一个粘土风格的人物肖像")

# 获取生成的工作流JSON
workflow_json = result['workflow_json']
```

## 系统架构

### 核心模块

- `NeedDecomposer`: 需求分解器
- `WorkflowLibrary`: 工作流库管理
- `WorkflowRetriever`: 工作流检索器（包含向量检索和重排序）
- `CodeSplitter`: 代码拆分器
- `FragmentMatcher`: 片段-需求匹配器
- `WorkflowAssembler`: 工作流拼接器
- `CodeToJsonConverter`: 代码到JSON转换器

### 配置文件

配置文件 `config.yaml` 需要包含以下配置：

```yaml
# OpenAI API配置（用于LLM调用）
openai:
  api_key: "YOUR_API_KEY_HERE"
  api_base: "https://api.openai.com/v1"
  chat_model: "gpt-4-turbo"
  embedding_model: "text-embedding-3-large"
  temperature: 0.7
  max_tokens: 4096

# Gemini API配置（用于Embedding）
gemini:
  api_key: "YOUR_GEMINI_API_KEY_HERE"
  api_base: "https://xiaoai.plus/v1"
  embedding_model: "gemini-embedding-001"

# 其他配置...
```

## API支持

系统支持以下API配置：

1. **OpenAI API**: 用于聊天模型调用
2. **Gemini API**: 用于embedding生成（配置在gemini部分）

### Gemini API配置示例

```python
import http.client
import json

conn = http.client.HTTPSConnection("xiaoai.plus")
payload = json.dumps({
   "input": "The food was delicious and the waiter...",
   "model": "text-embedding-ada-002", 
   "encoding_format": "float"
})
headers = {
   'Authorization': 'Bearer YOUR_API_KEY',
   'Content-Type': 'application/json'
}
conn.request("POST", "/v1/embeddings", payload, headers)
res = conn.getresponse()
data = res.read()
print(data.decode("utf-8"))
```

## 输出格式

生成的输出包含：
- `user_request`: 原始用户需求
- `decomposed_needs`: 分解后的原子需求列表
- `workflow_json`: 生成的ComfyUI工作流JSON
- `framework_code`: 工作流框架代码表示
- `success`: 生成是否成功
- `error`: 错误信息（如果有）

## 日志系统

系统会自动生成日志文件到 `./logs/workflow_generator.log`，便于调试和监控。

## 演示模式

直接运行 `python driver.py` 可以进入演示模式，展示系统功能。