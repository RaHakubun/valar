"""
Web平台爬虫（OpenArt, ComfyWorkflows, Civitai等）
注意：这些平台需要实际调研其API或网页结构
"""

import json
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

from .base_crawler import BaseCrawler


class OpenArtCrawler(BaseCrawler):
    """OpenArt.ai爬虫"""
    
    def __init__(self, config: Dict):
        super().__init__("openart", config)
        self.base_url = config["base_url"]
    
    def fetch_workflow_list(self) -> List[Dict]:
        """
        获取OpenArt工作流列表
        注意：这需要根据实际网站结构调整
        可能需要：
        1. 分析网页API调用
        2. 使用Selenium处理动态加载
        3. 处理分页
        """
        workflows = []
        
        # TODO: 实际实现需要分析OpenArt的API
        # 示例结构（需要实际调研）:
        # api_url = f"{self.base_url}/api/workflows?page=1&limit=100"
        
        self.logger.warning("OpenArt crawler needs actual API analysis to implement")
        return workflows
    
    def fetch_workflow_detail(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        # TODO: 实现详情获取
        self.logger.warning(f"OpenArt detail fetch not implemented for {workflow_id}")
        return None


class ComfyWorkflowsCrawler(BaseCrawler):
    """ComfyWorkflows.com爬虫"""
    
    def __init__(self, config: Dict):
        super().__init__("comfyworkflows", config)
        self.base_url = config["base_url"]
    
    def fetch_workflow_list(self) -> List[Dict]:
        """获取ComfyWorkflows列表"""
        workflows = []
        
        # TODO: 分析ComfyWorkflows.com的实际API或网页结构
        self.logger.warning("ComfyWorkflows crawler needs actual API analysis")
        return workflows
    
    def fetch_workflow_detail(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        self.logger.warning(f"ComfyWorkflows detail fetch not implemented for {workflow_id}")
        return None


class CivitaiCrawler(BaseCrawler):
    """Civitai爬虫"""
    
    def __init__(self, config: Dict):
        super().__init__("civitai", config)
        self.base_url = config["base_url"]
        self.api_endpoint = config.get("api_endpoint", "/api/v1/images")
    
    def fetch_workflow_list(self) -> List[Dict]:
        """
        获取Civitai图片列表（包含ComfyUI工作流）
        Civitai的API文档: https://github.com/civitai/civitai/wiki/REST-API-Reference
        """
        workflows = []
        page = 1
        
        try:
            while True:
                api_url = f"{self.base_url}{self.api_endpoint}"
                params = {
                    "page": page,
                    "limit": 100,
                    "nsfw": "false",  # 过滤NSFW内容
                }
                
                response = self.session.get(api_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                items = data.get("items", [])
                if not items:
                    break
                
                for item in items:
                    # 检查是否包含ComfyUI工作流
                    meta = item.get("meta", {})
                    if "workflow" in meta or "comfy" in meta:
                        workflows.append({
                            "id": str(item.get("id")),
                            "url": item.get("url"),
                            "meta": meta,
                        })
                
                page += 1
                self.rate_limit_wait()
                
                # 限制最大页数
                if page > 10:  # 可配置
                    break
        
        except Exception as e:
            self.logger.error(f"Error fetching Civitai workflows: {e}")
        
        return workflows
    
    def fetch_workflow_detail(self, workflow_id: str) -> Optional[Dict]:
        """从图片元数据中提取工作流"""
        workflow_info = getattr(self, '_current_workflow_info', None)
        if not workflow_info:
            return None
        
        try:
            meta = workflow_info.get("meta", {})
            
            # Civitai通常在meta中存储workflow
            if "workflow" in meta:
                workflow_data = meta["workflow"]
                if isinstance(workflow_data, str):
                    workflow_data = json.loads(workflow_data)
                
                # 添加元数据
                workflow_data["_metadata"] = {
                    "source": "civitai",
                    "image_id": workflow_id,
                    "url": workflow_info.get("url"),
                }
                
                return workflow_data
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error extracting workflow {workflow_id}: {e}")
            return None
    
    def run(self, max_count: Optional[int] = None) -> Dict:
        """重写run方法"""
        self.logger.info(f"Starting Civitai crawler")
        
        try:
            workflows = self.fetch_workflow_list()
            self.stats["total"] = len(workflows)
            
            if max_count:
                workflows = workflows[:max_count]
            
            for workflow_info in workflows:
                try:
                    workflow_id = workflow_info["id"]
                    self.logger.info(f"Processing workflow {workflow_id}")
                    
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
