from fastapi import FastAPI, Query
import importlib
import json

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/jhora_info")
def jhora_info():
    import importlib, pkgutil, json
    info = {}

    try:
        jhora = importlib.import_module("jhora")
        info["jhora_import"] = "ok"
    except Exception as e:
        info["jhora_import"] = f"error: {e}"
        return info

    # Kateri moduli obstajajo
    modules = ["jhora.horoscope", "jhora.horoscope.chart"]
    details = {}
    for m in modules:
        try:
            mod = importlib.import_module(m)
            attrs = dir(mod)
            # izpišemo samo "uporabne" stvari (brez __dunder__ imen)
            public = [a for a in attrs if not a.startswith("_")]
            details[m] = public[:200]  # omejimo izpis
        except Exception as e:
            details[m] = f"error: {e}"
    info["modules"] = details

    # poskusi prebrati verzijo paketa
    try:
        import importlib.metadata as im
        info["version"] = im.version("PyJHora")
    except Exception:
        info["version"] = "unknown"

    return info



@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),   # YYYY-MM-DD
    time: str = Query(...),   # HH:MM (24h)
    place: str = Query(...),  # City, Country
):
    try:
        # lazy import – zmanjšamo možnost sesutja ob zagonu
        try:
            from jhora.engine.astro_engine import run as jrun
        except Exception:
            # nekateri commiti imajo drugačno pot
            import importlib
            jrun = importlib.import_module("jhora.engine.astro_engine").run

        res = jrun(name, date, time, place)
        return {
            "ascendant": res["summary"]["ascendant"]["text"],
            "moon_nakshatra": res["summary"]["moon_nakshatra"],
            "chara_karakas": res["summary"]["chara_karakas"]
        }
    except Exception as e:
        return {"error": str(e)}
