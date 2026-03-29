import pytest
from pipeline.generator import OllamaGenerator

class TestOllamaGeneratorInit:
    def test_default_initialization(self):
        generator = OllamaGenerator()
        assert generator.model == "llama3.2"
        assert generator.base_url == "http://localhost:11434"
        assert generator.temperature == 0.3
        assert generator.max_tokens == 1024

    def test_custom_initialization(self):
        generator = OllamaGenerator(
            model="mistral",
            temperature=0.7,
            max_tokens=2048
        )
        assert generator.model == "mistral"
        assert generator.temperature == 0.7
        assert generator.max_tokens == 2048

    def test_prompts_loaded(self):
        generator = OllamaGenerator()
        assert generator.system_prompt is not None
        assert generator.rag_template is not None
        assert generator.context_template is not None

class TestContextFormatting:
    @pytest.fixture
    def generator(self):
        return OllamaGenerator()

    @pytest.fixture
    def sample_docs(self):
        return [
            {
                "title": "Hypertension Overview",
                "source": "MSD",
                "url": "https://example.com/hypertension",
                "text": "Hypertension is high blood pressure."
            },
            {
                "title": "Blood Pressure Guide",
                "source": "PDF",
                "url": None,
                "text": "Normal BP is 120/80 mmHg."
            }
        ]

    def test_format_context_includes_all_docs(self, generator, sample_docs):
        context = generator.format_context(sample_docs)
        assert "Hypertension Overview" in context
        assert "Blood Pressure Guide" in context

    def test_format_context_includes_source_types(self, generator, sample_docs):
        context = generator.format_context(sample_docs)
        assert "MSD" in context
        assert "PDF" in context

    def test_format_context_includes_urls_when_present(self, generator, sample_docs):
        context = generator.format_context(sample_docs)
        assert "https://example.com/hypertension" in context

    def test_format_context_handles_missing_url(self, generator, sample_docs):
        context = generator.format_context(sample_docs)
        assert "Blood Pressure Guide" in context

class TestPromptBuilding:
    @pytest.fixture
    def generator(self):
        return OllamaGenerator()

    @pytest.fixture
    def sample_docs(self):
        return [
            {
                "title": "Test Doc",
                "source": "PDF",
                "url": None,
                "text": "Sample medical content."
            }
        ]

    def test_build_prompt_includes_query(self, generator, sample_docs):
        query = "What is hypertension?"
        prompt = generator.build_prompt(query, sample_docs)
        assert query in prompt

    def test_build_prompt_includes_context(self, generator, sample_docs):
        prompt = generator.build_prompt("Test query", sample_docs)
        assert "Test Doc" in prompt
        assert "Sample medical content" in prompt

    def test_build_prompt_empty_docs(self, generator):
        prompt = generator.build_prompt("Test query", [])
        assert "Test query" in prompt
