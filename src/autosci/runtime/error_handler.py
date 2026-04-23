"""Error handler — classifies LLM API errors and determines recovery strategy."""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedError:
    reason: str
    message: str
    retryable: bool = False
    should_compress: bool = False
    status_code: Optional[int] = None


class ErrorHandler:
    """Classifies API errors and tracks retry state."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self._retry_count = 0

    def classify(self, error: Exception) -> ClassifiedError:
        """Classify an exception into a structured error with recovery hints."""
        error_str = str(error).lower()

        # Extract HTTP status code if present
        status_code = None
        for code in [401, 403, 429, 500, 502, 503, 504, 413]:
            if str(code) in str(error):
                status_code = code
                break

        if status_code == 401 or "unauthorized" in error_str or "authentication" in error_str:
            return ClassifiedError("auth", str(error), retryable=False, status_code=401)

        if status_code == 429 or "rate_limit" in error_str or "rate limit" in error_str:
            return ClassifiedError("rate_limit", str(error), retryable=True, status_code=429)

        if "overloaded" in error_str or status_code == 529:
            return ClassifiedError("overloaded", str(error), retryable=True, status_code=529)

        if status_code == 413 or "too large" in error_str:
            return ClassifiedError(
                "payload_too_large", str(error),
                retryable=True, should_compress=True, status_code=413,
            )

        if "context" in error_str and ("length" in error_str or "overflow" in error_str or "too long" in error_str):
            return ClassifiedError(
                "context_overflow", str(error),
                retryable=True, should_compress=True,
            )

        if "timeout" in error_str or "timed out" in error_str:
            return ClassifiedError("timeout", str(error), retryable=True)

        if status_code in (500, 502, 503, 504):
            return ClassifiedError("server_error", str(error), retryable=True, status_code=status_code)

        if "connection" in error_str:
            return ClassifiedError("connection_error", str(error), retryable=True)

        return ClassifiedError("unknown", str(error), retryable=True)

    def should_retry(self, classified: ClassifiedError) -> bool:
        """Check if we should retry after this error."""
        if not classified.retryable:
            return False
        if self._retry_count >= self.max_retries:
            logger.warning(f"Max retries ({self.max_retries}) reached for {classified.reason}")
            return False
        self._retry_count += 1
        return True

    def get_backoff_seconds(self) -> float:
        """Exponential backoff with cap."""
        return min(2 ** self._retry_count, 60)

    def reset(self) -> None:
        """Reset retry counter. Called at the start of each loop iteration."""
        self._retry_count = 0
