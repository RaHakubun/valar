# Workflow Library 清理和重建指南

## 📋 概述

提供一键清空workflow_library的功能，方便重新导入和组织workflow数据。

---

## 🔧 清理脚本功能

### `clean_workflow_library.py`

#### 会清空的内容
- ✅ `workflows/` - 所有workflow JSON文件
- ✅ `metadata/` - 所有元数据文件
- ✅ `code/` - 所有代码表示文件
- ✅ `embeddings.faiss` - 向量索引文件
- ✅ `embeddings.faiss.mapping.json` - 索引映射文件
- ✅ `node_meta.json` - 节点元数据
- ✅ `node_statistics.json` - 节点统计信息

#### 保留的内容
- ✅ 目录结构（workflows/, metadata/, code/）
- ✅ 配置文件（config.yaml）
- ✅ 其他数据目录（data/raw, data/processed）

---

## 🚀 使用方法

### 1. 查看当前统计

```bash
python clean_workflow_library.py --stats
```

**输出示例**:
```
================================================================================
Workflow Library 统计
================================================================================

📊 统计信息:
  - Workflows: 43 个
  - Metadata: 43 个
  - 向量索引: 存在 (0.25 MB)
  - 节点元数据: 存在

✅ Library包含 43 个workflow
```

### 2. 清空（需要确认）

```bash
python clean_workflow_library.py --clean
```

**执行流程**:
```
================================================================================
清空Workflow Library
================================================================================

将要删除以下内容:
  - workflows/ (43 个workflow)
  - metadata/ (43 个metadata文件)
  - embeddings.faiss (0.25 MB)
  - embeddings.faiss.mapping.json
  - node_meta.json
  - node_statistics.json

⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  
警告: 此操作不可逆！所有workflow数据将被永久删除！
⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  ⚠️  

确认删除? (输入 'YES' 继续): YES

开始清理...
  ✓ 清空 workflows/
  ✓ 清空 metadata/
  ✓ 删除 embeddings.faiss
  ✓ 删除 embeddings.faiss.mapping.json
  ✓ 删除 node_meta.json
  ✓ 删除 node_statistics.json

================================================================================
✅ 清理完成！共删除 6 项
================================================================================

现在可以重新导入workflow:
  python recorder.py --add <workflow.json>
  python recorder.py --batch workflowbench/
```

### 3. 强制清空（无需确认）⚠️

```bash
python clean_workflow_library.py --force
```

**警告**: 此命令会直接删除所有数据，无需确认！仅用于脚本自动化。

### 4. 交互式模式

```bash
python clean_workflow_library.py
```

会先显示统计信息，然后询问是否清空。

---

## 🔄 完整工作流程

### 场景1: 重新组织现有workflow

```bash
# 1. 查看当前状态
python clean_workflow_library.py --stats

# 2. 备份（可选）
cp -r data/workflow_library data/workflow_library_backup_$(date +%Y%m%d)

# 3. 清空
python clean_workflow_library.py --clean

# 4. 重新导入
python recorder.py --batch workflowbench/

# 5. 验证
python clean_workflow_library.py --stats
```

### 场景2: 从零开始构建

```bash
# 1. 清空现有数据
python clean_workflow_library.py --force

# 2. 批量导入新的workflow
python recorder.py --batch workflowbench/

# 3. 查看统计
python recorder.py --stats
```

### 场景3: 测试和调试

```bash
# 1. 清空
python clean_workflow_library.py --force

# 2. 添加单个测试workflow
python recorder.py --add test_workflow.json

# 3. 测试系统
python test_driver_generate.py

# 4. 如果有问题，重复步骤1-3
```

---

## 📊 清理前后对比

### 清理前
```
data/workflow_library/
├── workflows/           # 43个JSON文件，总计~2MB
├── metadata/            # 43个meta文件，包含embedding
├── embeddings.faiss     # 256KB向量索引
├── embeddings.faiss.mapping.json
├── node_meta.json       # 节点元数据
└── node_statistics.json # 节点统计
```

### 清理后
```
data/workflow_library/
├── workflows/           # 空目录
├── metadata/            # 空目录
└── (无其他文件)
```

