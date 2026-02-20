"""Embedding generation service using OpenAI text-embedding models.

Provides both single-text and batched embedding generation with automatic
chunking to stay within OpenAI's per-request input limits.  All heavy I/O
is async-safe — the synchronous OpenAI SDK call is dispatched to a thread
pool so it never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# OpenAI allows up to 2 048 inputs per embeddings request; we use a
# conservative default that works well for typical chunk sizes.
_DEFAULT_BATCH_SIZE = 100
_MAX_RETRIES = 3


class EmbeddingService:
    """Generate text embeddings via the OpenAI API.

    Parameters
    ----------
    model:
        Embedding model identifier (default ``text-embedding-3-small``).
    api_key:
        OpenAI API key.  Falls back to the ``OPENAI_API_KEY`` env var
        if not provided.
    dimensions:
        Optional output dimensionality override supported by v3 models.
        *None* keeps the model's native dimension (1 536 for ``-small``).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text string.

        Returns an empty vector for blank input to avoid API errors.
        """
        if not text or not text.strip():
            logger.warning("embed_single called with empty text — returning zero vector")
            return []

        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts, batching as needed.

        Parameters
        ----------
        texts:
            Texts to embed (order is preserved).
        batch_size:
            Number of texts per API call (max 2 048).

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in the same order.
        """
        if not texts:
            return []

        # Sanitise — OpenAI rejects empty strings
        sanitised = [t if t and t.strip() else " " for t in texts]

        all_embeddings: list[list[float]] = []
        loop = asyncio.get_running_loop()

        for start in range(0, len(sanitised), batch_size):
            batch = sanitised[start : start + batch_size]
            logger.debug(
                "Embedding batch %d–%d of %d",
                start,
                start + len(batch),
                len(sanitised),
            )
            batch_embeddings = await loop.run_in_executor(
                None,
                partial(self._embed_sync, batch),
            )
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def model(self) -> str:
        """Return the model identifier in use."""
        return self._model

    # ------------------------------------------------------------------
    # Internal — synchronous SDK call (run in thread)
    # ------------------------------------------------------------------

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        """Blocking call to the OpenAI embeddings endpoint."""
        kwargs: dict[str, Any] = {"input": texts, "model": self._model}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.embeddings.create(**kwargs)
                # API returns items in the *same* order as input
                return [item.embedding for item in response.data]
            except Exception:
                if attempt == _MAX_RETRIES:
                    logger.exception(
                        "OpenAI embeddings call failed after %d attempts", _MAX_RETRIES
                    )
                    raise
                logger.warning(
                    "Embeddings attempt %d/%d failed — retrying",
                    attempt,
                    _MAX_RETRIES,
                )
