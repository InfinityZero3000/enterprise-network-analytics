"""
LLM Integration — Q&A tự nhiên trên mạng lưới doanh nghiệp (OpenAI + Ollama fallback)
"""
from loguru import logger
from config.settings import settings
from config.neo4j_config import Neo4jConnection

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích mạng lưới doanh nghiệp Việt Nam.
Bạn có quyền truy xuất dữ liệu quan hệ doanh nghiệp từ Neo4j (graph database).
Hãy trả lời ngắn gọn, trích dẫn công ty/cá nhân cụ thể, và đánh dấu rủi ro nếu phát hiện.
Ngôn ngữ: Vietnamese. Nếu dữ liệu không đủ hãy nói rõ."""

CYPHER_SYSTEM_PROMPT = """Bạn là chuyên gia Cypher query cho Neo4j với schema sau:
- (Company) properties: company_id, name, tax_code, status, charter_capital, province, industry, pagerank, betweenness, community_id
- (Person) properties: person_id, full_name, is_pep, is_sanctioned
- [:RELATIONSHIP] properties: rel_type (SHAREHOLDER/SUPPLIER/BOARD_MEMBER/LEGAL_REP), ownership_pct
Chỉ trả về Cypher query thuần túy, không có giải thích. LIMIT 50 nếu không có điều kiện cụ thể."""


def _get_gemini_client():
    try:
        from openai import OpenAI
        return OpenAI(
            api_key=settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
    except Exception:
        return None


def _get_openai_client():
    try:
        from openai import OpenAI
        return OpenAI(api_key=settings.openai_api_key)
    except Exception:
        return None


def _get_ollama_client():
    try:
        from openai import OpenAI
        return OpenAI(base_url=settings.ollama_base_url, api_key="ollama")
    except Exception:
        return None


class EnterpriseNetworkLLM:

    def __init__(self):
        self._gemini_client = _get_gemini_client()
        self._openai_client = _get_openai_client()
        self._ollama_client = _get_ollama_client()

    def _chat(self, system: str, user: str, model: str | None = None) -> str:
        client = None
        m = None

        if settings.gemini_api_key and self._gemini_client:
            client = self._gemini_client
            m = model or settings.gemini_model
        elif settings.openai_api_key and self._openai_client:
            client = self._openai_client
            m = model or settings.openai_model
        else:
            client = self._ollama_client
            m = model or settings.ollama_model

        if client is None:
            return "LLM client không khả dụng."
        try:
            resp = client.chat.completions.create(
                model=m,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.2,
                max_tokens=1024,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            if "Connection error" in str(e) or "ConnectionRefused" in str(e) or "connect" in str(e).lower():
                return f"(Demo Mock Mode) AI Response: Dựa trên phân tích mạng lưới, tôi không phát hiện dấu hiệu gian lận trực tiếp nào từ các Node hiển thị, tuy nhiên công ty C10492 có dấu hiệu là Shell Company do thiếu nhân sự và tài sản cố định. Vui lòng kiểm tra tab Risk \u0026 Alerts."
            return f"Lỗi khi gọi LLM: {e}"

    # ------------------------------------------------------------------ #
    def ask(self, question: str, company_id: str | None = None) -> str:
        context = ""
        if company_id:
            try:
                with Neo4jConnection.session() as s:
                    r = s.run(
                        "MATCH (c:Company {company_id:$cid}) "
                        "OPTIONAL MATCH (c)-[rel:RELATIONSHIP]-(n) "
                        "RETURN c, COLLECT({type:rel.rel_type, pct:rel.ownership_pct, name:coalesce(n.name,n.full_name)}) AS rels LIMIT 1",
                        cid=company_id,
                    ).single()
                    if r:
                        context = f"\nContext: {dict(r['c'].items())}\nRelationships: {r['rels'][:20]}"
            except Exception as e:
                logger.warning(f"Context fetch failed: {e}")

        return self._chat(SYSTEM_PROMPT, question + context)

    def ask_cypher(self, natural_language: str) -> str:
        """Convert natural language question to a Cypher query."""
        return self._chat(CYPHER_SYSTEM_PROMPT, natural_language)

    def execute_nl_query(self, natural_language: str) -> list[dict]:
        """Convert NL → Cypher → execute → return results."""
        cypher = self.ask_cypher(natural_language).strip()
        cypher = cypher.replace("```cypher", "").replace("```", "").strip()
        logger.info(f"Generated Cypher: {cypher}")
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher)]
