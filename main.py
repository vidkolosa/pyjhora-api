from fastapi import FastAPI, Query
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, List

app = FastAPI()

# --- 27 nakšater ---
NAKSHATRAS = [
    "Ashvini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
    "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
    "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
    "Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati"
]

# -----------------------------
#   Jaimini ČARA-KARAKAS (JHora 7.32)
# -----------------------------
def _sidereal_longitudes(jd_ut: float, use_true_node: bool = True):
    import swisseph as swe
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)  # Lahiri / Chitrapaksha
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    bodies = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
    }
    node_id = swe.TRUE_NODE if use_true_node else swe.MEAN_NODE
    bodies["Rahu"] = node_id  # Ketu ne vključujemo

    lons = {}
    for name, bid in bodies.items():
        lons[name] = swe.calc_ut(jd_ut, bid, flag)[0][0]  # 0..360 sidereal
    return lons

def _chara_karakas_from_lons(lons: dict):
    """
    Jaimini Chara Karakas po sistemu Jagannath Hora 7.32:
    - Rangiranje po stopinjah ZNOTRAJ znaka (0–30°).
    - Rahu: 30 - (lon % 30).
    - Ketu izključen.
    Vrne (kar7, kar8) -> 7-karaka (brez Rahuja) in 8-karaka (z Rahujem).
    """
    def deg_in_sign(lon: float) -> float:
        return lon % 30.0

    items = []
    for name, lon in lons.items():
        if name == "Ketu":
            continue
        if name == "Rahu":
            val = 30.0 - (lon % 30.0)
        else:
            val = deg_in_sign(lon)
        items.append((name, val))

    # 8-karaka (Sun..Saturn + Rahu)
    eight_set = {"Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu"}
    items8 = [(n, m) for n, m in items if n in eight_set]
    items8.sort(key=lambda x: x[1], reverse=True)
    labels8 = ["AK","AmK","BK","MK","PK","GK","DK","PiK"]
    kar8 = {labels8[i]: items8[i][0] for i in range(min(8, len(items8)))}

    # 7-karaka (brez Rahuja)
    seven_set = eight_set - {"Rahu"}
    items7 = [(n, m) for n, m in items if n in seven_set]
    items7.sort(key=lambda x: x[1], reverse=True)
    labels7 = ["AK","AmK","BK","MK","PK","GK","DK"]
    kar7 = {labels7[i]: items7[i][0] for i in range(min(7, len(items7)))}

    return kar7, kar8

# -----------------------------
#  Health / Info
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/jhora_info")
def jhora_info():
    info = {}
    try:
        import importlib
        import importlib.metadata as im
        importlib.import_module("jhora")
        info["jhora_import"] = "ok"
        try:
            info["version"] = im.version("PyJHora")
        except Exception:
            info["version"] = "unknown"
    except Exception as e:
        info["jhora_import"] = f"error: {e}"
        info["version"] = "unknown"
    return info

# -----------------------------
#   /chart (PyJHora -> naš CK fix; fallback: Swiss)
# -----------------------------
@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),     # YYYY-MM-DD (lokalni datum)
    time: str = Query(...),     # HH:MM     (lokalni čas, 24h)
    place: str = Query(...),    # echo
    lat: float = Query(...),    # +N
    lon: float = Query(...),    # +E
    tz:  float = Query(...),    # ure (SLO: zima 1, poletje 2)
):
    # --- poskus PyJHora (a CK vedno preračunamo po naši metodi) ---
    try:
        from jhora.engine.astro_engine import run as jrun
        import swisseph as swe

        res = jrun(name, date, time, place)

        # izračun JD_UT iz lokalnega časa + TZ
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        hour_ut = (hh + mm/60.0) - tz
        jd_ut = swe.julday(y, m, d, hour_ut, swe.GREG_CAL)

        lons = _sidereal_longitudes(jd_ut, use_true_node=True)
        kar7, kar8 = _chara_karakas_from_lons(lons)

        return {
            "source": "PyJHora+CKfix",
            "ascendant": res["summary"]["ascendant"]["text"],
            "moon_nakshatra": res["summary"]["moon_nakshatra"],
            "chara_karakas_7": kar7,
            "chara_karakas_8": kar8
        }
    except Exception:
        pass

    # --- fallback: Swiss Ephemeris ---
    try:
        import swisseph as swe
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        hour_dec = hh + mm/60.0
        hour_ut = hour_dec - tz
        jd_ut = swe.julday(y, m, d, hour_ut, swe.GREG_CAL)

        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

        # Moon & nakshatra
        moon_lon = swe.calc_ut(jd_ut, swe.MOON, flag)[0][0]
        idx = int(math.floor((moon_lon / 360.0) * 27.0)) % 27
        nak = NAKSHATRAS[idx]

        # Ascendant
        ascmc, _ = swe.houses_ex(jd_ut, lat, lon, b'P')
        asc_deg = ascmc[0]
        zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                  "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        asc_sign = zodiac[int(asc_deg // 30)]

        # Chara Karakas (JHora-style)
        lons = _sidereal_longitudes(jd_ut, use_true_node=True)
        kar7, kar8 = _chara_karakas_from_lons(lons)

        return {
            "source": "SwissEphemeris",
            "echo": {"name": name, "place": place},
            "ascendant": {"degree": round(asc_deg, 2), "sign": asc_sign},
            "moon": {"longitude": round(moon_lon, 2), "nakshatra": nak},
            "chara_karakas_7": kar7,
            "chara_karakas_8": kar8
        }
    except Exception as e:
        return {"error": f"fallback_failed: {e}"}

