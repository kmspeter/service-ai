from dataclasses import dataclass

type EmbeddingVector = tuple[float, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingUsage:
    """Usage reported by an embedding provider; unavailable values remain unset."""

    input_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingBatchResult:
    """SDK-independent result for one provider batch request."""

    vectors: tuple[EmbeddingVector, ...]
    provider: str
    model: str
    dimension: int
    usage: EmbeddingUsage
    latency_ms: int


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """SDK-independent result for one text."""

    vector: EmbeddingVector
    provider: str
    model: str
    dimension: int
    usage: EmbeddingUsage
    latency_ms: int
