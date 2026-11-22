# CNC cella állapotfigyelés MQTT-vel

Ipar 4.0 technológiák (GKNB_INTM087) féléves házi feladat, 2026/27/1.

Egy szoftveresen szimulált CNC megmunkáló cella adatait (gépállapot, orsóhőmérséklet, rezgés, darabszám) MQTT-n küldöm egy Mosquitto brokerre. Egy Python feldolgozó ebből rendelkezésre állást és OEE-t számol, és riasztást küld, ha valami határérték felett van. Az egészet egy Node-RED műszerfal jeleníti meg, ahonnan hibát is lehet injektálni.

```
szimulator.py  --telemetria-->  Mosquitto  --> feldolgozo.py --kpi/riasztas--> Mosquitto
                <--parancs----   (1883)    --> Node-RED műszerfal (http://localhost:1880/dashboard)
```

## Ami kell hozzá

- Python 3.11+ (3.13-mal próbáltam)
- Mosquitto 2.x (Windowson winget: `winget install EclipseFoundation.Mosquitto`), alapbeállítással a localhost:1883-on figyel
- Node.js 18+ a Node-RED-hez

```
pip install -r requirements.txt
cd nodered
npm install
```

## Indítás

Négy külön terminálban (a broker Windowson szolgáltatásként is futhat):

```
mosquitto -v
python feldolgozo.py
python szimulator.py
cd nodered && npx node-red -u . flows.json
```

A műszerfal: http://localhost:1880/dashboard/cella1, a flow szerkesztő: http://localhost:1880

A szimulátor kapcsolói:

| kapcsoló | jelentés | alap |
|---|---|---|
| `--periodus` | mintavételi idő valós másodpercben | 1.0 |
| `--gyorsitas` | ennyiszer gyorsabban telik a szimulált idő | 1.0 |
| `--seed` | véletlenszám mag (ismételhető futás) | nincs |
| `--nincs-veletlen-allas` | kikapcsolja a véletlen rövid állásokat | |
| `--qos` | telemetria QoS szintje | 0 |

## MQTT témák

| téma | irány | tartalom |
|---|---|---|
| `cella1/cnc1/telemetria` | szimulátor → | JSON: `seq, ts, t, allapot, orso_hom_C, rezges_mm_s, darab, selejt` (1 Hz) |
| `cella1/cnc1/kapcsolat` | szimulátor → | `online` / `offline` (retained, az offline az LWT) |
| `cella1/cnc1/parancs` | → szimulátor | `{"parancs": "inditas" / "leallas" / "tulmelegedes" / "rezges" / "halozat" / "normal"}` |
| `cella1/cnc1/kpi` | feldolgozó → | A, P, Q, OEE, darab, selejt, idők (5 s-onként, retained) |
| `cella1/cnc1/riasztas` | feldolgozó → | `tipus, allapot (be/ki), ertek, hatar` |
| `cella1/cnc1/feldolgozo` | feldolgozó → | `online` / `offline` |

Kézzel is lehet parancsot küldeni:

```
mosquitto_pub -t cella1/cnc1/parancs -m "{\"parancs\": \"tulmelegedes\"}"
```

## Tesztek

```
python -m pytest tests          # egységtesztek a számításra (nem kell broker)
python teszt_forgatokonyvek.py  # T1-T6 forgatókönyvek, kell a futó broker, kb. 3 perc
python meres_kesleltetes.py     # késleltetésmérés QoS 0/1/2 és 10/100/1000 Hz mellett
python abrak.py naplo\kpi_....csv naplo\kesleltetes_....csv   # grafikonok
```

Az eredmények a `meresek/` mappába kerülnek, a feldolgozó naplói a `naplo/` mappába.

## Fájlok

- `szimulator.py` – a cella modellje és MQTT publikáló
- `feldolgozo.py` – feliratkozó, KPI, riasztás, watchdog, naplózás
- `szamitas.py` – az OEE és határérték logika (külön, hogy tesztelhető legyen)
- `nodered/flows.json` – a Node-RED műszerfal
- `doksi/abrak/` – draw.io ábrák (architektúra, DFD, SysML) és a grafikonok
