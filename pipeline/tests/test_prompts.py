import pytest
from pipeline.generator import load_prompt, PROMPTS_DIR

class TestPromptLoading:
    def test_prompts_directory_exists(self):
        assert PROMPTS_DIR.exists(), f"prompts directory not found: {PROMPTS_DIR}"

    def test_system_prompt_exists(self):
        prompt = load_prompt("system")
        assert len(prompt) > 0, "system prompt is empty"

    def test_rag_template_exists(self):
        prompt = load_prompt("rag_template")
        assert len(prompt) > 0, "RAG template is empty"
        assert "{context}" in prompt, "RAG template missing {context} placeholder"
        assert "{query}" in prompt, "RAG template missing {query} placeholder"

    def test_context_template_exists(self):
        prompt = load_prompt("context_template")
        assert len(prompt) > 0, "context template is empty"
        assert "{index}" in prompt, "context template missing {index} placeholder"
        assert "{title}" in prompt, "context template missing {title} placeholder"

    def test_invalid_prompt_raises_error(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt")
