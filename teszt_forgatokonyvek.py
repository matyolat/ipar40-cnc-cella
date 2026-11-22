import json
import subprocess
import sys
import time

import paho.mqtt.client as mqtt

TEMA = "cella1/cnc1"
SZIM = [sys.executable, "szimulator.py", "--periodus", "0.1", "--gyorsitas", "10",
        "--seed", "7", "--nincs-veletlen-allas"]
eredmenyek = []


class Figyelo:
    def __init__(self):
        self.riasztasok = []
        self.kpi = []
        self.telemetria = []
        self.kapcsolat = []
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="teszt_figyelo")
        self.c.on_message = self.uzenet
        self.c.connect("localhost", 1883)
        self.c.subscribe(TEMA + "/#", qos=1)
        self.c.loop_start()

    def uzenet(self, c, u, msg):
        most = time.time()
        if msg.retain:
            return
        if msg.topic.endswith("/kapcsolat") or msg.topic.endswith("/feldolgozo"):
            self.kapcsolat.append((most, msg.topic.split("/")[-1], msg.payload.decode()))
            return
        if msg.topic.endswith("/parancs"):
            return
        d = json.loads(msg.payload)
        d["_erkezett"] = most
        if msg.topic.endswith("/riasztas"):
            self.riasztasok.append(d)
        elif msg.topic.endswith("/kpi"):
            self.kpi.append(d)
        elif msg.topic.endswith("/telemetria"):
            self.telemetria.append(d)

    def parancs(self, p):
        self.c.publish(TEMA + "/parancs", json.dumps({"parancs": p}), qos=1)

    def var_riasztasra(self, tipus, allapot, max_ido):
        hatar = time.time() + max_ido
        while time.time() < hatar:
            for r in self.riasztasok:
                if r["tipus"] == tipus and r["allapot"] == allapot:
                    return r
            time.sleep(0.05)
        return None

    def leall(self):
        self.c.loop_stop()
        self.c.disconnect()


def var_onlinera(fig, ki, max_ido=20):
    hatar = time.time() + max_ido
    while time.time() < hatar:
        if any(k == ki and p == "online" for t, k, p in fig.kapcsolat):
            return
        time.sleep(0.05)
    raise RuntimeError(ki + " nem indult el")


def indit(fig):
    f = subprocess.Popen([sys.executable, "feldolgozo.py"], stdout=subprocess.DEVNULL)
    var_onlinera(fig, "feldolgozo")
    s = subprocess.Popen(SZIM, stdout=subprocess.DEVNULL)
    var_onlinera(fig, "kapcsolat")
    return f, s


def eredmeny(nev, elvart, kapott, ok):
    sor = "%-28s | elvart: %-34s | kapott: %-34s | %s" % (nev, elvart, kapott, "OK" if ok else "HIBA")
    print(sor)
    eredmenyek.append(sor)


def t1_normal():
    fig = Figyelo()
    f, s = indit(fig)
    time.sleep(31)
    k = fig.kpi[-1]
    eredmeny("T1 normal mukodes", "nincs riasztas", "%d riasztas" % len(fig.riasztasok),
             len(fig.riasztasok) == 0)
    eredmeny("T1 rendelkezesre allas", "A = 1.00", "A = %.3f" % k["rendelkezesre_allas"],
             k["rendelkezesre_allas"] > 0.99)
    eredmeny("T1 OEE", "0.85 < OEE <= 1", "OEE = %.3f" % k["oee"], 0.85 < k["oee"] <= 1)
    s.kill(); f.kill(); fig.leall()


def t2_leallas():
    fig = Figyelo()
    f, s = indit(fig)
    time.sleep(10)
    fig.parancs("leallas")
    time.sleep(10)
    fig.parancs("inditas")
    time.sleep(10)
    s.kill()
    time.sleep(6)
    tel = fig.telemetria
    fut = sum(1 for a, b in zip(tel, tel[1:]) if a["allapot"] == "FUT")
    a_sajat = fut / (len(tel) - 1)
    k = fig.kpi[-1]
    eredmeny("T2 leallas, A (elmeleti)", "A = 0.667 +- 0.05", "A = %.3f" % k["rendelkezesre_allas"],
             abs(k["rendelkezesre_allas"] - 2 / 3) < 0.05)
    eredmeny("T2 leallas, A (fuggetlen)", "A = %.3f +- 0.01" % a_sajat, "A = %.3f" % k["rendelkezesre_allas"],
             abs(k["rendelkezesre_allas"] - a_sajat) < 0.01)
    f.kill(); fig.leall()


