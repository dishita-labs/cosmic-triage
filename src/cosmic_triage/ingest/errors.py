"""Typed errors for external access."""


class IngestError(Exception):
    pass


class OfflineCacheMiss(IngestError):
    """COSMIC_OFFLINE=1 and the requested entry is not in the cache."""


class NetworkDisabled(IngestError):
    """A network call was attempted while offline."""


class CredentialMissing(IngestError):
    def __init__(self, name: str, how: str) -> None:
        super().__init__(f"BLOCKED: CREDENTIAL REQUIRED — {name}. {how}")
        self.name = name
        self.how = how


class ExternalAPIError(IngestError):
    def __init__(self, client: str, status: int | None, message: str) -> None:
        super().__init__(f"{client}: HTTP {status}: {message}")
        self.client = client
        self.status = status


class RateLimited(ExternalAPIError):
    pass
