from fastapi import FastAPI, Query
import astro_engine as ae

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),
    time: str = Query(...),
    place: str = Query(...)
):
    try:
        res = ae.run(name, date, time, place)
        return {
            "ascendant": res["summary"]["ascendant"]["text"],
            "moon_nakshatra": res["summary"]["moon_nakshatra"],
            "chara_karakas": res["summary"]["chara_karakas"]
        }
    except Exception as e:
        return {"error": str(e)}
