"""
数据爬取配置文件
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# 创建目录
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 数据源配置
DATA_SOURCES = {
    "openart": {
        "name": "OpenArt.ai",
        "base_url": "https://openart.ai",
        "api_endpoint": "/api/workflows",  # 需要实际调研API
        "enabled": True,
        "rate_limit": 1.0,  # 秒
    },
    "comfyworkflows": {
        "name": "ComfyWorkflows.com",
        "base_url": "https://comfyworkflows.com",
        "api_endpoint": "/api/workflows",
        "enabled": True,
        "rate_limit": 1.0,
    },
    "civitai": {
        "name": "Civitai",
        "base_url": "https://civitai.com",
        "api_endpoint": "/api/v1/images",
        "enabled": True,
        "rate_limit": 1.0,
    },
    "github": {
        "name": "GitHub Repositories",
        "enabled": True,
        "repos": [
            "comfyanonymous/ComfyUI_examples",
            "cubiq/ComfyUI_Workflows",
            "Comfy-Org/example_workflows",
            "aimpowerment/comfyui-workflows",
            "comfy-deploy/comfyui-workflows",
        ],
    },
}

# 爬取设置
CRAWLER_CONFIG = {
    "max_workers": 5,
    "timeout": 30,
    "retry_times": 3,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "save_images": False,  # 是否保存预览图
    "download_batch_size": 100,
}

# 文件过滤规则
WORKFLOW_FILTERS = {
    "min_nodes": 3,  # 最少节点数
    "max_nodes": 200,  # 最多节点数
    "required_keys": ["nodes", "links"],  # JSON必须包含的键
    "exclude_keywords": ["NSFW", "nsfw", "adult"],  # 排除关键词
}

# 输出格式
OUTPUT_FORMAT = {
    "workflow_json": "workflow_{id}.json",
    "metadata": "metadata_{id}.json",
    "summary": "crawl_summary.json",
}
