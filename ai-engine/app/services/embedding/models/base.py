from abc import ABC, abstractmethod


class EmbeddingModel(ABC):
    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float] | None: ...

    @abstractmethod
    async def embed_passage(self, text: str) -> list[float] | None: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]: ...

    @abstractmethod
    async def health(self) -> bool: ...
