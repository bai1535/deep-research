"""Safe Pydantic model construction from untrusted LLM output.

LLM outputs are inherently unreliable — models add extra fields, use wrong
types, misspell enum values, or send malformed nested objects. This module
wraps every Pydantic model construction so that:

1. Extra fields are stripped (never crash on unexpected keys).
2. Enum values are coerced (case-insensitive, dash/underscore tolerant).
3. Missing required fields get sensible defaults where possible.
4. Nested list elements that fail validation are filtered, not fatal.
5. Every failure is logged with enough context to debug.

Usage:
    from deep_research.safe_construct import safe_construct_list

    entries = safe_construct_list(VerificationEntry, verify_data.get("entries", []))
"""

from __future__ import annotations

import enum
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("deep_research.parser")

T = TypeVar("T", bound=BaseModel)


def _is_enum_field(model_cls: type[BaseModel], field_name: str) -> bool:
    """Check if a field on a Pydantic model is typed as an Enum."""
    field_info = model_cls.model_fields.get(field_name)
    if field_info is None:
        return False
    annotation = field_info.annotation
    if annotation is None:
        return False
    # Check if the annotation itself is an Enum subclass
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return True
    # Check for Optional[EnumType] / Union[EnumType, None]
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        from typing import Union, Optional
        args = getattr(annotation, "__args__", ())
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, enum.Enum):
                return True
    return False


# Known enum value aliases the model might mistakenly produce
_ENUM_ALIASES: dict[str, str] = {
    "accepted": "verified",
    "rejected": "false",
    "true": "verified",
    "correct": "verified",
    "incorrect": "false",
    "wrong": "false",
    "unverified": "suspect",
    "uncertain": "disputed",
    "unknown": "disputed",
    "contested": "disputed",
    "partially": "suspect",
    "partial": "suspect",
    "unsupported": "false",
    "confirmed": "verified",
    "valid": "verified",
    "invalid": "false",
}


def _normalize_enum_value(raw_value: Any) -> Any:
    """Normalize enum-like values.

    Coerces: "HIGH" → "high", "VERIFIED" → "verified"
    Also maps known model-aliases: "accepted" → "verified", "rejected" → "false"
    Returns the original value if normalization doesn't apply.
    """
    if not isinstance(raw_value, str):
        return raw_value
    cleaned = raw_value.strip().lower().replace("-", "_")
    return _ENUM_ALIASES.get(cleaned, cleaned)


def _filter_known_fields(data: dict[str, Any], model_cls: type[BaseModel]) -> dict[str, Any]:
    """Return a dict containing only fields the Pydantic model actually defines.

    Logs a warning for each dropped field so operators can spot prompt-drift.
    Also normalizes enum field values (case-insensitive, whitespace-tolerant).
    """
    known = set(model_cls.model_fields.keys())
    filtered: dict[str, Any] = {}
    extra: list[str] = []
    for k, v in data.items():
        if k in known:
            # Only normalize values for enum-typed fields
            if _is_enum_field(model_cls, k):
                filtered[k] = _normalize_enum_value(v)
            else:
                filtered[k] = v
        else:
            extra.append(k)

    if extra:
        logger.debug(
            "Stripped %d extra field(s) from %s: %s",
            len(extra),
            model_cls.__name__,
            extra,
        )
    return filtered


def safe_construct_one(
    model_cls: type[T],
    data: dict[str, Any] | None,
    *,
    context: str = "",
    fallback: T | None = None,
) -> T | None:
    """Safely construct one Pydantic model instance from LLM output.

    Args:
        model_cls: The Pydantic model class to construct.
        data: Raw dict from JSON parsing (may contain extra/missing fields).
        context: Label for log messages (e.g. "VerificationEntry[3]").
        fallback: Optional fallback instance to return on total failure.
                  If None and construction fails, returns None.

    Returns:
        An instance of model_cls, or fallback/None on failure.
    """
    if data is None:
        logger.warning("[%s] Cannot construct %s: data is None", context, model_cls.__name__)
        return fallback

    if not isinstance(data, dict):
        logger.warning(
            "[%s] Cannot construct %s: expected dict, got %s",
            context,
            model_cls.__name__,
            type(data).__name__,
        )
        return fallback

    # Filter to known fields only (no ValidationError from extras)
    cleaned = _filter_known_fields(data, model_cls)

    try:
        return model_cls(**cleaned)
    except ValidationError as e:
        # Log details and attempt per-field fallback
        error_count = e.error_count()
        logger.warning(
            "[%s] %s construction failed with %d validation error(s): %s",
            context,
            model_cls.__name__,
            error_count,
            str(e.errors()[:5]),  # first 5 errors
        )

        # Try with only the fields that don't have errors
        error_fields = {err["loc"][0] for err in e.errors() if err.get("loc")}
        reduced = {k: v for k, v in cleaned.items() if k not in error_fields}
        if reduced and len(reduced) >= len(cleaned) * 0.5:
            try:
                from pydantic.fields import PydanticUndefinedType

                complete = dict(reduced)
                for field_name, field_info in model_cls.model_fields.items():
                    if field_name not in complete:
                        default = field_info.default
                        if isinstance(default, PydanticUndefinedType):
                            # Required field with no default — try a safe fallback
                            if _is_enum_field(model_cls, field_name):
                                # Use first enum value as default
                                annotation = field_info.annotation
                                if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
                                    complete[field_name] = list(annotation)[0].value
                                    continue
                            continue  # can't fill, skip
                        if default is not None and default is not ...:
                            complete[field_name] = default
                        elif field_info.default_factory is not None:
                            complete[field_name] = field_info.default_factory()
                        elif field_info.annotation and hasattr(field_info.annotation, "__origin__"):
                            complete[field_name] = field_info.annotation()

                instance = model_cls.model_construct(**complete)
                logger.debug(
                    "[%s] Partial %s constructed with %d/%d fields (filled %d defaults)",
                    context, model_cls.__name__, len(reduced), len(cleaned),
                    len(complete) - len(reduced),
                )
                return instance
            except Exception:
                pass

        logger.error(
            "[%s] Total failure constructing %s. Cleaned data: %s",
            context,
            model_cls.__name__,
            str(cleaned)[:500],
        )
        return fallback


def safe_construct_list(
    model_cls: type[T],
    items: list[dict[str, Any]] | None,
    *,
    context: str = "",
) -> list[T]:
    """Safely construct a list of Pydantic model instances.

    Each item is independently constructed — one bad item doesn't kill
    the entire list. Bad items are filtered out with a warning log.

    Args:
        model_cls: The Pydantic model class for each item.
        items: List of raw dicts to construct.
        context: Label prefix for log messages.

    Returns:
        List of successfully constructed model instances (may be empty).
    """
    if items is None:
        logger.warning("[%s] Cannot construct %s list: items is None", context, model_cls.__name__)
        return []

    if not isinstance(items, list):
        logger.warning(
            "[%s] Cannot construct %s list: expected list, got %s",
            context,
            model_cls.__name__,
            type(items).__name__,
        )
        return []

    results: list[T] = []
    failures = 0

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning(
                "[%s] %s[%d] is not a dict (%s), skipping",
                context,
                model_cls.__name__,
                i,
                type(item).__name__,
            )
            failures += 1
            continue

        instance = safe_construct_one(
            model_cls, item,
            context=f"{context}/{model_cls.__name__}[{i}]",
        )
        if instance is not None:
            results.append(instance)
        else:
            failures += 1

    if failures > 0:
        logger.warning(
            "[%s] %d/%d %s items failed construction",
            context,
            failures,
            len(items),
            model_cls.__name__,
        )

    return results
