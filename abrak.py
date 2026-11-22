import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from szamitas import CellaFigyelo
from szimulator import CncGep

KI = "doksi/abrak/"
plt.rcParams.update({"font.size": 10, "font.family": "serif"})


def beolvas(fajl):
    with open(fajl, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def kesleltetes_boxplot():
    sorok = beolvas("meresek/kesleltetes_nyers.csv")
    adatok, cimkek = [], []
    for qos in ["0", "1", "2"]:
        for frek in ["10", "100", "1000"]:
            adatok.append([float(s["kesleltetes_ms"]) for s in sorok if s["qos"] == qos and s["frek_hz"] == frek])
            cimkek.append("QoS %s\n%s Hz" % (qos, frek))
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.boxplot(adatok, tick_labels=cimkek, showfliers=False, whis=(1, 99))
    ax.set_ylabel("késleltetés [ms]")
    ax.set_title("Publikáló → broker → feliratkozó késleltetés (n = 1000 / eset)")
    ax.grid(axis="y", alpha=0.4)
    fig.tight_layout()
    fig.savefig(KI + "kesleltetes_boxplot.png", dpi=200)


def tulmelegedes():
    gep = CncGep(seed=5, veletlen_allas=False)
    fig_ = CellaFigyelo()
    t, hom = [], []
    riasztas_t = leallas_t = None
    for i in range(900):
        if i == 300:
            gep.parancs("tulmelegedes")
        m = gep.lepes(1.0)
        for e in fig_.minta(m):
            if e["tipus"] == "orso_hom_C" and e["allapot"] == "be" and riasztas_t is None:
                riasztas_t = m["t"]
            if e["tipus"] == "gephiba" and leallas_t is None:
                leallas_t = m["t"]
        t.append(m["t"])
        hom.append(m["orso_hom_C"])

    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(t, hom, lw=1, label="orsóhőmérséklet")
    ax.axhline(75, color="orange", ls="--", lw=1, label="riasztási határ (75 °C)")
    ax.axhline(90, color="red", ls="--", lw=1, label="védelmi leállás (90 °C)")
    ax.axvline(300, color="gray", ls=":", lw=1)
    ax.text(305, 25, "hiba\ninjektálása", fontsize=8, color="gray")
    ax.axvline(riasztas_t, color="orange", lw=1)
    ax.axvline(leallas_t, color="red", lw=1)
    ax.annotate("", xy=(leallas_t, 60), xytext=(riasztas_t, 60), arrowprops=dict(arrowstyle="<->"))
    ax.text((riasztas_t + leallas_t) / 2, 62, "%d s" % (leallas_t - riasztas_t), ha="center")
    ax.set_xlabel("idő [s]")
    ax.set_ylabel("hőmérséklet [°C]")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.4)
    fig.tight_layout()
    fig.savefig(KI + "tulmelegedes.png", dpi=200)
    print("riasztas:", riasztas_t, "leallas:", leallas_t)


def oee_ido(fajl):
    sorok = beolvas(fajl)
    t = [float(s["tervezett_s"]) / 60 for s in sorok]
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for k, nev in [("A", "rendelkezésre állás"), ("P", "teljesítmény"), ("Q", "minőség"), ("OEE", "OEE")]:
        ax.plot(t, [float(s[k]) * 100 for s in sorok], lw=1.8 if k == "OEE" else 1, label=nev)
    ax.set_xlabel("eltelt idő [perc]")
    ax.set_ylabel("[%]")
    ax.set_ylim(0, 105)
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.4)
    fig.tight_layout()
    fig.savefig(KI + "oee_ido.png", dpi=200)
    u = sorok[-1]
    print("utolso kpi:", u)


def feldolgozo_kesleltetes(fajl):
    k = sorted(float(s["kesleltetes_ms"]) for s in beolvas(fajl))
    n = len(k)
    print("feldolgozo kesleltetes n=%d med=%.3f p95=%.3f p99=%.3f max=%.3f ms" % (
        n, k[n // 2], k[int(n * 0.95)], k[int(n * 0.99)], k[-1]))
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.hist(k, bins=50, range=(0, k[int(n * 0.99)] * 1.5))
    ax.set_xlabel("szimulátor → feldolgozó késleltetés [ms]")
    ax.set_ylabel("darab")
    ax.grid(alpha=0.4)
    fig.tight_layout()
    fig.savefig(KI + "feldolgozo_kesleltetes.png", dpi=200)


if __name__ == "__main__":
    kesleltetes_boxplot()
    tulmelegedes()
    if len(sys.argv) > 2:
        oee_ido(sys.argv[1])
        feldolgozo_kesleltetes(sys.argv[2])
