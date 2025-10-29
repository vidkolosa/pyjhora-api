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
    try:
        # ⬇️ Lazy import pravilnega modula:
        from astro_engine import run as jrun
        res = jrun(name, date, time, place)

        return {
            "ascendant": res["summary"]["ascendant"]["text"],
            "moon_nakshatra": res["summary"]["moon_nakshatra"],
            "chara_karakas": res["summary"]["chara_karakas"]
        }
    except Exception as e:
        return {"error": str(e)}
