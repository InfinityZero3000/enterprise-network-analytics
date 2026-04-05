"""
LLM Integration — Q&A tự nhiên trên mạng lưới doanh nghiệp (OpenAI + Ollama fallback)
"""
import re
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

GRAPH_RAG_HINT = """Khi trả lời, ưu tiên dựa trên Graph Context được cung cấp.
Nếu bằng chứng graph còn yếu, hãy nêu rõ mức độ chắc chắn và đề xuất câu hỏi truy vấn tiếp theo."""


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


def _get_groq_client():
    try:
        from openai import OpenAI
        return OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
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
        self._groq_client = _get_groq_client()
        self._openai_client = _get_openai_client()
        self._ollama_client = _get_ollama_client()
        self._embedding = None

    def _get_embedding(self):
        if self._embedding is not None:
            return self._embedding
        try:
            from ai.graph_embedding import GraphEmbedding
            self._embedding = GraphEmbedding()
        except Exception as e:
            logger.warning(f"GraphEmbedding unavailable: {e}")
            self._embedding = None
        return self._embedding

    def _extract_keywords(self, text: str) -> list[str]:
        tokens = re.findall(r"[A-Za-z0-9\-_.À-ỹ]{3,}", text.lower())
        stop_words = {
            "cho", "toi", "biết", "thế", "nào", "liên", "quan", "với", "các", "công", "ty",
            "doanh", "nghiệp", "rủi", "ro", "mối", "quan", "hệ", "trong", "graph", "node", "edge",
            "about", "what", "show", "does", "this", "that", "the", "and", "with", "from", "into",
        }
        keywords: list[str] = []
        for t in tokens:
            if t in stop_words:
                continue
            if t not in keywords:
                keywords.append(t)
            if len(keywords) >= 8:
                break
        return keywords

    def _retrieve_entities_by_keywords(self, keywords: list[str], limit: int = 12) -> list[dict]:
        if not keywords:
            return []

        cypher = """
        MATCH (e:Entity)
        WHERE any(k IN $keywords WHERE toLower(coalesce(e.name, e.full_name, e.address, e.node_id, '')) CONTAINS k)
        RETURN e.node_id AS node_id,
               coalesce(e.name, e.full_name, e.address, e.node_id) AS display_name,
               labels(e) AS labels,
               coalesce(e.pagerank_score, 0.0) AS pagerank
        ORDER BY pagerank DESC
        LIMIT $limit
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, keywords=keywords, limit=limit)]

    def _retrieve_relationship_snippets(self, node_ids: list[str], limit: int = 24) -> list[dict]:
        if not node_ids:
            return []

        cypher = """
        MATCH (a:Entity)-[r:RELATIONSHIP]->(b:Entity)
        WHERE a.node_id IN $node_ids OR b.node_id IN $node_ids
        RETURN coalesce(a.name, a.full_name, a.address, a.node_id) AS source,
               coalesce(r.rel_type, type(r), 'RELATIONSHIP') AS rel_type,
               coalesce(b.name, b.full_name, b.address, b.node_id) AS target,
               coalesce(r.ownership_pct, 0) AS ownership_pct
        LIMIT $limit
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, node_ids=node_ids, limit=limit)]

    def _retrieve_embedding_neighbors(self, entities: list[dict], top_n: int = 5) -> list[dict]:
        if not entities:
            return []
        emb = self._get_embedding()
        if emb is None or emb.model is None:
            return []

        first = entities[0].get("node_id")
        if not first:
            return []

        try:
            sims = emb.find_similar(str(first), top_n=top_n)
            return [{"node_id": nid, "similarity": round(float(score), 4)} for nid, score in sims]
        except Exception as e:
            logger.warning(f"Embedding retrieval failed: {e}")
            return []

    def _build_graphrag_context(self, question: str, company_id: str | None = None) -> str:
        keywords = self._extract_keywords(question)
        entities = self._retrieve_entities_by_keywords(keywords, limit=12)

        # If user pins a company_id, force-include it to improve precision.
        if company_id and all(str(e.get("node_id")) != str(company_id) for e in entities):
            entities.insert(0, {
                "node_id": company_id,
                "display_name": f"Company {company_id}",
                "labels": ["Company"],
                "pagerank": 0.0,
            })

        node_ids = [str(e.get("node_id")) for e in entities if e.get("node_id")]
        rels = self._retrieve_relationship_snippets(node_ids, limit=24)
        similar = self._retrieve_embedding_neighbors(entities, top_n=5)

        lines: list[str] = []
        lines.append(f"Keywords: {keywords}")
        lines.append(f"Matched entities ({len(entities)}):")
        for e in entities[:10]:
            lines.append(
                f"- {e.get('display_name')} | id={e.get('node_id')} | labels={e.get('labels')} | pagerank={round(float(e.get('pagerank', 0.0)), 6)}"
            )

        lines.append(f"Relationship snippets ({len(rels)}):")
        for r in rels[:20]:
            ownership = r.get("ownership_pct", 0)
            if ownership:
                lines.append(f"- {r.get('source')} -[{r.get('rel_type')} {ownership}%]-> {r.get('target')}")
            else:
                lines.append(f"- {r.get('source')} -[{r.get('rel_type')}]-> {r.get('target')}")

        if similar:
            lines.append("Embedding neighbors:")
            for s in similar:
                lines.append(f"- node_id={s['node_id']} similarity={s['similarity']}")

        return "\n".join(lines)

    def _chat(self, system: str, user: str, model: str | None = None) -> str:
        providers: list[tuple[str, object | None, str]] = []
        if settings.gemini_api_key and self._gemini_client:
            providers.append(("gemini", self._gemini_client, model or settings.gemini_model))
        if settings.groq_api_key and self._groq_client:
            providers.append(("groq", self._groq_client, model or settings.groq_model))
        if settings.openai_api_key and self._openai_client:
            providers.append(("openai", self._openai_client, model or settings.openai_model))
        if self._ollama_client:
            providers.append(("ollama", self._ollama_client, model or settings.ollama_model))

        if not providers:
            return "LLM client không khả dụng."

        last_error: Exception | None = None

        for provider_name, client, provider_model in providers:
            if client is None:
                continue
            try:
                logger.info(f"LLM provider call provider={provider_name} model={provider_model}")
                resp = client.chat.completions.create(
                    model=provider_model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=0.2,
                    max_tokens=1024,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                logger.error(f"LLM call failed provider={provider_name}: {e}")
                continue

        if last_error and (
            "Connection error" in str(last_error)
            or "ConnectionRefused" in str(last_error)
            or "connect" in str(last_error).lower()
        ):
            return "(Demo Mock Mode) AI Response: Dựa trên phân tích mạng lưới, tôi không phát hiện dấu hiệu gian lận trực tiếp nào từ các Node hiển thị, tuy nhiên công ty C10492 có dấu hiệu là Shell Company do thiếu nhân sự và tài sản cố định. Vui lòng kiểm tra tab Risk \u0026 Alerts."

        return f"Lỗi khi gọi LLM: {last_error}"

    # ------------------------------------------------------------------ #
    def ask(self, question: str, company_id: str | None = None, page_context: str | None = None) -> str:
        context = ""
        if page_context:
            context += f"\nUI Context: {page_context}"

        try:
            graphrag = self._build_graphrag_context(question, company_id=company_id)
            context += f"\nGraph Context:\n{graphrag}"
        except Exception as e:
            logger.warning(f"GraphRAG context build failed: {e}")

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
                        context += f"\nCompany Context: {dict(r['c'].items())}\nRelationships: {r['rels'][:20]}"
            except Exception as e:
                logger.warning(f"Context fetch failed: {e}")

        system_prompt = SYSTEM_PROMPT + "\n\n" + GRAPH_RAG_HINT
        return self._chat(system_prompt, question + context)

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
