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
#   Jaimini ČARA-KARAKAS
# -----------------------------
def _sidereal_longitudes(jd_ut: float, use_true_node: bool = True):
    import swisseph as swe
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    # Grahe: Sun..Saturn + Rahu
    bodies = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
    }
    # Node
    node_id = swe.TRUE_NODE if use_true_node else swe.MEAN_NODE
    bodies["Rahu"] = node_id

    lons = {}
    for name, bid in bodies.items():
        lons[name] = swe.calc_ut(jd_ut, bid, flag)[0][0]  # 0..360 sidereal
    return lons

def _chara_karakas_from_lons(lons: dict, include_rahu: bool = False):
    """
    Vrne seznam parov [(name, rank)], kjer rank 1=AK, 2=AmK, 3=BK, 4=MK, 5=PK, 6=GK, 7=DK, (8)=PiK.
    Pravilo: primerjamo ZNOTRAJ znaka -> deg_in_sign = lon % 30.
    Če include_rahu=True, za Rahu uporabimo 30 - (lon % 30).
    """
    def in_sign_deg(l):  # 0..30
        return l % 30.0

    items = []
    for name, lon in lons.items():
        if name == "Rahu" and not include_rahu:
            continue
        if name == "Rahu" and include_rahu:
            deg_in_sign = 30.0 - (lon % 30.0)  # Jaimini pravilo za Rahu
        else:
            deg_in_sign = in_sign_deg(lon)
        items.append((name, deg_in_sign))

    # razvrsti po padajoče (največ v znaku = AK)
    items.sort(key=lambda x: x[1], reverse=True)

    # preslikava v oznake
    labels7 = ["AK", "AmK", "BK", "MK", "PK", "GK", "DK"]
    labels8 = ["AK", "AmK", "BK", "MK", "PK", "GK", "DK", "PiK"]

    out7 = {labels7[i]: items[i][0] for i in range(min(7, len(items)))}
    if include_rahu and len(items) >= 8:
        out8 = {labels8[i]: items[i][0] for i in range(8)}
    else:
        out8 = None
    return out7, out8


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

@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),     # YYYY-MM-DD
    time: str = Query(...),     # HH:MM (24h)
    place: str = Query(...),    # City, Country (le za echo)
    lat: float = Query(...),    # +N
    lon: float = Query(...),    # +E
    tz:  float = Query(...),    # ure (npr. SLO poleti 2, pozimi 1)
):
    """Najprej poskusi PyJHora, sicer Swiss Ephemeris fallback."""
    # --- poskus PyJHora ---
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
        moon_lon = swe.calc_ut(jd_ut, swe.MOON, flag)[0][0]
        idx = int(math.floor((moon_lon / 360.0) * 27.0)) % 27
        nak = NAKSHATRAS[idx]
        ascmc, _ = swe.houses_ex(jd_ut, lat, lon, b'P')
        asc_deg = ascmc[0]
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
#   - strict: brez države ne gremo naprej
# -----------------------------

def _geocode_global(place: str) -> Tuple[Optional[Tuple[float, float, str]], Optional[List[str]]]:
    """
    Vrne:
      - (lat, lon, tzid), None  -> enoznačno mesto
      - None, [seznam možnosti] -> več ujemanj (dvoumno)
      - None, None              -> ni najdeno
    """
    import geonamescache
    from timezonefinder import TimezoneFinder

    p = (place or "").strip().lower()
    if not p:
        return None, None

    gc = geonamescache.GeonamesCache()
    cities = gc.get_cities()

    def norm_name(c): return c["name"].lower().strip()
    def name_cc(c):  return f"{c['name']}, {c['countrycode']}"
    def norm_pair(c): return name_cc(c).lower()

    # exact "name, CC" ali "name"
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

    # Če več kot 1 unikat → dvoumno
    if len(uniq) > 1:
        options = [
            name_cc(c)
            for c in sorted(uniq, key=lambda x: x.get("population", 0), reverse=True)[:7]
        ]
        return None, options

    # Enoznačno ujemanje
    c = uniq[0]
    lat = float(c["latitude"])
    lon = float(c["longitude"])
    tzid = TimezoneFinder().timezone_at(lng=lon, lat=lat)
    if not tzid:
        return None, None
    return (lat, lon, tzid), None

@app.get("/chart_global")
def chart_global(
    name: str,
    date: str,   # YYYY-MM-DD
    time: str,   # HH:MM
    place: str,  # zahtevamo "City, CC"
):
    """
    STRIKTNO: brez države (vejica) vrnemo 'country_required'.
    Nato:
      - geonamescache → lat/lon
      - timezonefinder → tzid
      - ZoneInfo → DST/offset
    """
    raw = (place or "").strip()
    if "," not in raw:
        return {"error": "country_required", "hint": "Uporabi 'City, CC' (npr. 'Springfield, US' ali 'Paris, FR')"}

    geo, options = _geocode_global(raw.lower())
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
