# 测试文档

## 运行测试

### 安装pytest

```bash
pip install pytest pytest-cov
```

### 运行所有测试

```bash
# 在项目根目录运行
pytest tests/

# 显示详细输出
pytest tests/ -v

# 显示print输出
pytest tests/ -s

# 生成覆盖率报告
pytest tests/ --cov=core --cov-report=html
```

### 运行特定测试文件

```bash
pytest tests/test_need_decomposer.py
pytest tests/test_code_splitter.py
pytest tests/test_fragment_matcher.py
pytest tests/test_workflow_assembler.py
pytest tests/test_end_to_end.py
```

### 运行特定测试函数

```bash
pytest tests/test_need_decomposer.py::test_need_decomposer_basic
```

## 测试结构

```
tests/
├── conftest.py              # pytest配置和共享fixtures
├── test_need_decomposer.py   # 需求分解模块测试
├── test_code_splitter.py     # 代码拆分模块测试
├── test_fragment_matcher.py  # 片段匹配模块测试
├── test_workflow_assembler.py # 工作流拼接模块测试
└── test_end_to_end.py        # 端到端集成测试
```

## Fixtures说明

### mock_llm_client
模拟的LLM客户端，返回预定义的响应，不需要真实的API调用。

### sample_workflow_json
示例工作流JSON，包含基础的文生图流程。

### sample_workflow_code
示例工作流代码表示。

### sample_node_defs
示例节点定义，包含常用节点的输入输出类型。

### sample_atomic_need
示例原子需求对象。

### sample_workflow_entry
示例工作流条目对象。

## 测试覆盖范围

### 单元测试

- ✅ 需求分解（NeedDecomposer）
  - 基础分解
  - 带依赖关系的分解
  - LLM失败回退
  - 依赖图构建
  - 拓扑排序
  - 环检测

- ✅ 代码拆分（CodeSplitter）
  - 规则拆分
  - LLM拆分
  - 混合拆分
  - 边界节点检测
  - 类别推断
  - 空工作流处理

- ✅ 片段匹配（FragmentMatcher）
  - 基础匹配
  - LLM判断
  - 规则匹配
  - 阈值控制
  - 类别兼容性
  - 关键词匹配
  - 约束匹配

- ✅ 工作流拼接（WorkflowAssembler）
  - 基础拼接
  - 代码片段组合
  - 变量重命名
  - 代码转JSON
  - 引用处理
  - 类型查找

### 集成测试

- ✅ 端到端流程
  - 简单工作流生成
  - 带上下文的生成
  - 验证器错误捕获
  - 完整流程各阶段

## Mock策略

测试使用Mock对象模拟外部依赖：

1. **LLM API**: 使用mock_llm_client fixture
2. **Embedding模型**: 返回固定向量
3. **Reranker模型**: 返回排序后的列表
4. **文件系统**: 使用pytest的tmp_path

这样可以在不需要真实API密钥和模型的情况下运行测试。

## 持续集成

可以配置GitHub Actions自动运行测试：

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest tests/ --cov=core
```

## 编写新测试

### 测试模板

```python
import pytest
from core.your_module import YourClass

def test_your_function(mock_llm_client, sample_node_defs):
    """测试描述"""
    # 准备
    obj = YourClass(mock_llm_client, sample_node_defs)
    
    # 执行
    result = obj.your_method(input_data)
    
    # 验证
    assert result is not None
    assert isinstance(result, ExpectedType)
    assert result.property == expected_value
```

### 使用Mock

```python
from unittest.mock import Mock, patch

# 模拟方法
mock_obj = Mock()
mock_obj.method.return_value = "expected_value"

# 模拟属性
mock_obj.property = 123

# 验证调用
assert mock_obj.method.called
assert mock_obj.method.call_count == 1
```

## 常见问题

### Q: 测试运行很慢
A: 检查是否有测试在进行真实的API调用。确保使用mock对象。

### Q: 导入错误
A: 确保在项目根目录运行pytest，或者设置PYTHONPATH。

### Q: Fixture未找到
A: 检查conftest.py是否在正确位置。

## 调试测试

```bash
# 在失败处进入debugger
pytest tests/ --pdb

# 只运行失败的测试
pytest tests/ --lf

# 停在第一个失败
pytest tests/ -x
```
