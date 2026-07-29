from __future__ import annotations

from typing import TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


def get_or_create(db: Session, model: type[ModelT], defaults: dict | None = None, **kwargs) -> tuple[ModelT, bool]:
    """Fetch a row matching kwargs, or insert one with kwargs + defaults.

    Not concurrency-safe (no upsert/ON CONFLICT) — fine for seed scripts and
    single-worker ingestion jobs, not for parallel writers hitting the same key.
    """
    instance = db.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True
