from moneyball.celery_app.app import app


@app.task(name="moneyball.ping")
def ping() -> str:
    return "pong"
