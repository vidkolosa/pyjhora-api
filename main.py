from fastapi import FastAPI, Query
from astro import generate_chart

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),     # format: YYYY-MM-DD
    time: str = Query(...),     # format: HH:MM (24h)
    place: str = Query(...),    # format: City, Country
):
    try:
        result = generate_chart(name, date, time, place)
        return {"data": result}
    except Exception as e:
        return {"error": str(e)}
