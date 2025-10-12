# ComfyUI工作流数据爬虫

## 概述

基于ComfyUI-R1论文第3章的数据收集方法实现的工作流爬虫系统。

## 数据源

### 1. GitHub仓库（已实现）
- comfyanonymous/ComfyUI_examples
- cubiq/ComfyUI_Workflows
- Comfy-Org/example_workflows
- aimpowerment/comfyui-workflows
- comfy-deploy/comfyui-workflows

### 2. Web平台（部分实现）
- **OpenArt.ai** - 需要API分析
- **ComfyWorkflows.com** - 需要API分析
- **Civitai** - 基础实现完成（使用官方API）

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 1. 爬取所有数据源

```bash
python -m crawler.main --source all
```

### 2. 爬取特定数据源

```bash
# GitHub仓库
python -m crawler.main --source github

# Civitai平台
python -m crawler.main --source civitai
```

### 3. 测试模式（限制数量）

```bash
python -m crawler.main --source github --max-count 10
```

## 项目结构

```
crawler/
├── __init__.py           # 包初始化
├── config.py             # 配置文件
├── base_crawler.py       # 爬虫基类
├── github_crawler.py     # GitHub爬虫实现
├── web_crawler.py        # Web平台爬虫实现
└── main.py               # 主程序入口

data/
├── raw/                  # 原始爬取数据
│   ├── github/
│   ├── civitai/
│   └── ...
└── processed/            # 处理后的数据
```

## 数据存储格式

每个工作流保存为独立的JSON文件：

```json
{
  "nodes": [...],
  "links": [...],
  "_metadata": {
    "source": "github",
    "repo": "comfyanonymous/ComfyUI_examples",
    "path": "workflows/example.json",
    "filename": "example.json"
  }
}
```

## 配置说明

编辑 `crawler/config.py` 可以调整：

- **速率限制**：`rate_limit` 参数
- **并发数**：`max_workers` 参数
- **过滤规则**：`WORKFLOW_FILTERS` 配置
- **数据源启用/禁用**：`enabled` 参数

## TODO

### 高优先级
- [ ] 分析OpenArt.ai的实际API/网页结构
- [ ] 分析ComfyWorkflows.com的实际API/网页结构
- [ ] 实现数据清洗逻辑（去重、格式验证）
- [ ] 实现双向转换测试

### 中优先级
- [ ] 添加节点文档爬取
- [ ] 支持增量更新
- [ ] 添加更多GitHub仓库
- [ ] 实现并发爬取

### 低优先级
- [ ] 使用Selenium/Playwright处理动态内容
- [ ] 添加代理池支持
- [ ] 实现断点续传
- [ ] 添加Web UI

## 注意事项

1. **速率限制**：请遵守各平台的速率限制，避免被封禁
2. **NSFW内容**：已配置过滤规则，但仍需人工审核
3. **API调研**：Web平台爬虫需要实际分析其API结构
4. **法律合规**：确保爬取行为符合目标网站的ToS

## 参考

- ComfyUI-R1论文 Section 3.1 Knowledge Bases
- 数据收集：27K → 4K（保留率14.5%）
- 平均每工作流：21个节点
