IDEALIS_CIKLUSIDO = 30.0
MAX_DT = 10.0


class Hatarertek:

    def __init__(self, nev, hatar, hiszterezis):
        self.nev = nev
        self.hatar = hatar
        self.hiszterezis = hiszterezis
        self.aktiv = False

    def ellenoriz(self, ertek):
        if not self.aktiv and ertek > self.hatar:
            self.aktiv = True
            return "be"
        if self.aktiv and ertek < self.hatar - self.hiszterezis:
            self.aktiv = False
            return "ki"
        return None


class CellaFigyelo:

    def __init__(self, ciklusido=IDEALIS_CIKLUSIDO):
        self.ciklusido = ciklusido
        self.tervezett_ido = 0.0
        self.futasi_ido = 0.0
        self.elozo_t = None
        self.allapot = None

        self.kezdo_darab = None
        self.nyers_darab = 0
        self.nyers_selejt = 0
        self.eltolas_darab = 0
        self.eltolas_selejt = 0
        self.kezdo_selejt = 0

        self.hatarok = [
            Hatarertek("orso_hom_C", 75.0, 5.0),
            Hatarertek("rezges_mm_s", 4.5, 0.5),
        ]

    def minta(self, m):
        esemenyek = []

        if self.elozo_t is not None:
            dt = m["t"] - self.elozo_t
            if dt > 0:
                self.tervezett_ido += dt
                if self.allapot == "FUT" and dt <= MAX_DT:
                    self.futasi_ido += dt
        self.elozo_t = m["t"]

        if m["allapot"] != self.allapot:
            if m["allapot"] == "HIBA":
                esemenyek.append({"tipus": "gephiba", "allapot": "be", "ertek": None, "hatar": None})
            elif self.allapot == "HIBA":
                esemenyek.append({"tipus": "gephiba", "allapot": "ki", "ertek": None, "hatar": None})
            self.allapot = m["allapot"]

        if self.kezdo_darab is None:
            self.kezdo_darab = m["darab"]
            self.kezdo_selejt = m["selejt"]
        if m["darab"] < self.nyers_darab:
            self.eltolas_darab += self.nyers_darab
            self.eltolas_selejt += self.nyers_selejt
        self.nyers_darab = m["darab"]
        self.nyers_selejt = m["selejt"]

        for h in self.hatarok:
            v = h.ellenoriz(m[h.nev])
            if v:
                esemenyek.append({"tipus": h.nev, "allapot": v, "ertek": m[h.nev], "hatar": h.hatar})

        return esemenyek

    def darab(self):
        return self.eltolas_darab + self.nyers_darab - self.kezdo_darab

    def selejt(self):
        return self.eltolas_selejt + self.nyers_selejt - self.kezdo_selejt

    def kpi(self):
        if self.kezdo_darab is None:
            return None
        darab = self.darab()
        selejt = self.selejt()

        a = self.futasi_ido / self.tervezett_ido if self.tervezett_ido > 0 else 0.0
        p = darab * self.ciklusido / self.futasi_ido if self.futasi_ido > 0 else 0.0
        p = min(p, 1.0)
        q = (darab - selejt) / darab if darab > 0 else 1.0

        return {
            "rendelkezesre_allas": round(a, 4),
            "teljesitmeny": round(p, 4),
            "minoseg": round(q, 4),
            "oee": round(a * p * q, 4),
            "darab": darab,
            "selejt": selejt,
            "futasi_ido_s": round(self.futasi_ido, 1),
            "tervezett_ido_s": round(self.tervezett_ido, 1),
            "allapot": self.allapot,
        }
