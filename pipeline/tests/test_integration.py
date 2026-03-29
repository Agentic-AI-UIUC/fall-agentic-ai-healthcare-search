import pytest
from pipeline.generator import OllamaGenerator

'''
    Integration tests - OLLAMA MUST BE RUNNING!
'''
class TestOllamaIntegration:
    @pytest.fixture
    def generator(self):
        return OllamaGenerator()

    def test_health_check(self, generator):
        is_healthy = generator.check_health()
        
        if not is_healthy:
            pytest.skip("ollama not running - skipping integration test")
        
        assert is_healthy is True

    # test ollama can generate a response
    def test_generate_response(self, generator):
        if not generator.check_health():
            pytest.skip("ollama not running - skipping integration test")

        mock_docs = [
            {
                "title": "Test Document",
                "source": "PDF",
                "url": None,
                "text": "Hypertension is defined as blood pressure above 140/90 mmHg."
            }
        ]

        response = generator.generate(
            query="What is hypertension?",
            retrieved_docs=mock_docs
        )

        assert len(response) > 0, "Empty response from Ollama"
        assert "error" not in response.lower() or "blood" in response.lower()
