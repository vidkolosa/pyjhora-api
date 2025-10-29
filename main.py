from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),   # YYYY-MM-DD
    time: str = Query(...),   # HH:MM (24h)
    place: str = Query(...),  # City, Country
):
    # Zaenkrat samo test, da vidimo pot deluje:
    return {
        "echo": {
            "name": name,
            "date": date,
            "time": time,
            "place": place
        }
    }
