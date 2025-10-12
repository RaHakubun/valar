# 🚀 快速参考指南

ComfyUI工作流生成系统 - 所有常用命令

---

## 📋 Workflow Library 管理

### 查看统计信息
```bash
# 方式1: 使用清理脚本
python clean_workflow_library.py --stats

# 方式2: 使用recorder
python recorder.py --stats
```

### 清空Library
```bash
# 安全清空（需要输入 'YES' 确认）
python clean_workflow_library.py --clean

# 强制清空（无需确认，危险！）
python clean_workflow_library.py --force

# 交互式清空
python clean_workflow_library.py
```

### 重建Library
```bash
# 一键重建（需要确认）
python rebuild_library.py

# 快速重建（无需确认）
python rebuild_library.py --force

# 从指定目录重建
python rebuild_library.py --source /path/to/workflows/
```

---

## 📥 导入Workflow

### 添加单个workflow
```bash
python recorder.py --add workflow.json
```

### 批量导入
```bash
# 从workflowbench/导入所有
python recorder.py --batch workflowbench/

# 从指定目录导入
python recorder.py --batch /path/to/workflows/
```

### 导入时的过程
系统会自动：
1. ✅ 解析workflow JSON
2. ✅ 转换为Python代码表示
3. ✅ 使用LLM提取意图描述
4. ✅ 生成embedding向量
5. ✅ 添加到FAISS索引
6. ✅ 保存metadata

---

## 🔍 查询和搜索

### 搜索workflow
```bash
python recorder.py --search "人物"
python recorder.py --search "超分"
```

### 查看workflow详情
```bash
python recorder.py --show wf_xxx
```

### 删除workflow
```bash
python recorder.py --delete wf_xxx
```

---

## 🎯 生成Workflow

### 使用demo函数
```python
# test_driver_generate.py
from driver import ComfyUIWorkflowGenerator

generator = ComfyUIWorkflowGenerator('config.yaml')
result = generator.generate_workflow("生成一个粘土风格的人物肖像")
```

### 运行测试
```bash
python test_driver_generate.py
```

### 查看详细输出
生成过程会显示：
- ✅ 需求分解结果
- ✅ 检索到的候选workflow
- ✅ Reranker评分
- ✅ 工作流框架代码
- ✅ 最终JSON结构

---

## 🔧 系统维护

### 一键迁移embedding（首次使用）
```bash
python migrate_embeddings.py
```

**说明**: 为现有workflow生成并保存embedding，避免重复生成。只需运行一次！

### 完整重建流程
```bash
# 方式1: 使用重建脚本（推荐）
python rebuild_library.py --force

# 方式2: 手动步骤
python clean_workflow_library.py --force
python recorder.py --batch workflowbench/
python clean_workflow_library.py --stats
```

---

## 📊 系统状态检查

### 检查配置
```bash
cat config.yaml
```

### 检查library状态
```bash
python clean_workflow_library.py --stats
```

**输出示例**:
```
📊 统计信息:
  - Workflows: 43 个
  - Metadata: 43 个
  - 向量索引: 存在 (0.25 MB)
  - 节点元数据: 存在
```

### 检查向量索引
```bash
ls -lh data/workflow_library/*.faiss
```

---

## 🐛 常见问题修复

### 问题1: 启动慢，多次embedding API调用
```bash
# 解决: 运行迁移脚本
python migrate_embeddings.py
```

### 问题2: Reranker崩溃（segmentation fault）
✅ **已修复**: 已切换到API模式，不会再崩溃

### 问题3: Workflow数据混乱
```bash
# 解决: 清空并重建
python rebuild_library.py --force
```

### 问题4: 向量索引损坏
```bash
# 解决: 删除索引，重新导入
rm data/workflow_library/embeddings.faiss*
python recorder.py --batch workflowbench/
```

### 问题5: 节点元数据错误
```bash
# 解决: 删除元数据，重新生成
rm data/workflow_library/node_meta.json
python recorder.py --batch workflowbench/
```

---

## 📁 目录结构

