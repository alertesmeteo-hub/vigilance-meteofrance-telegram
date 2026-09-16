import html
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

API = "https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours"
COLORS = {2: "🟡", 3: "🟠", 4: "🔴"}
PHENOMENA = {
    "1": "vent violent", "2": "pluie-inondation", "3": "orages",
    "4": "inondation", "5": "neige-verglas", "6": "canicule",
    "7": "grand froid", "8": "avalanches", "9": "vagues-submersion",
}
DEPARTMENTS = dict(pair.split("|", 1) for pair in """
01|Ain
02|Aisne
03|Allier
04|Alpes-de-Haute-Provence
05|Hautes-Alpes
06|Alpes-Maritimes
07|Ardèche
08|Ardennes
09|Ariège
10|Aube
11|Aude
12|Aveyron
13|Bouches-du-Rhône
14|Calvados
15|Cantal
16|Charente
17|Charente-Maritime
18|Cher
19|Corrèze
2A|Corse-du-Sud
2B|Haute-Corse
21|Côte-d'Or
22|Côtes-d'Armor
23|Creuse
24|Dordogne
25|Doubs
26|Drôme
27|Eure
28|Eure-et-Loir
29|Finistère
30|Gard
31|Haute-Garonne
32|Gers
33|Gironde
34|Hérault
35|Ille-et-Vilaine
36|Indre
37|Indre-et-Loire
38|Isère
39|Jura
40|Landes
41|Loir-et-Cher
42|Loire
43|Haute-Loire
44|Loire-Atlantique
45|Loiret
46|Lot
47|Lot-et-Garonne
48|Lozère
49|Maine-et-Loire
50|Manche
51|Marne
52|Haute-Marne
53|Mayenne
54|Meurthe-et-Moselle
55|Meuse
56|Morbihan
57|Moselle
58|Nièvre
59|Nord
60|Oise
61|Orne
62|Pas-de-Calais
63|Puy-de-Dôme
64|Pyrénées-Atlantiques
65|Hautes-Pyrénées
66|Pyrénées-Orientales
67|Bas-Rhin
68|Haut-Rhin
69|Rhône
70|Haute-Saône
71|Saône-et-Loire
72|Sarthe
73|Savoie
74|Haute-Savoie
75|Paris
76|Seine-Maritime
77|Seine-et-Marne
78|Yvelines
79|Deux-Sèvres
80|Somme
81|Tarn
82|Tarn-et-Garonne
83|Var
84|Vaucluse
85|Vendée
86|Vienne
87|Haute-Vienne
88|Vosges
89|Yonne
90|Territoire de Belfort
91|Essonne
92|Hauts-de-Seine
93|Seine-Saint-Denis
94|Val-de-Marne
95|Val-d'Oise
""".strip().splitlines())


def need(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError("Secret manquant : " + name)
    return value


def main():
    response = requests.get(API, headers={"apikey": need("MF_API_KEY")}, timeout=60)
    response.raise_for_status()
    data = response.json()
    product = data["product"]
    now = datetime.now(ZoneInfo("Europe/Paris"))
    updated = datetime.fromisoformat(product["update_time"].replace("Z", "+00:00"))
    if not timedelta(0) <= now - updated <= timedelta(hours=12):
        raise RuntimeError("Carte Météo-France trop ancienne.")
    current = next((period for period in product.get("periods", []) if datetime.fromisoformat(period["begin_validity_time"].replace("Z", "+00:00")) <= now < datetime.fromisoformat(period["end_validity_time"].replace("Z", "+00:00"))), None)
    if current is None:
        raise RuntimeError("Aucune période de vigilance valide.")

    groups = {}
    for item in current.get("timelaps", {}).get("domain_ids", []):
        code = str(item.get("domain_id", "")).upper().zfill(2)
        name = DEPARTMENTS.get(code)
        if not name:
            continue
        department = f"{name} ({code})"
        for phenomenon in item.get("phenomenon_items", []):
            color = int(phenomenon.get("phenomenon_max_color_id", 1))
            if color in COLORS:
                label = PHENOMENA.get(str(phenomenon.get("phenomenon_id")), "phénomène météo")
                groups.setdefault((color, label), []).append(department)

    lines = ["<b>• Vigilances en cours :</b>"]
    if not groups:
        lines.append("🟢 <b>Vigilance verte :</b> aucun département en vigilance jaune, orange ou rouge.")
    else:
        for (color, label), departments in sorted(groups.items(), reverse=True):
            lines.append(f"{COLORS[color]} <b>{html.escape(label)} :</b> {html.escape(', '.join(sorted(departments)))}.")
    text = "\n".join(lines) + "\n\nSource : https://vigilance.meteofrance.fr/fr"

    os.makedirs("output", exist_ok=True)
    with open("output/message.html", "w", encoding="utf-8") as file:
        file.write(text)
    with open("output/carte.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    if os.getenv("DRY_RUN", "true").lower() == "true":
        print(text)
        return

    telegram = requests.post(
        f"https://api.telegram.org/bot{need('TELEGRAM_BOT_TOKEN')}/sendMessage",
        data={"chat_id": "@Alerte_meteo", "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=60,
    )
    telegram.raise_for_status()


if __name__ == "__main__":
    main()
