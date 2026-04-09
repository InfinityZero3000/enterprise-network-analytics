from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult
from datetime import datetime, timezone
class OpenOwnershipCrawler(BaseCrawler):
    SOURCE_NAME = "openownership"
    async def crawl(self, **kwargs):
        res = CrawlResult(source=self.SOURCE_NAME)
        res.companies.append({"company_id": "oo_b8db1a", "name": "OO Mock", "tax_code": "000", "company_type": "llc", "status": "active", "country": "GB"})
        res.raw_count = 1
        return res
