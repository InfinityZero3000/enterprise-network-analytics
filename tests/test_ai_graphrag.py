"""Unit tests for GraphRAG-enhanced AI chat integration."""
from unittest.mock import patch

from ai.llm_integration import EnterpriseNetworkLLM, GRAPH_RAG_HINT, SYSTEM_PROMPT
from api.routes.ai_api import AskRequest, ask


class TestGraphRAGIntegration:

    def test_extract_keywords_dedup_and_limit(self):
        llm = EnterpriseNetworkLLM()
        question = (
            "Cho toi biet moi quan he rui ro giua Portcullis Portcullis "
            "va Bora Bora Financial trong graph node edge relation"
        )

        keywords = llm._extract_keywords(question)

        assert len(keywords) <= 8
        assert "portcullis" in keywords
        assert "bora" in keywords
        assert keywords.count("portcullis") == 1

    @patch.object(EnterpriseNetworkLLM, "_retrieve_embedding_neighbors")
    @patch.object(EnterpriseNetworkLLM, "_retrieve_relationship_snippets")
    @patch.object(EnterpriseNetworkLLM, "_retrieve_entities_by_keywords")
    def test_build_graphrag_context_contains_entities_and_rels(
        self,
        mock_entities,
        mock_rels,
        mock_neighbors,
    ):
        llm = EnterpriseNetworkLLM()

        mock_entities.return_value = [
            {
                "node_id": "236724",
                "display_name": "Portcullis TrustNet Chambers",
                "labels": ["Address", "Entity"],
                "pagerank": 0.0123,
            },
            {
                "node_id": "132324",
                "display_name": "Bora Bora Financial Ltd",
                "labels": ["Company", "Entity"],
                "pagerank": 0.0221,
            },
        ]
        mock_rels.return_value = [
            {
                "source": "Portcullis TrustNet Chambers",
                "rel_type": "RELATIONSHIP",
                "target": "Bora Bora Financial Ltd",
                "ownership_pct": 0,
            }
        ]
        mock_neighbors.return_value = [{"node_id": "81027146", "similarity": 0.7712}]

        context = llm._build_graphrag_context(
            "Cho toi biet moi quan he rui ro lien quan Portcullis va Bora Bora Financial"
        )

        assert "Matched entities (2):" in context
        assert "Portcullis TrustNet Chambers" in context
        assert "Relationship snippets (1):" in context
        assert "Embedding neighbors:" in context
        assert "similarity=0.7712" in context

    @patch.object(EnterpriseNetworkLLM, "_chat", return_value="ok")
    @patch.object(EnterpriseNetworkLLM, "_build_graphrag_context", return_value="GraphRAG block")
    def test_ask_includes_ui_and_graphrag_context(self, mock_graphrag, mock_chat):
        llm = EnterpriseNetworkLLM()

        answer = llm.ask("Explain this graph", page_context="Dashboard snapshot")

        assert answer == "ok"
        mock_graphrag.assert_called_once_with("Explain this graph", company_id=None)
        mock_chat.assert_called_once()

        called_system, called_user = mock_chat.call_args[0]
        assert SYSTEM_PROMPT in called_system
        assert GRAPH_RAG_HINT in called_system
        assert "UI Context: Dashboard snapshot" in called_user
        assert "Graph Context:\nGraphRAG block" in called_user


class TestAiApiAskRoute:

    @patch("api.routes.ai_api._llm")
    def test_ask_route_passes_page_context(self, mock_llm):
        mock_llm.ask.return_value = "route-ok"

        req = AskRequest(
            question="What does this graph mean?",
            company_id="C001",
            page_context="Graph view snapshot",
        )
        resp = ask(req)

        mock_llm.ask.assert_called_once_with(
            "What does this graph mean?",
            company_id="C001",
            page_context="Graph view snapshot",
        )
        assert resp["answer"] == "route-ok"
