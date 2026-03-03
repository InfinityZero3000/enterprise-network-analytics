"""Companies API routes."""
from fastapi import APIRouter, HTTPException, Query
from graph.graph_queries import GraphQueries

router = APIRouter()
_queries = GraphQueries()


@router.get("/{company_id}/stats")
def get_company_stats(company_id: str):
    """Thống kê mạng lưới của một doanh nghiệp."""
    result = _queries.get_company_network_stats(company_id)
    if not result:
        raise HTTPException(404, f"Company not found: {company_id}")
    return result


@router.get("/{company_id}/ownership-chain")
def get_ownership_chain(
    company_id: str,
    depth: int = Query(default=4, ge=1, le=8),
):
    """Chuỗi sở hữu tới {depth} cấp."""
    return _queries.get_ownership_chain(company_id, depth)


@router.post("/common-shareholders")
def find_common_shareholders(company_ids: list[str]):
    """Tìm cổ đông chung giữa danh sách công ty."""
    if len(company_ids) < 2:
        raise HTTPException(400, "Need at least 2 company IDs.")
    return _queries.find_common_shareholders(company_ids)


@router.get("/{company_id}/circular-ownership")
def check_circular(company_id: str):
    """Kiểm tra sở hữu vòng tròn cho công ty."""
    return _queries.detect_circular_ownership(company_id)
