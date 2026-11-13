"""Persistent vector storage using PostgreSQL and pgvector."""
import json
from typing import Any

import psycopg

from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS document_chunks (
            strategy TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            source TEXT NOT NULL,
            page INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            metadata JSONB NOT NULL,
            embedding VECTOR({self.dimensions}) NOT NULL,
            PRIMARY KEY (strategy, chunk_id)
        );
        CREATE INDEX IF NOT EXISTS document_chunks_strategy_idx
            ON document_chunks (strategy);
        """
        with psycopg.connect(self.database_url) as connection:
            connection.execute(ddl)

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace one strategy atomically so changed documents leave no stale rows."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have equal lengths")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError("embedding has an unexpected dimension")

        rows = [
            (
                strategy,
                chunk.chunk_id,
                chunk.document_id,
                chunk.source,
                chunk.page,
                chunk.text,
                json.dumps(chunk.metadata, ensure_ascii=False),
                "[" + ",".join(str(value) for value in vector) + "]",
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        statement = """
            INSERT INTO document_chunks (
                strategy, chunk_id, document_id, source, page,
                text_content, metadata, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
        """
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                connection.execute(
                    "DELETE FROM document_chunks WHERE strategy = %s",
                    (strategy,),
                )
                with connection.cursor() as cursor:
                    cursor.executemany(statement, rows)

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Rank by cosine similarity and apply allow-listed metadata filters."""
        if len(query_vector) != self.dimensions:
            raise ValueError("query vector has an unexpected dimension")
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        allowed_filters = {"section", "year", "document_type", "language"}
        filters = filters or {}
        unknown = set(filters) - allowed_filters
        if unknown:
            raise ValueError(f"Unsupported filters: {sorted(unknown)}")

        vector = "[" + ",".join(str(value) for value in query_vector) + "]"
        clauses = ["strategy = %s"]
        where_params: list[Any] = [strategy]
        for key, value in filters.items():
            clauses.append("metadata ->> %s = %s")
            where_params.extend([key, str(value)])

        query = f"""
            SELECT chunk_id, document_id, source, page, text_content,
                   metadata, 1 - (embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE {' AND '.join(clauses)}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params = [vector, *where_params, vector, top_k]
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            {
                "chunk_id": row[0],
                "document_id": row[1],
                "source": row[2],
                "page": row[3],
                "text": row[4],
                "metadata": row[5],
                "score": float(row[6]),
            }
            for row in rows
        ]

    def count(self, strategy: str) -> int:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE strategy = %s",
                (strategy,),
            ).fetchone()
        return int(row[0]) if row else 0
