import astro_engine as ae

def generate_chart(name, date, time, place):
    """
    Uporabi PyJHora engine za izračun astrološke karte.
    """
    res = ae.run(name, date, time, place)
    return {
        "ascendant": res["summary"]["ascendant"]["text"],
        "moon_nakshatra": res["summary"]["moon_nakshatra"],
        "chara_karakas": res["summary"]["chara_karakas"]
    }
