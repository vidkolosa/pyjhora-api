from fastapi import FastAPI, Query
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, List, Dict

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
#   Sidereal longitudes (Lahiri) – ALWAYS TRUE NODE
# -----------------------------
def _sidereal_longitudes_true(jd_ut: float) -> Dict[str, float]:
    """
    Vrne sidereal longitudes 0..360 za Sun..Saturn + Rahu (TRUE NODE).
    Ayanamša: Lahiri (Chitrapaksha).
    """
    import swisseph as swe
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

    bodies = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.TRUE_NODE,   # 🔒 vedno TRUE NODE
    }

    lons = {}
    for name, bid in bodies.items():
        lons[name] = swe.calc_ut(jd_ut, bid, flag)[0][0]
    return lons

# -----------------------------
#   Čara Karakas (8-karaka, Rahu vključen; Ketu izključen)
#   Rang po 0–30° v znaku; Rahu = 30 − (lon % 30)
# -----------------------------
def _chara_karakas_8(lons: Dict[str, float]) -> Dict[str, str]:
    def deg_in_sign(l): return l % 30.0
    pairs = []
    for name, lon in lons.items():
        if name == "Rahu":
            val = 30.0 - (lon % 30.0)
        else:
            val = deg_in_sign(lon)
        pairs.append((name, val))
    labels8 = ["AK","AmK","BK","MK","PK","GK","DK","PiK"]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return {labels8[i]: pairs[i][0] for i in range(min(8, len(pairs)))}

