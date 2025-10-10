"""
GitHub仓库爬虫
"""

import json
import re
from typing import Dict, List, Optional
from pathlib import Path

from .base_crawler import BaseCrawler


class GitHubCrawler(BaseCrawler):
    """GitHub仓库爬虫 - 爬取ComfyUI工作流示例"""
    
    def __init__(self, config: Dict):
        super().__init__("github", config)
        self.repos = config.get("repos", [])
        self.github_token = None  # 可选：设置GitHub Token以提高速率限制
    
    def fetch_workflow_list(self) -> List[Dict]:
        """获取所有仓库的工作流文件列表"""
        all_workflows = []
        
        for repo in self.repos:
            self.logger.info(f"Fetching workflows from {repo}")
            try:
                workflows = self._fetch_repo_workflows(repo)
                all_workflows.extend(workflows)
            except Exception as e:
                self.logger.error(f"Error fetching from {repo}: {e}")
        
        return all_workflows
    
    def _fetch_repo_workflows(self, repo: str) -> List[Dict]:
        """从单个仓库获取工作流"""
        api_url = f"https://api.github.com/repos/{repo}/contents"
        
        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            response = self.session.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            contents = response.json()
            
            workflows = []
            for item in contents:
                # 递归查找JSON文件
                if item["type"] == "file" and item["name"].endswith(".json"):
                    workflows.append({
                        "id": f"{repo.replace('/', '_')}_{item['name'][:-5]}",
                        "name": item["name"],
                        "download_url": item["download_url"],
                        "repo": repo,
                        "path": item["path"],
                    })
                elif item["type"] == "dir":
                    # 递归获取目录中的文件
                    sub_workflows = self._fetch_dir_workflows(
                        item["url"], repo, headers
                    )
                    workflows.extend(sub_workflows)
            
            return workflows
        
        except Exception as e:
            self.logger.error(f"Error fetching repo {repo}: {e}")
            return []
    
    def _fetch_dir_workflows(
        self, dir_url: str, repo: str, headers: Dict
    ) -> List[Dict]:
        """递归获取目录中的工作流文件"""
        try:
            response = self.session.get(dir_url, headers=headers, timeout=30)
            response.raise_for_status()
            contents = response.json()
            
            workflows = []
            for item in contents:
                if item["type"] == "file" and item["name"].endswith(".json"):
                    workflows.append({
                        "id": f"{repo.replace('/', '_')}_{item['path'].replace('/', '_')[:-5]}",
                        "name": item["name"],
                        "download_url": item["download_url"],
                        "repo": repo,
                        "path": item["path"],
                    })
                elif item["type"] == "dir":
                    sub_workflows = self._fetch_dir_workflows(
                        item["url"], repo, headers
                    )
                    workflows.extend(sub_workflows)
            
            return workflows
        
        except Exception as e:
            self.logger.error(f"Error fetching directory {dir_url}: {e}")
            return []
    
    def fetch_workflow_detail(self, workflow_id: str) -> Optional[Dict]:
        """下载工作流JSON文件"""
        # 从workflow_list中找到对应的workflow_info
        # 这里需要缓存workflow_list信息
        workflow_info = getattr(self, '_current_workflow_info', None)
        if not workflow_info:
            return None
        
        try:
            response = self.session.get(
                workflow_info["download_url"],
                timeout=30
            )
            response.raise_for_status()
            
            workflow_data = response.json()
            
            # 添加元数据
            workflow_data["_metadata"] = {
                "source": "github",
                "repo": workflow_info["repo"],
                "path": workflow_info["path"],
                "filename": workflow_info["name"],
            }
            
            return workflow_data
        
        except Exception as e:
            self.logger.error(f"Error downloading workflow {workflow_id}: {e}")
            return None
    
    def run(self, max_count: Optional[int] = None) -> Dict:
        """重写run方法以支持workflow_info传递"""
        self.logger.info(f"Starting GitHub crawler")
        
        try:
            workflows = self.fetch_workflow_list()
            self.stats["total"] = len(workflows)
            
            if max_count:
                workflows = workflows[:max_count]
            
            for workflow_info in workflows:
                try:
                    workflow_id = workflow_info["id"]
                    self.logger.info(f"Fetching workflow {workflow_id}")
                    
                    # 临时存储当前workflow_info供fetch_workflow_detail使用
                    self._current_workflow_info = workflow_info
                    
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
