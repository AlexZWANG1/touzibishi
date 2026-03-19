"""
Embedding abstraction layer — supports OpenAI and Ollama providers.

Switch providers via EMBEDDING_PROVIDER env var:
  - "openai" (default): uses OpenAI API (text-embedding-3-small)
  - "ollama": uses local Ollama server (nomic-embed-text)
"""

import json
import os
from typing import Callable


class Embedder:
    """Thin abstraction over embedding providers."""

    def __init__(self, usage_tracker: Callable[..., None] | None = None):
        self.provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        if self.provider == "ollama":
            self.model_name = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        else:
            self.model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._usage_tracker = usage_tracker

    @property
    def model_id(self) -> str:
        return f"{self.provider}:{self.model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns one vector per input text."""
        if self.provider == "ollama":
            return self._embed_ollama(texts)
        return self._embed_openai(texts)

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        import openai

        client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        response = client.embeddings.create(model=self.model_name, input=texts)
        usage = getattr(response, "usage", None)
        if self._usage_tracker:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            try:
                self._usage_tracker(input_tokens=prompt_tokens)
            except TypeError:
                self._usage_tracker(prompt_tokens)
        return [item.embedding for item in response.data]

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        import httpx

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        vectors = []
        for text in texts:
            resp = httpx.post(
                f"{base_url}/api/embeddings",
                json={"model": self.model_name, "prompt": text},
                timeout=30.0,
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
        return vectors
