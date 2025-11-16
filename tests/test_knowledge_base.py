"""
Tests for Knowledge Base with RAG
"""

import pytest
from datetime import datetime
from core.knowledge_base import KnowledgeEntry, KnowledgeBase


@pytest.fixture
def knowledge_entry():
    """Create a sample knowledge entry"""
    return KnowledgeEntry(
        id="kb_001",
        incident_id="inc_001",
        incident_type="application_error",
        root_causes=["Database connection timeout", "High query latency"],
        symptoms=["500 errors in API", "Slow response times"],
        resolution_steps=[
            "Restart database connection pool",
            "Optimize slow queries",
            "Scale database instances"
        ],
        context={
            'execution_mode': 'adaptive',
            'confidence_scores': {'log_analyzer': 0.9}
        },
        timestamp=datetime.utcnow(),
        tenant_id="default"
    )


class TestKnowledgeEntry:
    """Test KnowledgeEntry dataclass"""

    def test_entry_creation(self, knowledge_entry):
        """Test creating a knowledge entry"""
        assert knowledge_entry.id == "kb_001"
        assert knowledge_entry.incident_id == "inc_001"
        assert knowledge_entry.incident_type == "application_error"
        assert len(knowledge_entry.root_causes) == 2
        assert len(knowledge_entry.symptoms) == 2
        assert len(knowledge_entry.resolution_steps) == 3

    def test_entry_to_text(self, knowledge_entry):
        """Test converting entry to searchable text"""
        text = knowledge_entry.to_text()

        assert "application_error" in text
        assert "Database connection timeout" in text
        assert "500 errors" in text
        assert "Restart database connection pool" in text


@pytest.mark.asyncio
class TestKnowledgeBase:
    """Test KnowledgeBase functionality"""

    @pytest.fixture
    async def kb(self):
        """Create knowledge base instance"""
        kb = KnowledgeBase(
            collection_name="test_rca_knowledge",
            persist_directory="./data/test_knowledge"
        )
        # Note: initialization will fail if chromadb is not installed
        # but that's OK for testing the interface
        return kb

    async def test_knowledge_base_creation(self, kb):
        """Test creating knowledge base"""
        assert kb.collection_name == "test_rca_knowledge"
        assert kb.persist_directory == "./data/test_knowledge"
        assert kb._initialized is False

    async def test_entry_to_text_format(self, knowledge_entry):
        """Test that entry text contains all key information"""
        text = knowledge_entry.to_text()

        # Check all major components are present
        assert "Incident Type:" in text
        assert "Symptoms:" in text
        assert "Root Causes:" in text
        assert "Resolution:" in text
        assert "Context:" in text

        # Check specific values
        assert "application_error" in text
        assert "Database connection timeout" in text


@pytest.mark.asyncio
class TestRAGEnhancedOrchestrator:
    """Test RAG-enhanced orchestrator"""

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock base orchestrator"""
        class MockOrchestrator:
            async def run_rca(self, incident_id, signals, **kwargs):
                class MockGraph:
                    def get_root_causes(self):
                        class MockCause:
                            title = "Mock root cause"
                        return [MockCause()]

                class MockContext:
                    def __init__(self, incident_id):
                        self.incident_id = incident_id
                        self.signals = signals
                        self.graph = MockGraph()
                        self.agent_results = {}
                        self.metadata = {}
                        self.config = type('obj', (object,), {
                            'execution_mode': 'adaptive'
                        })()

                return MockContext(incident_id)

        return MockOrchestrator()

    @pytest.fixture
    def mock_knowledge_base(self):
        """Mock knowledge base"""
        class MockKnowledgeBase:
            async def get_incident_recommendations(self, current_signals, tenant_id):
                return {
                    'recommendations': [
                        {
                            'root_cause': 'Database timeout',
                            'confidence': 0.85,
                            'supporting_incidents': 3
                        }
                    ],
                    'confidence': 0.85
                }

            async def add_rca_result(self, context, tenant_id):
                return "kb_123"

        return MockKnowledgeBase()

    async def test_rag_orchestrator_adds_recommendations(
        self, mock_orchestrator, mock_knowledge_base
    ):
        """Test that RAG orchestrator adds recommendations to context"""
        from core.knowledge_base import RAGEnhancedOrchestrator

        rag_orch = RAGEnhancedOrchestrator(mock_orchestrator, mock_knowledge_base)

        # Create mock signals
        class MockSignal:
            title = "High error rate"

        signals = [MockSignal()]

        context = await rag_orch.run_rca("inc_001", signals)

        # Check recommendations were added
        assert 'kb_recommendations' in context.metadata
        assert 'kb_enhanced' in context.metadata
        assert context.metadata['kb_enhanced'] is True


class TestKnowledgeBaseIntegration:
    """Integration tests for knowledge base (require dependencies)"""

    @pytest.mark.skip(reason="Requires chromadb installation")
    @pytest.mark.asyncio
    async def test_add_and_search_incidents(self):
        """Test adding and searching for similar incidents"""
        kb = KnowledgeBase(
            collection_name="test_integration",
            persist_directory="./data/test_int_kb"
        )

        # Initialize
        initialized = await kb.initialize()
        if not initialized:
            pytest.skip("Knowledge base dependencies not available")

        # Add test entry
        entry = KnowledgeEntry(
            id="test_001",
            incident_id="inc_test",
            incident_type="performance_degradation",
            root_causes=["High CPU usage"],
            symptoms=["Slow API responses"],
            resolution_steps=["Scale instances"],
            context={},
            timestamp=datetime.utcnow(),
            tenant_id="default"
        )

        # Store in KB (would need mock RCA context)
        # Similar = await kb.find_similar_incidents("Slow API", "default")

        # Clean up
        # Would delete test collection here

    @pytest.mark.skip(reason="Requires chromadb installation")
    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test getting knowledge base statistics"""
        kb = KnowledgeBase()
        initialized = await kb.initialize()

        if not initialized:
            pytest.skip("Knowledge base dependencies not available")

        stats = await kb.get_statistics()

        assert 'total_entries' in stats
        assert 'collection_name' in stats