def t3_tulmelegedes():
    fig = Figyelo()
    f, s = indit(fig)
    time.sleep(5)
    fig.parancs("tulmelegedes")
    r = fig.var_riasztasra("orso_hom_C", "be", 30)
    g = fig.var_riasztasra("gephiba", "be", 30)
    ok = r is not None and r["ertek"] > 75
    eredmeny("T3 tulmelegedes riasztas", "riasztas, T > 75 C", "T = %s C" % (r["ertek"] if r else "-"), ok)
    if r and g:
        t_r = next(x["t"] for x in fig.telemetria if x["ts"] == r["ts_minta"])
        t_g = next(x["t"] for x in fig.telemetria if x["ts"] == g["ts_minta"])
        eredmeny("T3 elorejelzesi ido", "riasztas a leallas elott", "%.0f s-mal elotte (szim. ido)" % (t_g - t_r),
                 t_g > t_r)
    else:
        eredmeny("T3 elorejelzesi ido", "riasztas a leallas elott", "nem jott gephiba", False)
    s.kill(); f.kill(); fig.leall()


def t4_rezges():
    fig = Figyelo()
    f, s = indit(fig)
    time.sleep(5)
    t0 = time.time()
    fig.parancs("rezges")
    r = fig.var_riasztasra("rezges_mm_s", "be", 5)
    eredmeny("T4 rezges riasztas", "riasztas < 1 s alatt",
             "%.2f s, %s mm/s" % (r["_erkezett"] - t0, r["ertek"]) if r else "nincs", r is not None and r["_erkezett"] - t0 < 1)
    time.sleep(10)
    fig.parancs("normal")
    r2 = fig.var_riasztasra("rezges_mm_s", "ki", 5)
    eredmeny("T4 rezges megszunik", "riasztas 'ki' allapot", "megjott" if r2 else "nem jott", r2 is not None)
    s.kill(); f.kill(); fig.leall()


def t5_kapcsolatkieses():
    fig = Figyelo()
    f, s = indit(fig)
    time.sleep(5)
    t0 = time.time()
    s.kill()
    r = fig.var_riasztasra("kapcsolat", "be", 15)
    time.sleep(4)
    lwt = [t for t, k, p in fig.kapcsolat if k == "kapcsolat" and p == "offline"]
    eredmeny("T5 folyamat leall", "riasztas < 8 s", "%.2f s (%s)" % (r["_erkezett"] - t0, r["ertek"]) if r else "nincs",
             r is not None and r["_erkezett"] - t0 < 8)
    eredmeny("T5 LWT uzenet", "offline < 8 s (keepalive 5 s)", "%.2f s" % (lwt[0] - t0) if lwt else "nincs",
             bool(lwt) and lwt[0] - t0 < 8)
    f.kill(); fig.leall()


def t6_halozatkieses():
    fig = Figyelo()
    f, s = indit(fig)
    time.sleep(5)
    t0 = time.time()
    fig.parancs("halozat")
    r = fig.var_riasztasra("kapcsolat", "be", 12)
    time.sleep(13)
    lwt = [t for t, k, p in fig.kapcsolat if k == "kapcsolat" and p == "offline"]
    vissza = fig.var_riasztasra("kapcsolat", "ki", 8)
    eredmeny("T6 halozatkieses, watchdog", "riasztas 5-6 s kozott",
             "%.2f s (%s)" % (r["_erkezett"] - t0, r["ertek"]) if r else "nincs",
             r is not None and 5 <= r["_erkezett"] - t0 <= 6)
    eredmeny("T6 LWT uzenet", "offline kb. 7,5 s (1,5 x keepalive)", "%.2f s" % (lwt[0] - t0) if lwt else "nincs",
             bool(lwt) and 5 < lwt[0] - t0 < 10)
    eredmeny("T6 helyreallas", "riasztas 'ki' kb. 15 s utan",
             "%.2f s" % (vissza["_erkezett"] - t0) if vissza else "nincs", vissza is not None)
    s.kill(); f.kill(); fig.leall()


if __name__ == "__main__":
    for t in [t1_normal, t2_leallas, t3_tulmelegedes, t4_rezges, t5_kapcsolatkieses, t6_halozatkieses]:
        print("---", t.__name__)
        t()
        time.sleep(1)
    with open("meresek/teszt_eredmenyek.txt", "w", encoding="utf-8") as fajl:
        fajl.write(time.strftime("%Y-%m-%d %H:%M") + "\n")
        fajl.write("\n".join(eredmenyek) + "\n")
    print("\nOK:", sum("| OK" in e for e in eredmenyek), "/", len(eredmenyek))
