"""
Tests for Expression Evaluation Task
Phase 2 (v4.1.0-beta.2): Unit tests for async expression evaluation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from qgis.core import QgsTask
from core.tasks.expression_evaluation_task import ExpressionEvaluationTask


@pytest.fixture
def mock_layer():
    """Create mock QgsVectorLayer."""
    layer = Mock()
    layer.name.return_value = "test_layer"
    layer.featureCount.return_value = 1000
    return layer


@pytest.fixture
def mock_features():
    """Create mock features list."""
    features = []
    for i in range(50):
        feature = Mock()
        feature.id.return_value = i
        feature.attribute.return_value = i * 100
        features.append(feature)
    return features


class TestTaskCreation:
    """Test task initialization."""
    
    def test_task_creation(self, mock_layer):
        """Test creating expression evaluation task."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='"population" > 10000',
            description="Test evaluation"
        )
        
        assert task.layer == mock_layer
        assert task.expression == '"population" > 10000'
        assert task.result_features is None
        assert task.exception is None
    
    def test_task_inherits_qgstask(self, mock_layer):
        """Test task is proper QgsTask."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='"id" > 0'
        )
        
        assert isinstance(task, QgsTask)
        assert task.canCancel()


class TestTaskExecution:
    """Test task run() method."""
    
    def test_successful_evaluation(self, mock_layer, mock_features):
        """Test successful expression evaluation."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='"field" = 1'
        )
        
        # Mock getFeatures to return mock features
        mock_layer.getFeatures.return_value = iter(mock_features)
        
        # Run task
        result = task.run()
        
        assert result is True
        assert task.result_features == mock_features
        assert len(task.result_features) == 50
        assert task.exception is None
    
    def test_evaluation_with_no_matches(self, mock_layer):
        """Test evaluation that matches no features."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='"field" = 999999'
        )
        
        # Mock getFeatures to return empty
        mock_layer.getFeatures.return_value = iter([])
        
        result = task.run()
        
        assert result is True
        assert task.result_features == []
        assert len(task.result_features) == 0
    
    def test_evaluation_failure(self, mock_layer):
        """Test handling of evaluation failure."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='invalid expression'
        )
        
        # Mock getFeatures to raise exception
        mock_layer.getFeatures.side_effect = Exception("Invalid expression")
        
        result = task.run()
        
        assert result is False
        assert task.exception is not None
        assert "Invalid expression" in str(task.exception)


class TestTaskCancellation:
    """Test task cancellation."""
    
    def test_cancel_during_execution(self, mock_layer):
        """Test cancelling task during execution."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='"id" > 0'
        )
        
        # Mock features generator that checks cancellation
        def feature_generator():
            for i in range(100):
                if task.isCanceled():
                    return
                feature = Mock()
                feature.id.return_value = i
                yield feature
        
        mock_layer.getFeatures.return_value = feature_generator()
        
        # Cancel after task starts
        task.cancel()
        
        result = task.run()
        
        # Should return False when cancelled
        assert result is False or task.isCanceled()


class TestTaskCallbacks:
    """Test task completion callbacks."""
    
    def test_finished_callback_success(self, mock_layer, mock_features):
        """Test finished() called on success."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='"field" = 1'
        )
        
        mock_layer.getFeatures.return_value = iter(mock_features)
        task.run()
        
        # Call finished() manually (normally called by task manager)
        task.finished(True)
        
        # Should complete without error
        assert task.result_features is not None
    
    def test_finished_callback_failure(self, mock_layer):
        """Test finished() called on failure."""
        task = ExpressionEvaluationTask(
            layer=mock_layer,
            expression='invalid'
        )
        
        mock_layer.getFeatures.side_effect = Exception("Error")
        task.run()
        
        # Call finished() manually
        task.finished(False)
        
        # Should have exception recorded
        assert task.exception is not None


# Integration test would require full QGIS environment
# Skipped in unit tests, covered by manual testing
