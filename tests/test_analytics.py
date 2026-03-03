"""Unit tests for fraud detection and risk scoring."""
import pytest
from unittest.mock import MagicMock, patch
from analytics.fraud_detection.rule_based import AlertLevel, FraudAlert


class TestRuleBasedFraudDetector:

    def _mock_session(self, mock_session_ctx, return_values: dict):
        """return_values maps query substring → list of mock records."""
        mock_session = MagicMock()

        def side_effect(query, **kwargs):
            for key, records in return_values.items():
                if key in query:
                    return records
            return []

        mock_session.run.side_effect = side_effect
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        return mock_session

    @patch("analytics.fraud_detection.rule_based.Neo4jConnection.session")
    def test_no_alerts_when_empty(self, mock_session_ctx):
        from analytics.fraud_detection.rule_based import RuleBasedFraudDetector
        self._mock_session(mock_session_ctx, {"shell": [], "circular": [], "pep": [], "anction": []})
        detector = RuleBasedFraudDetector()
        alerts = detector.run_all_rules()
        assert isinstance(alerts, list)

    def test_fraud_alert_dataclass():
        alert = FraudAlert(
            entity_id="C001",
            entity_name="Test Co",
            entity_type="Company",
            alert_type="shell_company",
            level=AlertLevel.HIGH,
            score=0.75,
            description="Test alert",
            evidence={"key": "value"},
        )
        assert alert.level == AlertLevel.HIGH
        assert alert.score == 0.75
        assert alert.evidence["key"] == "value"

    def test_alert_levels():
        levels = [AlertLevel.LOW, AlertLevel.MEDIUM, AlertLevel.HIGH, AlertLevel.CRITICAL]
        assert len(levels) == 4
        assert AlertLevel.CRITICAL.value == "critical"


class TestRiskScoringEngine:

    @patch("analytics.risk.risk_scoring.Neo4jConnection.session")
    def test_score_company_returns_none_for_unknown(self, mock_session_ctx):
        from analytics.risk.risk_scoring import RiskScoringEngine
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = None
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        engine = RiskScoringEngine()
        result = engine.score_company("NONEXISTENT_ID")
        assert result is None

    def test_risk_level_thresholds():
        from analytics.risk.risk_scoring import _risk_level
        assert _risk_level(10) == "low"
        assert _risk_level(30) == "medium"
        assert _risk_level(60) == "high"
        assert _risk_level(80) == "critical"

    def test_weight_sum():
        from analytics.risk.risk_scoring import WEIGHTS
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights must sum to 1.0, got {total}"


class TestOwnershipAnalyzer:

    @patch("analytics.ownership.cross_ownership.Neo4jConnection.session")
    def test_detect_cross_ownership_empty(self, mock_session_ctx):
        from analytics.ownership.cross_ownership import OwnershipAnalyzer
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        analyzer = OwnershipAnalyzer()
        result = analyzer.detect_cross_ownership()
        assert result == []

    @patch("analytics.ownership.cross_ownership.Neo4jConnection.session")
    def test_get_ownership_tree_structure(self, mock_session_ctx):
        from analytics.ownership.cross_ownership import OwnershipAnalyzer
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_session_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_ctx.return_value.__exit__ = MagicMock(return_value=False)
        analyzer = OwnershipAnalyzer()
        tree = analyzer.get_ownership_tree("C001")
        assert "company_id" in tree
        assert "nodes" in tree
        assert "edges" in tree
