# astro.py
import astro_engine as ae

# --- helpers ---------------------------------------------------------------

PLANET_MAP = {
    "sun": "Sun", "su": "Sun",
    "moon": "Moon", "mo": "Moon",
    "mars": "Mars", "ma": "Mars",
    "mercury": "Mercury", "me": "Mercury",
    "jupiter": "Jupiter", "ju": "Jupiter",
    "venus": "Venus", "ve": "Venus",
    "saturn": "Saturn", "sa": "Saturn",
    "rahu": "Rahu", "ra": "Rahu",
    "ketu": "Ketu", "ke": "Ketu",
}

KARAKA_ORDER_7 = ["AK", "AmK", "BK", "MK", "PK", "GK", "DK"]

def _norm_name(key: str) -> str:
    k = key.strip().lower()
    return PLANET_MAP.get(k, key)

def _to_abs_deg(sign_index: int, deg_in_sign: float) -> float:
    """Absolute sidereal longitude 0–360 (Aries=0)."""
    return sign_index * 30.0 + deg_in_sign

def _effective_abs_for_rahu(sign_index: int, deg_in_sign: float) -> float:
    """
    Jaimini pravilo: za Rahuja vzamemo obratno stopinjo v znaku (30 - d),
    ker se giblje retrogradno. To je ekvivalentno 360 - abs_longitude.
    """
    return sign_index * 30.0 + (30.0 - deg_in_sign)

def _extract_positions(res) -> dict:
    """
    Poskusi izrezati surove pozicije planetov iz različnih možnih struktur,
    ki jih lahko vrne tvoj astro_engine.
    Vrne slovar:
      {
        "Sun": {"sign": int(0..11), "deg": float, "retro": bool},
        ...
      }
    """
    src = res.get("positions") or res.get("planets") or {}
    if not src and "raw" in res:
        src = res["raw"].get("positions") or res["raw"].get("planets") or {}

    out = {}
    for k, v in src.items():
        name = _norm_name(k)
        if isinstance(v, dict):
            sign = int(v.get("sign") or v.get("rasi") or v.get("sign_index") or 0)
            deg = float(v.get("longitude") or v.get("deg") or v.get("deg_in_sign") or 0.0)
            retro = bool(v.get("retro") or v.get("is_retro") or False)
            out[name] = {"sign": sign, "deg": deg, "retro": retro}
    return out

def compute_chara_karakas(positions: dict,
                          include_rahu: bool = True,
                          include_ketu: bool = False) -> dict:
    """
    Jaimini Čara Karake po JHora 7.32:
      - sidereal absolute longitude 0–360
      - Rahu oceni z obratno stopinjo v znaku (30 - d)
      - standardno: 7-karaka shema (Rahu vključen, Ketu izključen)
    Vrne npr.: {"AK": "Mars", "AmK": "Venus", ...}
    """
    usable = {}
    for name, pos in positions.items():
        if name == "Ketu" and not include_ketu:
            continue
        if name == "Rahu":
            abs_deg = _effective_abs_for_rahu(pos["sign"], pos["deg"])
        else:
            abs_deg = _to_abs_deg(pos["sign"], pos["deg"])
        usable[name] = abs_deg % 360.0

    base_set = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"}
    if include_rahu:
        base_set.add("Rahu")
    if not include_ketu and "Ketu" in usable:
        usable.pop("Ketu", None)

    filtered = {k: v for k, v in usable.items() if k in base_set}
    sorted_items = sorted(filtered.items(), key=lambda kv: kv[1], reverse=True)

    karakas = {}
    for i, (planet, _) in enumerate(sorted_items[:7]):
        karakas[KARAKA_ORDER_7[i]] = planet
    return karakas

# --- public API ------------------------------------------------------------

def generate_chart(name, date, time, place):
    """
    Uporabi astro_engine za izračun ter JHora-kompatibilen ponovni izračun Čara Karak.
    """
    res = ae.run(name, date, time, place)

    positions = _extract_positions(res)
    if not positions and hasattr(ae, "positions"):
        try:
            positions = _extract_positions({"positions": ae.positions(name, date, time, place)})
        except Exception:
            positions = {}

    if positions:
        chara_karakas = compute_chara_karakas(positions, include_rahu=True, include_ketu=False)
    else:
        chara_karakas = res.get("summary", {}).get("chara_karakas")

    return {
        "ascendant": res["summary"]["ascendant"]["text"],
        "moon_nakshatra": res["summary"]["moon_nakshatra"],
        "chara_karakas": chara_karakas,
    }
