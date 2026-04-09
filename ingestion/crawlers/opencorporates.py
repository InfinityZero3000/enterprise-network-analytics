from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult
from datetime import datetime, timezone
class OpenCorporatesCrawler(BaseCrawler):
    SOURCE_NAME = "opencorporates"
    async def crawl(self, **kwargs):
        res = CrawlResult(source=self.SOURCE_NAME)
        res.companies.append({"company_id": "oc_sg_12345", "name": "Mock FPT", "tax_code": "123", "company_type": "llc", "status": "active", "country": "SG"})
        res.raw_count = 1
        return res
