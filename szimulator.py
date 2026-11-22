import argparse
import json
import random
import time

import paho.mqtt.client as mqtt

TEMA = "cella1/cnc1"


class CncGep:

    def __init__(self, seed=None, veletlen_allas=True):
        self.rnd = random.Random(seed)
        self.veletlen_allas = veletlen_allas
        self.t = 0.0
        self.allapot = "FUT"
        self.hom = 22.0
        self.darab = 0
        self.selejt = 0
        self.ciklusido = 30.0
        self.ciklus = 0.0
        self.hiba = None
        self.allas_vege = None
        self.halozat_hiba = False

    def parancs(self, p):
        if p == "leallas":
            self.allapot = "ALL"
            self.allas_vege = None
        elif p == "inditas":
            if self.allapot != "HIBA":
                self.allapot = "FUT"
        elif p in ("tulmelegedes", "rezges"):
            self.hiba = p
        elif p == "halozat":
            self.halozat_hiba = True
        elif p == "normal":
            self.hiba = None
            if self.allapot == "HIBA":
                self.allapot = "ALL"
        else:
            print("ismeretlen parancs:", p)

    def lepes(self, dt):
        self.t += dt

        if self.veletlen_allas:
            if self.allapot == "FUT" and self.rnd.random() < 0.003 * dt:
                self.allapot = "ALL"
                self.allas_vege = self.t + self.rnd.uniform(20, 90)
            elif self.allapot == "ALL" and self.allas_vege and self.t >= self.allas_vege:
                self.allapot = "FUT"
                self.allas_vege = None

        if self.allapot == "FUT":
            cel = 95.0 if self.hiba == "tulmelegedes" else 48.0
        else:
            cel = 22.0
        self.hom += (cel - self.hom) * dt / 120.0

        if self.hom > 90.0 and self.allapot == "FUT":
            self.allapot = "HIBA"

        if self.allapot == "FUT":
            if self.hiba == "rezges":
                rezges = self.rnd.gauss(6.0, 0.5)
            else:
                rezges = self.rnd.gauss(1.8, 0.15)
        else:
            rezges = abs(self.rnd.gauss(0.05, 0.02))

        if self.allapot == "FUT":
            self.ciklus += dt * self.rnd.uniform(0.88, 1.0)
            if self.ciklus >= self.ciklusido:
                self.ciklus -= self.ciklusido
                self.darab += 1
                p_selejt = 0.15 if self.hiba == "rezges" else 0.02
                if self.rnd.random() < p_selejt:
                    self.selejt += 1

        hom_mert = self.hom + self.rnd.gauss(0, 0.2)

        return {
            "t": round(self.t, 2),
            "allapot": self.allapot,
            "orso_hom_C": round(hom_mert, 1),
            "rezges_mm_s": round(max(rezges, 0), 2),
            "darab": self.darab,
            "selejt": self.selejt,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--periodus", type=float, default=1.0, help="mintaveteli ido valos s-ban")
    ap.add_argument("--gyorsitas", type=float, default=1.0, help="szimulalt ido szorzoja")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--nincs-veletlen-allas", action="store_true")
    ap.add_argument("--qos", type=int, default=0)
    args = ap.parse_args()

    gep = CncGep(args.seed, not args.nincs_veletlen_allas)

    def on_connect(client, userdata, flags, rc, props):
        print("kapcsolodva:", rc)
        client.subscribe(TEMA + "/parancs", qos=1)
        client.publish(TEMA + "/kapcsolat", "online", qos=1, retain=True)

    def on_message(client, userdata, msg):
        try:
            p = json.loads(msg.payload)["parancs"]
        except (ValueError, KeyError):
            print("hibas parancs:", msg.payload)
            return
        print("parancs:", p)
        gep.parancs(p)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cnc1_szimulator")
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(TEMA + "/kapcsolat", "offline", qos=1, retain=True)
    client.connect(args.broker, 1883, keepalive=5)
    client.loop_start()

    dt = args.periodus * args.gyorsitas
    seq = 0
    kieses_vege = None
    kovetkezo = time.monotonic()
    try:
        while True:
            adat = gep.lepes(dt)
            adat["seq"] = seq
            adat["ts"] = time.time()
            seq += 1

            if gep.halozat_hiba:
                gep.halozat_hiba = False
                kieses_vege = time.monotonic() + 15
                client.loop_stop()
                print("halozati kieses 15 s")
            if kieses_vege:
                if time.monotonic() >= kieses_vege:
                    kieses_vege = None
                    client.loop_start()
                    print("halozat vissza")
            else:
                client.publish(TEMA + "/telemetria", json.dumps(adat), qos=args.qos)

            kovetkezo += args.periodus
            var = kovetkezo - time.monotonic()
            if var > 0:
                time.sleep(var)
    except KeyboardInterrupt:
        pass
    info = client.publish(TEMA + "/kapcsolat", "offline", qos=1, retain=True)
    info.wait_for_publish(2)
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
