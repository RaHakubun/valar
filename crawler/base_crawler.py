"""
爬虫基类
"""

import time
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import CRAWLER_CONFIG, RAW_DIR


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, source_name: str, config: Dict):
        self.source_name = source_name
        self.config = config
        self.logger = logging.getLogger(f"Crawler.{source_name}")
        self.session = self._create_session()
        self.output_dir = RAW_DIR / source_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
    
    def _create_session(self) -> requests.Session:
        """创建带重试机制的Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=CRAWLER_CONFIG["retry_times"],
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": CRAWLER_CONFIG["user_agent"]
        })
        return session
    
    def rate_limit_wait(self):
        """速率限制等待"""
        if "rate_limit" in self.config:
            time.sleep(self.config["rate_limit"])
    
    @abstractmethod
    def fetch_workflow_list(self) -> List[Dict]:
        """获取工作流列表（需子类实现）"""
        pass
    
    @abstractmethod
    def fetch_workflow_detail(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情（需子类实现）"""
        pass
    
    def save_workflow(self, workflow_data: Dict, workflow_id: str):
        """保存工作流数据"""
        file_path = self.output_dir / f"workflow_{workflow_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Saved workflow {workflow_id} to {file_path}")
    
    def run(self, max_count: Optional[int] = None) -> Dict:
        """执行爬取任务"""
        self.logger.info(f"Starting crawler for {self.source_name}")
        
        try:
            workflows = self.fetch_workflow_list()
            self.stats["total"] = len(workflows)
            
            if max_count:
                workflows = workflows[:max_count]
            
            for workflow_info in workflows:
                try:
                    workflow_id = workflow_info.get("id", workflow_info.get("name"))
                    self.logger.info(f"Fetching workflow {workflow_id}")
                    
                    detail = self.fetch_workflow_detail(workflow_id)
                    if detail:
                        self.save_workflow(detail, workflow_id)
                        self.stats["success"] += 1
                    else:
                        self.stats["skipped"] += 1
                    
                    self.rate_limit_wait()
                    
                except Exception as e:
                    self.logger.error(f"Error processing workflow {workflow_id}: {e}")
                    self.stats["failed"] += 1
        
        except Exception as e:
            self.logger.error(f"Error in crawler run: {e}")
        
        finally:
            self.logger.info(f"Crawler finished. Stats: {self.stats}")
            self._save_stats()
        
        return self.stats
    
    def _save_stats(self):
        """保存统计信息"""
        stats_file = self.output_dir / "crawl_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                "source": self.source_name,
                "stats": self.stats,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }, f, indent=2)
