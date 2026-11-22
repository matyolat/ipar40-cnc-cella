import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from szamitas import CellaFigyelo, Hatarertek


def minta(t, allapot="FUT", hom=40.0, rezges=1.8, darab=0, selejt=0):
    return {"t": t, "allapot": allapot, "orso_hom_C": hom, "rezges_mm_s": rezges,
            "darab": darab, "selejt": selejt}


def test_hatarertek_hiszterezis():
    h = Hatarertek("x", 75, 5)
    assert h.ellenoriz(70) is None
    assert h.ellenoriz(76) == "be"
    assert h.ellenoriz(80) is None
    assert h.ellenoriz(72) is None
    assert h.ellenoriz(69.9) == "ki"


def test_rendelkezesre_allas():
    f = CellaFigyelo()
    for t in range(0, 101):
        f.minta(minta(t, "FUT" if t < 60 else "ALL"))
    k = f.kpi()
    assert k["tervezett_ido_s"] == 100
    assert k["futasi_ido_s"] == 60
    assert abs(k["rendelkezesre_allas"] - 0.6) < 1e-9


def test_teljesitmeny_es_minoseg():
    f = CellaFigyelo(ciklusido=30)
    for t in range(0, 121):
        f.minta(minta(t, darab=t // 40, selejt=1 if t >= 80 else 0))
    k = f.kpi()
    assert k["darab"] == 3
    assert abs(k["teljesitmeny"] - 0.75) < 1e-9
    assert abs(k["minoseg"] - 2 / 3) < 1e-3
    assert abs(k["oee"] - 1.0 * 0.75 * (2 / 3)) < 1e-3


def test_kimaradt_adat_allasnak_szamit():
    f = CellaFigyelo()
    f.minta(minta(0))
    f.minta(minta(10))
    f.minta(minta(40))
    k = f.kpi()
    assert k["tervezett_ido_s"] == 40
    assert k["futasi_ido_s"] == 10


def test_szamlalo_nullazodas():
    f = CellaFigyelo()
    f.minta(minta(0, darab=5))
    f.minta(minta(1, darab=8))
    f.minta(minta(2, darab=1))
    assert f.darab() == 3 + 1 + 0


def test_riasztas_esemenyek():
    f = CellaFigyelo()
    assert f.minta(minta(0, hom=50)) == []
    e = f.minta(minta(1, hom=78))
    assert e[0]["tipus"] == "orso_hom_C" and e[0]["allapot"] == "be"
    e = f.minta(minta(2, hom=79, rezges=5.2))
    assert len(e) == 1 and e[0]["tipus"] == "rezges_mm_s"
    e = f.minta(minta(3, allapot="HIBA", hom=91, rezges=0.1))
    tipusok = [x["tipus"] for x in e]
    assert "gephiba" in tipusok and "rezges_mm_s" in tipusok
