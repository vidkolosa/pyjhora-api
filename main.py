from fastapi import FastAPI, Query
import math

app = FastAPI()

# --- Nakshatra imena (27) ---
NAKSHATRAS = [
    "Ashvini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
    "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
    "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
    "Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati"
]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/jhora_info")
def jhora_info():
    """
    Minimalna diagnostika: ali je paket jhora sploh uvozen.
    """
    info = {}
    try:
        import importlib
        import importlib.metadata as im
        jhora = importlib.import_module("jhora")
        info["jhora_import"] = "ok"
        try:
            info["version"] = im.version("PyJHora")
        except Exception:
            info["version"] = "unknown"
    except Exception as e:
        info["jhora_import"] = f"error: {e}"
        info["version"] = "unknown"
    return info

@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),     # YYYY-MM-DD
    time: str = Query(...),     # HH:MM (24h)
    place: str = Query(...),    # City, Country (le za echo)
    lat: float = Query(...),    # +N (npr. Maribor 46.56)
    lon: float = Query(...),    # +E (Maribor 15.65)
    tz:  float = Query(...),    # ura offset od UTC (poleti SLO = 2, pozimi = 1)
):
    """
    Vrne ascendent + Moon nakshatro.
    1) najprej poskusi PyJHora (če je engine na voljo)
    2) fallback: Swiss Ephemeris (pyswisseph)
    """
    # --- POSKUS PyJHora (če kdaj dobiš engine modul) ---
    try:
        from jhora.engine.astro_engine import run as jrun
        res = jrun(name, date, time, place)
        return {
            "source": "PyJHora",
            "ascendant": res["summary"]["ascendant"]["text"],
            "moon_nakshatra": res["summary"]["moon_nakshatra"],
            "chara_karakas": res["summary"]["chara_karakas"]
        }
    except Exception:
        pass  # preklopimo na fallback

    # --- FALLBACK: Swiss Ephemeris ---
    try:
        import swisseph as swe

        # parse datuma in časa
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        hour_dec = hh + mm/60.0

        # lokalni čas -> UTC
        hour_ut = hour_dec - tz

        # julijanski dan (UT)
        jd_ut = swe.julday(y, m, d, hour_ut, swe.GREG_CAL)

        # sidereal (Lahiri), ker to uporablja večina Jyotish sistemov
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

        # Lunina dolžina (sidereal)
        flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        moon_lon = swe.calc_ut(jd_ut, swe.MOON, flag)[0][0]  # ekliptična dolžina v stopinjah 0..360

        # Nakshatra index (0..26)
        idx = int(math.floor((moon_lon / 360.0) * 27.0)) % 27
        nak = NAKSHATRAS[idx]

        # Hiše + ascendent (Placidus; ascendent je element 0 iz houses_ex)
        # opomba: swe pričakuje geografsko dolžino +E, širino +N
        ascmc, cusps = swe.houses_ex(jd_ut, lat, lon, b'P')  # Placidus
        asc_deg = ascmc[0]  # 0..360

        # Pretvorimo asc v znak (sanskrit opcijsko)
        zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                  "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        asc_sign = zodiac[int(asc_deg // 30)]

        return {
            "source": "SwissEphemeris",
            "echo": {"name": name, "place": place},
            "ascendant": {"degree": round(asc_deg, 2), "sign": asc_sign},
            "moon": {"longitude": round(moon_lon, 2), "nakshatra": nak}
        }

    except Exception as e:
        return {"error": f"fallback_failed: {e}"}