# -----------------------------
#   Bhave (Whole-Sign) – Rāši
# -----------------------------
def _planets_by_bhava(lons: Dict[str, float], asc_deg: float) -> Dict[str, int]:
    """
    Whole-Sign houses: house = ((planet_sign - asc_sign) % 12) + 1
    Dodamo še Ketu (180° od Rahuja) informativno.
    """
    asc_sign = int(asc_deg // 30)  # 0..11
    out: Dict[str, int] = {}
    lons_ext = dict(lons)
    lons_ext["Ketu"] = (lons["Rahu"] + 180.0) % 360.0

    for name, lon in lons_ext.items():
        sign = int(lon // 30)
        house = ((sign - asc_sign) % 12) + 1
        out[name] = house
    return out

def _invert_dict_list(bhavas: Dict[str, int]) -> Dict[int, List[str]]:
    box: Dict[int, List[str]] = {i: [] for i in range(1, 13)}
    for g, h in bhavas.items():
        box[h].append(g)
    for h in box:
        box[h].sort()
    return box

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
        import importlib, importlib.metadata as im
        importlib.import_module("jhora")
        info["jhora_import"] = "ok"
        info["version"] = im.version("PyJHora")
    except Exception as e:
        info["jhora_import"] = f"error: {e}"
        info["version"] = "unknown"
    return info

# -----------------------------
#   /chart (PyJHora za tekste; numeriko računamo TU) – TRUE NODE
# -----------------------------
@app.get("/chart")
def chart(
    name: str = Query(...),
    date: str = Query(...),     # YYYY-MM-DD (lokalni datum)
    time: str = Query(...),     # HH:MM (lokalni čas, 24h)
    place: str = Query(...),    # echo
    lat: float = Query(...),    # +N
    lon: float = Query(...),    # +E
    tz:  float = Query(...),    # ure (SLO: zima 1, poletje 2)
):
    # 1) PyJHora za tekst; če pade, gremo na Swiss-only spodaj
    try:
        from jhora.engine.astro_engine import run as jrun
        import swisseph as swe

        res = jrun(name, date, time, place)

        y, m, d = map(int, date.split("-"))
        hh, mm = map(int, time.split(":"))
        jd_ut = swe.julday(y, m, d, (hh + mm/60.0) - tz, swe.GREG_CAL)

        # Ascendant degree (za bhave)
        ascmc, _ = swe.houses_ex(jd_ut, lat, lon, b'P')
        asc_deg = ascmc[0]

        lons = _sidereal_longitudes_true(jd_ut)
        kar8 = _chara_karakas_8(lons)
        bhavas = _planets_by_bhava(lons, asc_deg)

        return {
            "source": "PyJHora+CK(TrueNode+Lahiri)",
            "ascendant": res["summary"]["ascendant"]["text"],
            "moon_nakshatra": res["summary"]["moon_nakshatra"],
            "chara_karakas": kar8,               # 🔹 samo 8-karaka
            "asc_degree": round(asc_deg, 2),
            "bhavas": bhavas,
            "planets_by_house": _invert_dict_list(bhavas)
        }
    except Exception:
        pass

    # 2) Fallback: Swiss Ephemeris (True Node + Lahiri)
    try:
        import swisseph as swe
        y, m, d = map(int, date.split("-"))
        hh, mm = map(int, time.split(":"))
        jd_ut = swe.julday(y, m, d, (hh + mm/60.0) - tz, swe.GREG_CAL)

        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

        # Luna & nakšatra (informativno)
        moon_lon = swe.calc_ut(jd_ut, swe.MOON, flag)[0][0]
        idx = int((moon_lon / 360.0) * 27.0) % 27
        nak = NAKSHATRAS[idx]

        # Ascendant (za bhave)
        ascmc, _ = swe.houses_ex(jd_ut, lat, lon, b'P')
        asc_deg = ascmc[0]
        zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                  "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
        asc_sign = zodiac[int(asc_deg // 30)]

        lons = _sidereal_longitudes_true(jd_ut)
        kar8 = _chara_karakas_8(lons)
        bhavas = _planets_by_bhava(lons, asc_deg)

        return {
            "source": "SwissEphemeris(TrueNode+Lahiri)",
            "echo": {"name": name, "place": place},
            "ascendant": {"degree": round(asc_deg, 2), "sign": asc_sign},
            "moon": {"longitude": round(moon_lon, 2), "nakshatra": nak},
            "chara_karakas": kar8,
            "bhavas": bhavas,
            "planets_by_house": _invert_dict_list(bhavas)
        }
    except Exception as e:
        return {"error": f"fallback_failed: {e}"}

# -----------------------------
#   chart_smart (SLO mesta)
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
    if p in CITY_DB: return CITY_DB[p]
    for name, tpl in CITY_DB.items():
        if name in p: return tpl
    return None

@app.get("/chart_smart")
def chart_smart(name: str, date: str, time: str, place: str):
    city = _find_city(place)
    if not city:
        return {"error":"unknown_place","hint":"Uporabi eno izmed: "+", ".join(CITY_DB.keys())}
    lat,lon,tzid = city
    y,m,d = map(int, date.split("-")); hh,mm = map(int, time.split(":"))
    local_dt = datetime(y,m,d,hh,mm,tzinfo=ZoneInfo(tzid))
    tz_off = local_dt.utcoffset().total_seconds()/3600.0
    return chart(name=name,date=date,time=time,place=place,lat=lat,lon=lon,tz=tz_off)

# -----------------------------
#   chart_global (geocoder)
# -----------------------------
def _geocode_global(place: str) -> Tuple[Optional[Tuple[float,float,str]], Optional[List[str]]]:
    import geonamescache
    from timezonefinder import TimezoneFinder
    raw = (place or "").strip()
    if not raw: return None,None
    norm = raw.replace(" ,",",").replace(", ",",")
    parts = norm.split(",")
    if len(parts)==2:
        city_raw,country_raw = parts[0].strip(),parts[1].strip()
        cc_map = {"slovenia":"SI","slovenija":"SI","austria":"AT","österreich":"AT","oesterreich":"AT",
                  "croatia":"HR","hrvatska":"HR","italy":"IT","italia":"IT",
                  "germany":"DE","deutschland":"DE"}
        country_cc = cc_map.get(country_raw.lower(),country_raw.upper())
        p = f"{city_raw}, {country_cc}".lower()
    else:
        p = raw.lower()
    gc = geonamescache.GeonamesCache(); cities = gc.get_cities()
    def name_cc(c): return f"{c['name']}, {c['countrycode']}"
    candidates=[c for c in cities.values() if p in name_cc(c).lower()]
    if not candidates: return None,None
    uniq={ (c["name"],c["countrycode"]):c for c in candidates }.values()
    if len(uniq)>1:
        opts=[name_cc(c) for c in sorted(uniq,key=lambda x:x.get("population",0),reverse=True)[:7]]
        return None,opts
    c=list(uniq)[0]
    lat,lon=float(c["latitude"]),float(c["longitude"])
    tzid=TimezoneFinder().timezone_at(lng=lon,lat=lat)
    if not tzid: return None,[name_cc(c)]
    return (lat,lon,tzid),None

@app.get("/chart_global")
def chart_global(name: str, date: str, time: str, place: str):
    if "," not in place:
        return {"error":"country_required","hint":"Uporabi 'City, CC' (npr. 'Paris, FR')"}
    geo,opts=_geocode_global(place)
    if opts: return {"error":"place_ambiguous","options":opts}
    if not geo: return {"error":"place_not_found"}
    lat,lon,tzid=geo
    y,m,d=map(int,date.split("-")); hh,mm=map(int,time.split(":"))
    local_dt=datetime(y,m,d,hh,mm,tzinfo=ZoneInfo(tzid))
    tz_off=local_dt.utcoffset().total_seconds()/3600.0
    return chart(name=name,date=date,time=time,place=place,lat=lat,lon=lon,tz=tz_off)
