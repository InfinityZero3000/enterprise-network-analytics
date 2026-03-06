"""
Crawler package — thu thập dữ liệu doanh nghiệp từ nhiều nguồn công khai.

Supported sources
─────────────────
╔══════════════════════╦═══════════════════════════════════════════════╦═══════════════╗
║ Source               ║ URL                                           ║ License       ║
╠══════════════════════╬═══════════════════════════════════════════════╬═══════════════╣
║ OpenCorporates       ║ https://api.opencorporates.com/v0.4           ║ CC BY 4.0     ║
║ OpenSanctions        ║ https://api.opensanctions.org                 ║ CC BY NC 4.0  ║
║ GLEIF (LEI)          ║ https://api.gleif.org/api/v1                  ║ CC0 1.0       ║
║ OpenOwnership (BODS) ║ https://api.openownership.org                 ║ CC BY 4.0     ║
║ World Bank           ║ https://api.worldbank.org/v2                  ║ CC BY 4.0     ║
║ Vietnam NBR (DKKD)   ║ https://dangkykinhdoanh.gov.vn                ║ Public        ║
╚══════════════════════╩═══════════════════════════════════════════════╩═══════════════╝
"""
from ingestion.crawlers.opencorporates import OpenCorporatesCrawler
from ingestion.crawlers.opensanctions import OpenSanctionsCrawler
from ingestion.crawlers.gleif import GleifCrawler
from ingestion.crawlers.openownership import OpenOwnershipCrawler
from ingestion.crawlers.worldbank import WorldBankCrawler
from ingestion.crawlers.vietnam_nbr import VietnamNBRCrawler

__all__ = [
    "OpenCorporatesCrawler",
    "OpenSanctionsCrawler",
    "GleifCrawler",
    "OpenOwnershipCrawler",
    "WorldBankCrawler",
    "VietnamNBRCrawler",
]
