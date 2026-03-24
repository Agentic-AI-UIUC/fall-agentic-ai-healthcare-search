import os
from groq import Groq
from pathlib import Path
from typing import List, Dict

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    prompt_path = PROMPTS_DIR / f"{name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text().strip()


class GroqGenerator:
    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 1024
    ):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = Groq(api_key=api_key)

        self.system_prompt = load_prompt("system")
        self.rag_template = load_prompt("rag_template")
        self.context_template = load_prompt("context_template")

    # format retrieved documents into context string
    def format_context(self, retrieved_docs: List[Dict]) -> str:
        context_parts = []

        for i, doc in enumerate(retrieved_docs, 1):
            url_line = f"URL: {doc.get('url')}" if doc.get('url') else ""

            formatted = self.context_template.format(
                index=i,
                title=doc.get('title', 'Unknown'),
                source_type=doc.get('source', 'Unknown'),
                url_line=url_line,
                content=doc.get('text', '')
            )
            context_parts.append(formatted)

        return "\n".join(context_parts)

    # build the prompt with context and query
    def build_prompt(self, query: str, retrieved_docs: List[Dict]) -> str:
        context = self.format_context(retrieved_docs)

        return self.rag_template.format(
            context=context,
            query=query
        )

    # have Groq generate a response
    def generate(
        self,
        query: str,
        retrieved_docs: List[Dict],
    ) -> str:
        prompt = self.build_prompt(query, retrieved_docs)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            return f"Error communicating with Groq: {str(e)}"

    def check_health(self) -> bool:
        return bool(os.environ.get("GROQ_API_KEY"))


# Have LLM generate simple content without RAG context
def simple_generate(query: str, model: str = "llama-3.3-70b-versatile") -> str:
    try:
        generator = GroqGenerator(model=model)
    except ValueError as e:
        return f"Error: {str(e)}"

    if not generator.check_health():
        return "Error: GROQ_API_KEY is not set."

    try:
        response = generator.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": generator.system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error: {str(e)}"