---

## ⚠️ 注意事项

### 1. 数据不可恢复
清空操作会**永久删除**所有workflow数据，删除前请确保：
- 已备份重要数据
- 或者可以重新导入原始workflow JSON

### 2. 不会影响的内容
以下内容**不会**被清理脚本影响：
- `workflowbench/` 目录（原始workflow数据）
- `config.yaml` 配置文件
- `data/raw/` 和 `data/processed/`
- 其他项目文件

### 3. 推荐备份策略
如果数据重要，建议在清理前备份：
```bash
# 备份整个workflow_library
tar -czf workflow_library_backup_$(date +%Y%m%d_%H%M%S).tar.gz data/workflow_library/

# 恢复备份
tar -xzf workflow_library_backup_YYYYMMDD_HHMMSS.tar.gz
```

---

## 🔧 高级用法

### 作为Python模块使用

```python
from clean_workflow_library import clean_workflow_library, show_library_stats

# 显示统计
show_library_stats()

# 清空（需要确认）
clean_workflow_library(confirm=True)

# 强制清空
clean_workflow_library(confirm=False)

# 清空自定义路径
clean_workflow_library(library_path='/path/to/library', confirm=False)
```

### 集成到其他脚本

```python
# example_reset.py
from clean_workflow_library import clean_workflow_library
import subprocess

# 1. 清空
print("清空旧数据...")
clean_workflow_library(confirm=False)

# 2. 重新导入
print("导入新数据...")
subprocess.run(["python", "recorder.py", "--batch", "workflowbench/"])

# 3. 测试
print("运行测试...")
subprocess.run(["python", "test_driver_generate.py"])
```

---

## 🐛 常见问题

### Q1: 清空后系统无法运行？
**A**: 这是正常的，清空后需要重新导入workflow：
```bash
python recorder.py --batch workflowbench/
```

### Q2: 清空时提示权限错误？
**A**: 检查文件权限：
```bash
chmod -R u+w data/workflow_library/
```

### Q3: 想要保留部分workflow？
**A**: 清空前先备份：
```bash
# 备份特定workflow
cp data/workflow_library/workflows/wf_xxx.json backup/
cp data/workflow_library/metadata/wf_xxx.meta.json backup/

# 清空
python clean_workflow_library.py --force

# 恢复特定workflow
python recorder.py --add backup/wf_xxx.json
```

### Q4: 如何验证清空成功？
**A**: 运行统计命令：
```bash
python clean_workflow_library.py --stats
# 应该显示: Workflows: 0 个
```

---

## 📝 与recorder.py的配合使用

### recorder.py 现有命令
```bash
# 查看统计
python recorder.py --stats

# 添加单个workflow
python recorder.py --add workflow.json

# 批量添加
python recorder.py --batch workflowbench/

# 搜索workflow
python recorder.py --search "人物"

# 删除单个workflow
python recorder.py --delete wf_xxx
```

### 完整重建流程
```bash
# 1. 查看当前状态
python recorder.py --stats
# 或
python clean_workflow_library.py --stats

# 2. 清空所有数据
python clean_workflow_library.py --clean

# 3. 重新导入
python recorder.py --batch workflowbench/

# 4. 验证
python recorder.py --stats
```

---

## ✅ 总结

`clean_workflow_library.py` 提供了一个**安全、可控**的方式来清空和重建workflow库：

| 命令 | 功能 | 安全性 | 使用场景 |
|------|------|--------|----------|
| `--stats` | 查看统计 | ✅ 完全安全 | 日常检查 |
| `--clean` | 清空（需确认） | ⚠️  需确认 | 手动重建 |
| `--force` | 强制清空 | ❌ 直接删除 | 脚本自动化 |
| 无参数 | 交互模式 | ⚠️  需确认 | 谨慎操作 |

**推荐工作流**:
1. 使用 `--stats` 查看当前状态
2. 使用 `--clean` 安全清空（需手动确认）
3. 使用 `recorder.py --batch` 重新导入
4. 使用 `--stats` 验证结果

🎯 **现在你的workflow库管理更加清晰和可控了！**
