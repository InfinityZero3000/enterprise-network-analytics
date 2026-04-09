from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult
from datetime import datetime, timezone
class OpenSanctionsCrawler(BaseCrawler):
    SOURCE_NAME = "opensanctions"
    async def crawl(self, **kwargs):
        res = CrawlResult(source=self.SOURCE_NAME)
        res.companies.append({"company_id": "os_123", "name": "Mock PEP", "tax_code": "", "company_type": "pep", "status": "active", "country": "VN"})
        res.raw_count = 1
        return res
