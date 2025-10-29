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


from datetime import datetime
from zoneinfo import ZoneInfo

# Mini baza koordinat (lahko dodaš še mesta)
CITY_DB = {
    # ime: (lat, lon, tzid)
    "maribor": (46.56, 15.65, "Europe/Ljubljana"),
    "ljubljana": (46.06, 14.51, "Europe/Ljubljana"),
    "celje": (46.24, 15.27, "Europe/Ljubljana"),
    "kranj": (46.24, 14.36, "Europe/Ljubljana"),
    "koper": (45.55, 13.73, "Europe/Ljubljana"),
    "murska sobota": (46.66, 16.16, "Europe/Ljubljana"),
    "ptuj": (46.42, 15.87, "Europe/Ljubljana"),
    "novo mesto": (45.80, 15.17, "Europe/Ljubljana"),
    "nova gorica": (45.95, 13.65, "Europe/Ljubljana"),
    "velenje": (46.36, 15.11, "Europe/Ljubljana"),
}

def _find_city(place: str):
    p = place.lower().strip()
    # najprej poskusi popolno ujemanje
    if p in CITY_DB:
        return CITY_DB[p]
    # potem poskusi, če niz vsebuje ime mesta
    for name, tpl in CITY_DB.items():
        if name in p:
            return tpl
    return None

@app.get("/chart_smart")
def chart_smart(
    name: str = Query(...),
    date: str = Query(...),   # YYYY-MM-DD
    time: str = Query(...),   # HH:MM (24h)
    place: str = Query(...),  # npr. "Maribor", "Maribor, Slovenia"
):
    """
    Enostavna verzija: brez lat/lon/tz.
    - prepozna slovenska mesta iz CITY_DB
    - časovni pas in DST (poletje/zima) izračuna sam (ZoneInfo)
    """
    # 1) poišči mesto
    city = _find_city(place)
    if not city:
        return {"error": "unknown_place", "hint": "Uporabi eno izmed: " + ", ".join(CITY_DB.keys())}

    lat, lon, tzid = city

    # 2) izračunaj lokalni -> UTC offset za dan/uro (samodejno upošteva poletje/zima)
    try:
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        local_dt = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tzid))
        tz_offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    except Exception as e:
        return {"error": f"bad_datetime: {e}"}

    # 3) pokliči obstoječi /chart "motor"
    return chart(
        name=name, date=date, time=time, place=place,
        lat=lat, lon=lon, tz=tz_offset_hours
    )

from zoneinfo import ZoneInfo
from datetime import datetime
from typing import Optional

# --- GLOBAL PLACE → (lat, lon, tzid) ---
def _geocode_global(place: str) -> Optional[tuple[float, float, str]]:
    """
    Brez interneta:
    - geonamescache: poišče koordinate mesta (približno)
    - timezonefinder: izračuna ime čas. pasu iz lat/lon
    """
    import geonamescache
    from timezonefinder import TimezoneFinder

    p = place.strip().lower()
    if not p:
        return None

    gc = geonamescache.GeonamesCache()
    cities = gc.get_cities()  # dict id -> info
    # Najprej poskusi natančno ime, nato 'contains'
    def norm(s): return s.lower().strip()
    candidates = []

    # 1) exact match by name
    for c in cities.values():
        if norm(c['name']) == p or norm(f"{c['name']}, {c['countrycode']}") == p:
            candidates.append(c)

    # 2) contains (če exact ni našel)
    if not candidates:
        for c in cities.values():
            name_cc = f"{c['name']}, {c['countrycode']}".lower()
            if p in norm(c['name']) or p in name_cc:
                candidates.append(c)

    if not candidates:
        return None

    # Vzemi prvega z največ prebivalci (verjetneje pravilno)
    c = sorted(candidates, key=lambda x: x.get('population', 0), reverse=True)[0]
    lat = float(c['latitude'])
    lon = float(c['longitude'])

    tf = TimezoneFinder()
    tzid = tf.timezone_at(lng=lon, lat=lat)
    if not tzid:
        return None
    return (lat, lon, tzid)

@app.get("/chart_global")
def chart_global(
    name: str,
    date: str,   # YYYY-MM-DD
    time: str,   # HH:MM
    place: str,  # "City" ali "City, Country"
):
    """
    Internacionalno:
      - iz 'place' najde lat/lon (geonamescache)
      - določi časovni pas (timezonefinder)
      - DST/poletje-zima izračuna sam (ZoneInfo)
      - nato pokliče /chart (Swiss Ephemeris fallback ali PyJHora, če je na voljo)
    """
    geo = _geocode_global(place)
    if not geo:
        return {"error": "place_not_found", "hint": "Poskusi 'City, Country' (npr. 'New York, US' ali 'Sydney, AU')"}

    lat, lon, tzid = geo

    # izračun lokalnega UTC offseta za izbrani datum/uro
    try:
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        local_dt = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tzid))
        tz_offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    except Exception as e:
        return {"error": f"bad_datetime: {e}"}

    # ponovno uporabimo obstoječi motor /chart
    return chart(
        name=name, date=date, time=time, place=place,
        lat=lat, lon=lon, tz=tz_offset_hours
    )
