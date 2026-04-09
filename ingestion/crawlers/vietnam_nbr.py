from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult
from datetime import datetime, timezone
class VietnamNBRCrawler(BaseCrawler):
    SOURCE_NAME = "vietnam_nbr"
    async def crawl(self, **kwargs):
        res = CrawlResult(source=self.SOURCE_NAME)
        res.companies.append({"company_id": "vn_fpt", "name": "VN Mock", "tax_code": "vnn", "company_type": "llc", "status": "active", "country": "VN"})
        res.raw_count = 1
        return res
