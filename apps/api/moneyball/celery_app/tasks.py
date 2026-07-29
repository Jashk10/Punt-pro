from moneyball.celery_app.app import app
from moneyball.db.session import SessionLocal


@app.task(name="moneyball.ping")
def ping() -> str:
    return "pong"


@app.task(name="moneyball.ingestion.sync_afl", bind=True, max_retries=3, default_retry_delay=30)
def sync_afl(self, year: int, round_: int | None = None) -> dict:
    from moneyball.ingestion.afl.sync import run_full_sync

    db = SessionLocal()
    try:
        return run_full_sync(db, year=year, round_=round_)
    except Exception as exc:  # network/API failures are expected and retryable
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
