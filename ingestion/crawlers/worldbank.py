from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult
from datetime import datetime, timezone
class WorldBankCrawler(BaseCrawler):
    SOURCE_NAME = "worldbank"
    async def crawl(self, **kwargs):
        res = CrawlResult(source=self.SOURCE_NAME)
        res.companies.append({"company_id": "wb_vn", "name": "Mock WB", "tax_code": "", "company_type": "macro", "status": "active", "country": "VN"})
        res.raw_count = 1
        return res