```
.
├── config.yaml                      # 配置文件
├── driver.py                        # 主生成器
├── recorder.py                      # Workflow管理
├── main.py                          # 双向转换（JSON↔️Code）
│
├── clean_workflow_library.py        # 清空脚本
├── rebuild_library.py               # 重建脚本
├── migrate_embeddings.py            # Embedding迁移
├── test_driver_generate.py          # 测试脚本
│
├── data/workflow_library/           # Workflow库
│   ├── workflows/                   # JSON文件
│   ├── metadata/                    # 元数据（含embedding）
│   ├── code/                        # 代码表示
│   ├── embeddings.faiss             # 向量索引
│   ├── embeddings.faiss.mapping.json
│   ├── node_meta.json               # 节点元数据
│   └── node_statistics.json         # 节点统计
│
├── workflowbench/                   # 原始workflow数据
│   ├── 001.json
│   ├── 002.json
│   └── ...
│
└── core/                            # 核心模块
    ├── llm_client.py
    ├── vector_search.py
    ├── workflow_library.py
    └── ...
```

---

## 🔑 API配置

### OpenAI API (embedding + chat)
```yaml
openai:
  api_key: "sk-..."
  api_base: "https://xiaoai.plus/v1"
  embedding_model: "text-embedding-ada-002"
  chat_model: "gpt-4o-mini"
```

### SiliconFlow Reranker API
```yaml
reranker:
  type: "api"
  api_url: "https://api.siliconflow.cn/v1/rerank"
  api_key: "sk-..."
  model: "Pro/BAAI/bge-reranker-v2-m3"
```

---

## 📈 性能优化

### 已优化的部分
✅ Embedding保存到metadata（避免重复生成）  
✅ 向量索引持久化（快速加载）  
✅ Reranker使用API（避免崩溃）  
✅ 候选数量限制（最多20个）  

### 性能指标
- **系统启动**: ~2秒（从30秒优化）
- **单个需求检索**: ~1秒
- **Reranker评分**: ~0.5秒（API调用）
- **完整生成流程**: ~40秒

---

## 🎓 学习路径

### 1. 快速上手（5分钟）
```bash
# 查看现有workflow
python clean_workflow_library.py --stats

# 测试生成
python test_driver_generate.py
```

### 2. 导入数据（10分钟）
```bash
# 清空并重建
python rebuild_library.py --force

# 验证
python recorder.py --stats
```

### 3. 深入理解（30分钟）
阅读文档：
- `FINAL_SUMMARY.md` - 系统总结
- `DRIVER_FIXES.md` - Bug修复历史
- `RERANKER_API_MIGRATION.md` - API迁移
- `CLEAN_AND_REBUILD.md` - 清理重建指南

### 4. 自定义开发（1小时+）
查看核心代码：
- `core/workflow_library.py` - Library管理
- `core/vector_search.py` - 检索和rerank
- `driver.py` - 完整生成流程
- `main.py` - JSON↔️Code转换

---

## 🆘 获取帮助

### 查看命令帮助
```bash
python clean_workflow_library.py --help
python rebuild_library.py --help
python recorder.py --help
```

### 查看文档
```bash
# 列出所有markdown文档
ls *.md

# 查看特定文档
cat QUICK_REFERENCE.md
cat CLEAN_AND_REBUILD.md
```

---

## ✅ 每日检查清单

### 使用前检查
- [ ] config.yaml配置正确
- [ ] API密钥有效
- [ ] workflow_library包含数据
- [ ] 向量索引文件存在

### 使用后检查
- [ ] 生成的workflow有效
- [ ] 日志无错误
- [ ] API调用成功
- [ ] 系统性能正常

---

## 🎯 最佳实践

### ✅ 推荐做法
1. 定期备份workflow_library
2. 使用`--stats`检查状态
3. 清空前先确认
4. 导入后验证数据
5. 保持原始JSON文件

### ❌ 避免做法
1. 不要使用`--force`除非确定
2. 不要手动编辑.faiss文件
3. 不要删除metadata中的embedding
4. 不要混合不同版本的数据
5. 不要在生产环境直接测试

---

## 📞 快速命令索引

| 任务 | 命令 |
|------|------|
| 查看统计 | `python clean_workflow_library.py --stats` |
| 清空数据 | `python clean_workflow_library.py --clean` |
| 重建库 | `python rebuild_library.py --force` |
| 导入单个 | `python recorder.py --add file.json` |
| 批量导入 | `python recorder.py --batch workflowbench/` |
| 测试生成 | `python test_driver_generate.py` |
| 迁移embedding | `python migrate_embeddings.py` |

**🔖 将此页面加入书签，随时查阅！**
