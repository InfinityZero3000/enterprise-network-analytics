"""Unit tests for graph queries and algorithms."""
import pytest
from unittest.mock import MagicMock, patch


class TestGraphQueries:

    def _make_session(self, return_value):
        mock_session = MagicMock()
        mock_session.run.return_value = return_value
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_session)
        mock_cm.__exit__ = MagicMock(return_value=False)
        return mock_session, mock_cm

    @patch("graph.graph_queries.Neo4jConnection.session")
    def test_get_company_network_stats(self, mock_session_ctx):
        from graph.graph_queries import GraphQueries
        mock_session = MagicMock()
        record = MagicMock()
        record.__getitem__ = lambda s, k: {"company_id": "C001", "name": "Test Co",
                                            "degree": 5, "shareholder_count": 2,
                                            "investee_count": 3, "board_member_count": 2,
                                            "supplier_count": 0, "community_id": 1,
                                            "pagerank": 0.123, "betweenness": 0.05}[k]
        mock_session.run.return_value.single.return_value = record
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        gq = GraphQueries()
        result = gq.get_company_network_stats("C001")
        assert result is not None
        mock_session.run.assert_called_once()

    @patch("graph.graph_queries.Neo4jConnection.session")
    def test_detect_circular_ownership_no_cycle(self, mock_session_ctx):
        from graph.graph_queries import GraphQueries
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        gq = GraphQueries()
        result = gq.detect_circular_ownership("C001")
        assert result == []

    @patch("graph.graph_queries.Neo4jConnection.session")
    def test_find_common_shareholders(self, mock_session_ctx):
        from graph.graph_queries import GraphQueries
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        gq = GraphQueries()
        result = gq.find_common_shareholders(["C001", "C002"])
        assert isinstance(result, list)


class TestGraphAlgorithms:

    @patch("graph.algorithms.graph_algorithms.Neo4jConnection.session")
    def test_project_graph(self, mock_session_ctx):
        from graph.algorithms.graph_algorithms import GraphAlgorithms
        mock_session = MagicMock()
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        algo = GraphAlgorithms()
        algo.project_graph("test-graph", ["Company"], ["RELATIONSHIP"])
        mock_session.run.assert_called()

    @patch("graph.algorithms.graph_algorithms.Neo4jConnection.session")
    def test_get_top_connected_entities_returns_list(self, mock_session_ctx):
        from graph.algorithms.graph_algorithms import GraphAlgorithms
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        algo = GraphAlgorithms()
        result = algo.get_top_connected_entities()
        assert isinstance(result, list)
