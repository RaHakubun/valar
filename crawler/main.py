"""
爬虫主程序
"""

import argparse
import logging
from typing import List

from .config import DATA_SOURCES
from .github_crawler import GitHubCrawler
from .web_crawler import OpenArtCrawler, ComfyWorkflowsCrawler, CivitaiCrawler


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CrawlerMain")


CRAWLER_MAP = {
    "github": GitHubCrawler,
    "openart": OpenArtCrawler,
    "comfyworkflows": ComfyWorkflowsCrawler,
    "civitai": CivitaiCrawler,
}


def run_crawler(source_name: str, max_count: int = None):
    """运行指定数据源的爬虫"""
    if source_name not in DATA_SOURCES:
        logger.error(f"Unknown data source: {source_name}")
        return
    
    config = DATA_SOURCES[source_name]
    if not config.get("enabled", False):
        logger.warning(f"Data source {source_name} is disabled")
        return
    
    crawler_class = CRAWLER_MAP.get(source_name)
    if not crawler_class:
        logger.error(f"No crawler implementation for {source_name}")
        return
    
    logger.info(f"Starting crawler for {source_name}")
    crawler = crawler_class(config)
    stats = crawler.run(max_count=max_count)
    
    logger.info(f"Crawler {source_name} finished with stats: {stats}")
    return stats


def run_all_crawlers(max_count: int = None):
    """运行所有启用的爬虫"""
    all_stats = {}
    
    for source_name in DATA_SOURCES:
        if DATA_SOURCES[source_name].get("enabled", False):
            try:
                stats = run_crawler(source_name, max_count)
                all_stats[source_name] = stats
            except Exception as e:
                logger.error(f"Error running crawler {source_name}: {e}")
    
    return all_stats


def main():
    parser = argparse.ArgumentParser(description="ComfyUI工作流数据爬虫")
    parser.add_argument(
        "--source",
        type=str,
        choices=list(DATA_SOURCES.keys()) + ["all"],
        default="all",
        help="数据源选择"
    )
    parser.add_argument(
        "--max-count",
        type=int,
        default=None,
        help="最大爬取数量（用于测试）"
    )
    
    args = parser.parse_args()
    
    if args.source == "all":
        logger.info("Running all crawlers")
        stats = run_all_crawlers(max_count=args.max_count)
    else:
        logger.info(f"Running crawler for {args.source}")
        stats = run_crawler(args.source, max_count=args.max_count)
    
    logger.info("=" * 80)
    logger.info("Crawling completed!")
    logger.info(f"Final stats: {stats}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
