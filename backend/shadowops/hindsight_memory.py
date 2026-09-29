import os
import logging
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Protocol
from urllib.parse import urlparse


HINDSIGHT_CLOUD_API_URL = "https://api.hindsight.vectorize.io"
logger = logging.getLogger("shadowops.hindsight")


class MemoryFact(Protocol):
    id: str
    text: str
    type: str | None
    context: str | None
    metadata: dict[str, str] | None


class MemoryStore(Protocol):
    def recall(self, query: str) -> list[MemoryFact]: ...

    def retain(
        self,
        *,
        content: str,
        document_id: str,
        occurred_at: datetime,
        metadata: dict[str, str],
        service: str,
    ) -> None: ...


class MemoryConfigurationError(RuntimeError):
    pass


class MemoryServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class HindsightSettings:
    api_url: str
    bank_id: str
    api_key: str | None

    @classmethod
    def from_environment(cls) -> "HindsightSettings":
        api_url = os.getenv("HINDSIGHT_API_URL", "").strip()
        bank_id = os.getenv("HINDSIGHT_BANK_ID", "").strip()
        api_key = os.getenv("HINDSIGHT_API_KEY", "").strip() or None
        missing = [name for name, value in (("HINDSIGHT_API_URL", api_url), ("HINDSIGHT_BANK_ID", bank_id)) if not value]
        if api_url and urlparse(api_url).hostname == "api.hindsight.vectorize.io" and not api_key:
            missing.append("HINDSIGHT_API_KEY")
        if missing:
            raise MemoryConfigurationError(
                "Configure " + " and ".join(missing) + " before using Hindsight memory. "
                "Copy .env.example to .env and set a real Hindsight endpoint and bank."
            )
        return cls(api_url=api_url, bank_id=bank_id, api_key=api_key)


class HindsightMemoryStore:
    def __init__(self, settings: HindsightSettings) -> None:
        try:
            from hindsight_client import Hindsight
        except ImportError as exc:
            raise MemoryConfigurationError(
                "The Hindsight Python client is not installed. Install backend/requirements.txt."
            ) from exc

        self._bank_id = settings.bank_id
        self._client = Hindsight(
            base_url=settings.api_url,
            api_key=settings.api_key,
            timeout=20.0,
        )

    def recall(self, query: str) -> list[MemoryFact]:
        started = perf_counter()
        try:
            response = self._client.recall(bank_id=self._bank_id, query=query, budget="mid", max_tokens=1800)
            logger.info("operation=recall bank_id=%s result_count=%s duration_ms=%.2f", self._bank_id, len(response.results), (perf_counter() - started) * 1000)
            return list(response.results)
        except Exception as exc:
            logger.warning("operation=recall bank_id=%s error=%s duration_ms=%.2f", self._bank_id, type(exc).__name__, (perf_counter() - started) * 1000)
            raise MemoryServiceError(f"Hindsight recall failed: {type(exc).__name__}") from exc

    def retain(
        self,
        *,
        content: str,
        document_id: str,
        occurred_at: datetime,
        metadata: dict[str, str],
        service: str,
    ) -> None:
        started = perf_counter()
        try:
            response = self._client.retain(
                bank_id=self._bank_id,
                content=content,
                context="resolved SRE incident",
                timestamp=occurred_at,
                document_id=document_id,
                metadata=metadata,
                tags=[f"service:{service}"],
                retain_async=False,
            )
            if not getattr(response, "success", False):
                raise MemoryServiceError("Hindsight did not confirm the incident memory write.")
            logger.info("operation=retain bank_id=%s document_id=%s success=true duration_ms=%.2f", self._bank_id, document_id, (perf_counter() - started) * 1000)
        except MemoryServiceError:
            raise
        except Exception as exc:
            logger.warning("operation=retain bank_id=%s document_id=%s error=%s duration_ms=%.2f", self._bank_id, document_id, type(exc).__name__, (perf_counter() - started) * 1000)
            raise MemoryServiceError(f"Hindsight retain failed: {type(exc).__name__}") from exc

    def close(self) -> None:
        try:
            self._client.close()
        except Exception as exc:
            raise MemoryServiceError(f"Hindsight client shutdown failed: {type(exc).__name__}") from exc


def configured_memory_store() -> tuple[MemoryStore, str]:
    settings = HindsightSettings.from_environment()
    return HindsightMemoryStore(settings), settings.bank_id