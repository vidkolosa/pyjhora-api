from fastapi import FastAPI, Query
import importlib
import json

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/jhora_info")
def jhora_info():
    """
    Diagnostika: pove, katera verzija PyJHora je nameščena
    in katere pomembne poti obstajajo v paketu.
    """
    info = {}
    try:
        jhora = importlib.import_module("jhora")
        info["jhora_import"] = "ok"
        # Poskusi prepoznane module/poti
        candidates = [
            "jhora.horoscope",
            "jhora.horoscope.chart",
            "jhora.horoscope.chart.charts",
            "jhora.horoscope.chart.drik",
            "jhora.panchanga.drik",
        ]
        found = {}
        for c in candidates:
            try:
                importlib.import_module(c)
                found[c] = True
            except Exception as e:
                found[c] = False
        info["modules_found"] = found

        # Verzijica iz distribucije (če obstaja)
        try:
            import pkg_resources  # včasih ni nameščen, pa je ok
            info["version"] = pkg_resources.get_distribution("PyJHora").version
        except Exception:
            info["version"] = "unknown"

    except Exception as e:
        info["jhora_import"] = f"error: {e}"

    return info

@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),   # YYYY-MM-DD
    time: str = Query(...),   # HH:MM (24h)
    place: str = Query(...),  # City, Country
):
    """
    Začasno: samo echo, dokler ne zaključiva povezave na prave jhora funkcije.
    """
    return {
        "echo": {
            "name": name,
            "date": date,
            "time": time,
            "place": place
        }
    }
