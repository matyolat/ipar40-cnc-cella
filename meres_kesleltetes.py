import csv
import json
import statistics
import time

import paho.mqtt.client as mqtt

TEMA = "meres/kesleltetes"
N = 1000
FREKVENCIAK = [10, 100, 1000]
QOS_LISTA = [0, 1, 2]

erkezett = {}


def on_message(c, u, msg):
    most = time.perf_counter()
    d = json.loads(msg.payload)
    erkezett[d["seq"]] = (most - d["t"]) * 1000.0


def meres(qos, frek):
    erkezett.clear()
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="meres_sub")
    sub.on_message = on_message
    sub.connect("localhost", 1883)
    sub.subscribe(TEMA, qos=qos)
    sub.loop_start()
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="meres_pub")
    pub.connect("localhost", 1883)
    pub.loop_start()
    time.sleep(1)

    minta = {"allapot": "FUT", "orso_hom_C": 47.9, "rezges_mm_s": 1.81, "darab": 120, "selejt": 2}
    periodus = 1.0 / frek
    kov = time.perf_counter()
    for i in range(N):
        d = dict(minta, seq=i, t=time.perf_counter())
        pub.publish(TEMA, json.dumps(d), qos=qos)
        kov += periodus
        var = kov - time.perf_counter()
        if var > 0:
            time.sleep(var)
    time.sleep(2)

    pub.loop_stop(); pub.disconnect()
    sub.loop_stop(); sub.disconnect()
    return list(erkezett.values())


def percentilis(lista, p):
    s = sorted(lista)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


if __name__ == "__main__":
    sorok = []
    nyers = open("meresek/kesleltetes_nyers.csv", "w", newline="")
    w = csv.writer(nyers, delimiter=";")
    w.writerow(["qos", "frek_hz", "kesleltetes_ms"])
    for qos in QOS_LISTA:
        for frek in FREKVENCIAK:
            k = meres(qos, frek)
            for x in k:
                w.writerow([qos, frek, round(x, 4)])
            sor = [qos, frek, len(k), N - len(k), min(k), statistics.mean(k), statistics.median(k),
                   percentilis(k, 95), percentilis(k, 99), max(k)]
            sorok.append(sor)
            print("QoS %d %5d Hz: n=%d elveszett=%d min=%.3f atl=%.3f med=%.3f p95=%.3f p99=%.3f max=%.3f ms" % tuple(sor))
    nyers.close()

    with open("meresek/kesleltetes_osszesito.csv", "w", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["qos", "frek_hz", "n", "elveszett", "min_ms", "atlag_ms", "median_ms", "p95_ms", "p99_ms", "max_ms"])
        for s in sorok:
            w.writerow([s[0], s[1], s[2], s[3]] + [round(x, 3) for x in s[4:]])