# -----------------------------
#   SLO chart_smart (lokalna mini baza)
# -----------------------------
CITY_DB = {
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
    p = (place or "").lower().strip()
    if p in CITY_DB:
        return CITY_DB[p]
    for name, tpl in CITY_DB.items():
        if name in p:
            return tpl
    return None

@app.get("/chart_smart")
def chart_smart(
    name: str = Query(...),
    date: str = Query(...),
    time: str = Query(...),
    place: str = Query(...),
):
    city = _find_city(place)
    if not city:
        return {"error": "unknown_place", "hint": "Uporabi eno izmed: " + ", ".join(CITY_DB.keys())}
    lat, lon, tzid = city
    try:
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        local_dt = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tzid))
        tz_offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    except Exception as e:
        return {"error": f"bad_datetime: {e}"}
    return chart(name=name, date=date, time=time, place=place, lat=lat, lon=lon, tz=tz_offset_hours)

# -----------------------------
#   GLOBAL geocoder (offline)
#   - geonamescache + timezonefinder
# -----------------------------
def _geocode_global(place: str) -> Tuple[Optional[Tuple[float, float, str]], Optional[List[str]]]:
    """
    Vrne:
      - (lat, lon, tzid), None  -> enoznačno mesto
      - None, [možnosti]        -> več ujemanj (dvoumno)
      - None, None              -> ni najdeno
    """
    import geonamescache
    from timezonefinder import TimezoneFinder

    # normalizacija: sprejmemo "City,CC", "City, CC", "City, Slovenia" ...
    raw = (place or "").strip()
    if not raw:
        return None, None
    norm = raw.replace(" ,", ",").replace(", ", ",")
    parts = norm.split(",")
    if len(parts) == 2:
        city_raw, country_raw = parts[0].strip(), parts[1].strip()
        cc_map = {
            "slovenia": "SI", "slovenija": "SI",
            "austria": "AT", "österreich": "AT", "oesterreich": "AT",
            "croatia": "HR", "hrvatska": "HR",
            "italy": "IT", "italia": "IT",
            "germany": "DE", "deutschland": "DE",
        }
        country_cc = cc_map.get(country_raw.lower(), country_raw.upper())
        p = f"{city_raw}, {country_cc}".lower()
    else:
        p = raw.lower().strip()

    gc = geonamescache.GeonamesCache()
    cities = gc.get_cities()

    def norm_name(c): return c["name"].lower().strip()
    def name_cc(c):  return f"{c['name']}, {c['countrycode']}"
    def norm_pair(c): return name_cc(c).lower()

    candidates: List[dict] = []
    for c in cities.values():
        if p == norm_pair(c) or p == norm_name(c):
            candidates.append(c)
    if not candidates:
        for c in cities.values():
            if p in norm_name(c) or p in norm_pair(c):
                candidates.append(c)
    if not candidates:
        return None, None

    # Deduplikacija po (ime, država)
    seen = set()
    uniq: List[dict] = []
    for c in candidates:
        k = (c["name"], c["countrycode"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)

    if len(uniq) > 1:
        options = [name_cc(c) for c in sorted(uniq, key=lambda x: x.get("population", 0), reverse=True)[:7]]
        return None, options

    c = uniq[0]
    lat = float(c["latitude"])
    lon = float(c["longitude"])
    tzid = TimezoneFinder().timezone_at(lng=lon, lat=lat)
    if not tzid:
        return None, [name_cc(c)]
    return (lat, lon, tzid), None

@app.get("/chart_global")
def chart_global(
    name: str,
    date: str,   # YYYY-MM-DD
    time: str,   # HH:MM
    place: str,  # "City, CC" (npr. "Maribor, SI")
):
    raw = (place or "").strip()
    if "," not in raw:
        return {"error": "country_required", "hint": "Uporabi 'City, CC' (npr. 'Springfield, US' ali 'Paris, FR')"}

    geo, options = _geocode_global(raw)
    if options:
        return {"error": "place_ambiguous", "options": options}
    if not geo:
        return {"error": "place_not_found", "hint": "Uporabi 'City, CC' (npr. 'Springfield, US')"}

    lat, lon, tzid = geo
    try:
        y, m, d = [int(x) for x in date.split("-")]
        hh, mm = [int(x) for x in time.split(":")]
        local_dt = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tzid))
        tz_offset_hours = local_dt.utcoffset().total_seconds() / 3600.0
    except Exception as e:
        return {"error": f"bad_datetime: {e}"}

    return chart(name=name, date=date, time=time, place=place, lat=lat, lon=lon, tz=tz_offset_hours)
