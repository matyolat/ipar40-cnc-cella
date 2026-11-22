import argparse
import csv
import json
import os
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

from szamitas import CellaFigyelo

TEMA = "cella1/cnc1"
KPI_PERIODUS = 5.0
TIMEOUT = 5.0

figyelo = CellaFigyelo()
zar = threading.Lock()
utolso_uzenet = None
kapcsolat_hiba = False


def naplo_nyit(nev, fejlec):
    os.makedirs("naplo", exist_ok=True)
    fajl = os.path.join("naplo", nev + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv")
    f = open(fajl, "w", newline="")
    w = csv.writer(f, delimiter=";")
    w.writerow(fejlec)
    return f, w


kesl_f, kesl_w = naplo_nyit("kesleltetes", ["seq", "t", "kesleltetes_ms"])
riaszt_f, riaszt_w = naplo_nyit("riasztasok", ["ido", "tipus", "allapot", "ertek", "hatar"])
kpi_f, kpi_w = naplo_nyit("kpi", ["ido", "tervezett_s", "futasi_s", "A", "P", "Q", "OEE", "darab", "selejt"])


def riasztas(client, tipus, allapot, ertek=None, hatar=None, ts_minta=None):
    uzenet = {
        "ts": time.time(),
        "ts_minta": ts_minta,
        "tipus": tipus,
        "allapot": allapot,
        "ertek": ertek,
        "hatar": hatar,
    }
    client.publish(TEMA + "/riasztas", json.dumps(uzenet), qos=1)
    ido = datetime.now().strftime("%H:%M:%S")
    riaszt_w.writerow([ido, tipus, allapot, ertek, hatar])
    riaszt_f.flush()
    print(ido, "RIASZTAS", tipus, allapot, ertek if ertek is not None else "")


def on_connect(client, userdata, flags, rc, props):
    print("kapcsolodva:", rc)
    client.subscribe(TEMA + "/telemetria")
    client.subscribe(TEMA + "/kapcsolat", qos=1)
    client.publish(TEMA + "/feldolgozo", "online", qos=1, retain=True)


def on_message(client, userdata, msg):
    global utolso_uzenet, kapcsolat_hiba

    if msg.topic.endswith("/kapcsolat"):
        if msg.retain:
            return
        allapot = msg.payload.decode()
        print("szimulator:", allapot)
        if allapot == "offline" and not kapcsolat_hiba:
            kapcsolat_hiba = True
            riasztas(client, "kapcsolat", "be", ertek="lwt")
        return

    try:
        m = json.loads(msg.payload)
    except ValueError:
        print("hibas uzenet")
        return

    most = time.time()
    kesl = (most - m["ts"]) * 1000
    kesl_w.writerow([m["seq"], m["t"], round(kesl, 3)])

    with zar:
        utolso_uzenet = time.monotonic()
        if kapcsolat_hiba:
            kapcsolat_hiba = False
            riasztas(client, "kapcsolat", "ki")
        esemenyek = figyelo.minta(m)

    for e in esemenyek:
        riasztas(client, e["tipus"], e["allapot"], e["ertek"], e["hatar"], m["ts"])


def main():
    global kapcsolat_hiba
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    args = ap.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cnc1_feldolgozo")
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(TEMA + "/feldolgozo", "offline", qos=1, retain=True)
    client.connect(args.broker, 1883, keepalive=30)
    client.loop_start()

    kovetkezo_kpi = time.monotonic() + KPI_PERIODUS
    try:
        while True:
            time.sleep(0.2)
            most = time.monotonic()

            with zar:
                kiesett = utolso_uzenet is not None and most - utolso_uzenet > TIMEOUT
                if kiesett and not kapcsolat_hiba:
                    kapcsolat_hiba = True
                    riasztas(client, "kapcsolat", "be", ertek="timeout")

            if most >= kovetkezo_kpi:
                kovetkezo_kpi += KPI_PERIODUS
                with zar:
                    k = figyelo.kpi()
                if k:
                    k["ts"] = time.time()
                    k["kapcsolat"] = not kapcsolat_hiba
                    client.publish(TEMA + "/kpi", json.dumps(k), qos=1, retain=True)
                    kpi_w.writerow([datetime.now().strftime("%H:%M:%S"), k["tervezett_ido_s"], k["futasi_ido_s"],
                                    k["rendelkezesre_allas"], k["teljesitmeny"], k["minoseg"], k["oee"],
                                    k["darab"], k["selejt"]])
                    print("A=%.3f P=%.3f Q=%.3f OEE=%.3f darab=%d" % (
                        k["rendelkezesre_allas"], k["teljesitmeny"], k["minoseg"], k["oee"], k["darab"]))
                kesl_f.flush()
                kpi_f.flush()
    except KeyboardInterrupt:
        pass
    client.loop_stop()
    client.disconnect()
    kesl_f.close()
    riaszt_f.close()
    kpi_f.close()


if __name__ == "__main__":
    main()
