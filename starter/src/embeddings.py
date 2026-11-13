"""Local multilingual embeddings used by the ingestion pipeline."""
from typing import Protocol

from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Embed Vietnamese and multilingual text with a local MiniLM model.

    The model is downloaded from Hugging Face on first use and then loaded from
    the local cache. Document and query vectors are L2-normalized so cosine
    similarity can be used consistently by pgvector.
    """

    DEFAULT_MODEL = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        batch_size: int = 16,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name, device=device)

        dimensions = self.model.get_embedding_dimension()
        if dimensions is None:
            raise ValueError(
                f"Cannot determine embedding dimensions for {model_name}"
            )
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("Document texts must not be empty")

        vectors = self.model.encode_document(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(texts) >= self.batch_size,
        )
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        if not question.strip():
            raise ValueError("Query must not be empty")

        vector = self.model.encode_query(
            question,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vector.tolist()
