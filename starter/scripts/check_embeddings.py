"""Download the configured model and verify local multilingual embeddings."""
from math import sqrt
from pathlib import Path
import sys

# Allow both `python scripts/check_embeddings.py` and
# `python -m scripts.check_embeddings` from the starter directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.embeddings import MyEmbedder


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    return dot_product / (left_norm * right_norm)


def main() -> None:
    embedder = MyEmbedder(device="cpu")
    documents = [
        "Học máy cho phép máy tính học các mẫu từ dữ liệu.",
        "Cây xanh hấp thụ khí carbon dioxide trong quá trình quang hợp.",
    ]
    query = "Máy tính học từ dữ liệu như thế nào?"

    document_vectors = embedder.embed_documents(documents)
    query_vector = embedder.embed_query(query)

    print(f"Model: {embedder.model_name}")
    print(f"Dimensions: {embedder.dimensions}")
    print(f"Document vectors: {len(document_vectors)}")
    print(f"Query dimensions: {len(query_vector)}")
    print(
        "Similarity to machine-learning text: "
        f"{cosine_similarity(query_vector, document_vectors[0]):.4f}"
    )
    print(
        "Similarity to unrelated text: "
        f"{cosine_similarity(query_vector, document_vectors[1]):.4f}"
    )

    if embedder.dimensions != 384:
        raise RuntimeError(
            f"Expected 384 dimensions, received {embedder.dimensions}"
        )
    if len(query_vector) != embedder.dimensions:
        raise RuntimeError("Query vector has an unexpected size")
    if any(len(vector) != embedder.dimensions for vector in document_vectors):
        raise RuntimeError("A document vector has an unexpected size")

    print("Embedding setup OK")


if __name__ == "__main__":
    main()
