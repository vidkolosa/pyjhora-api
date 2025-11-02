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

KARAKA_ORDER_8 = ["AK", "AmK", "BK", "MK", "PK", "GK", "DK", "PiK"]

def _norm_name(key: str) -> str:
    k = key.strip().lower()
    return PLANET_MAP.get(k, key)

def _to_abs_deg(sign_index: int, deg_in_sign: float) -> float:
    """Absolute sidereal longitude 0–360 (Aries=0)."""
    return sign_index * 30.0 + deg_in_sign

def _effective_abs_for_rahu(sign_index: int, deg_in_sign: float) -> float:
    """
    Jaimini rule: for Rahu use (30 − deg_in_sign) inside sign => effectively
    its motion is retrograde. Equivalent to 360 − abs_longitude.
    """
    return sign_index * 30.0 + (30.0 - deg_in_sign)

def _extract_positions(res) -> dict:
    """
    Extract raw planet positions from result of astro_engine.run.
    Return dict:
      { "Sun": {"sign": int, "deg": float, "retro": bool}, ... }
    """
    src = res.get("positions") or res.get("planets") or {}
    if not src and isinstance(res.get("raw"), dict):
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

def compute_chara_karakas_8(positions: dict,
                             include_rahu: bool = True,
                             include_ketu: bool = False) -> dict:
    """
    Compute Chara Karakas in 8-karaka system:
      - Use sidereal absolute longitudes 0–360
      - If Rahu included: use its effective abs deg (_effective_abs_for_rahu)
      - Exclude Ketu if include_ketu=False
    Return e.g.: {"AK": "Rahu", "AmK": "Mars", ...}
    """
    usable = {}
    for name, pos in positions.items():
        if name == "Ketu" and not include_ketu:
            continue
        if name == "Rahu" and include_rahu:
            abs_deg = _effective_abs_for_rahu(pos["sign"], pos["deg"])
        else:
            abs_deg = _to_abs_deg(pos["sign"], pos["deg"])
        usable[name] = abs_deg % 360.0

    base_set = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"}
    if include_rahu:
        base_set.add("Rahu")

    filtered = {k: v for k, v in usable.items() if k in base_set}
    sorted_items = sorted(filtered.items(), key=lambda kv: kv[1], reverse=True)

    karakas = {}
    for i, (planet, _) in enumerate(sorted_items[:len(KARAKA_ORDER_8)]):
        karakas[KARAKA_ORDER_8[i]] = planet

    return karakas

# --- public API ------------------------------------------------------------

def generate_chart(name, date, time, place):
    """
    Use astro_engine to compute chart; then compute chara karakas.
    Returns dict:
      { "ascendant": ..., "moon_nakshatra": ..., "chara_karakas": {...} }
    """
    res = ae.run(name, date, time, place)
    positions = _extract_positions(res)
    if not positions:
        # fallback: use summary if available
        chara = res.get("summary", {}).get("chara_karakas")
    else:
        chara = compute_chara_karakas_8(positions, include_rahu=True, include_ketu=False)

    return {
        "ascendant": res["summary"]["ascendant"]["text"],
        "moon_nakshatra": res["summary"]["moon_nakshatra"],
        "chara_karakas": chara,
    }
