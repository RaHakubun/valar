# 快速开始指南

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

## 🚀 运行爬虫

### 1. GitHub数据源（推荐先测试）

```bash
# 测试模式 - 只爬取少量数据
python -m crawler.main --source github --max-count 10

# 完整爬取
python -m crawler.main --source github
```

### 2. 所有数据源

```bash
python -m crawler.main --source all
```

## 📊 爬取结果

已成功测试：
- ✅ **GitHub爬虫** - 成功爬取5个工作流（受API速率限制影响）
  - 数据位置：`data/raw/github/`
  - 统计信息：`data/raw/github/crawl_stats.json`

待实现：
- ⚠️ **OpenArt.ai** - 需要API调研
- ⚠️ **ComfyWorkflows.com** - 需要API调研  
- ⚠️ **Civitai** - 基础实现完成，待测试

## 🔍 查看已爬取数据

```bash
# 列出所有爬取的工作流
ls -lh data/raw/github/

# 查看统计信息
cat data/raw/github/crawl_stats.json

# 查看工作流示例
cat data/raw/github/workflow_comfyanonymous_ComfyUI_examples_cosmos_image_to_video_cosmos_7B.json | python -m json.tool | head -50
```

## ⚙️ 配置说明

编辑 `crawler/config.py` 可调整：

```python
# 速率限制（秒）
"rate_limit": 1.0

# 并发数
"max_workers": 5

# 启用/禁用数据源
"enabled": True
```

## 🐛 常见问题

### GitHub API速率限制

**问题**：`403 rate limit exceeded`

**解决方案**：
1. 等待一小时后重试
2. 设置GitHub Token（推荐）：
   ```python
   # 在 crawler/github_crawler.py 中
   self.github_token = "your_github_token_here"
   ```

### 缺少依赖

```bash
pip install requests beautifulsoup4
```

## 📈 下一步

1. **实现数据清洗**：参考论文第3章的清洗流程
2. **分析Web平台API**：OpenArt和ComfyWorkflows
3. **测试双向转换**：使用已有的 `main.py` 解析器
4. **数据验证**：检查节点完整性和DAG结构

## 📚 参考

- 论文：ComfyUI-R1 Section 3.1 Knowledge Bases
- 数据收集：27K → 4K（保留率14.5%）
- 平均每工作流：21个节点
