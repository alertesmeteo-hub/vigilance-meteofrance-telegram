"""Publie le résumé départemental de la vigilance Météo-France sur Telegram."""
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BASE = "https://public-api.meteofrance.fr/public/DPVigilance/v1/"
PARIS = ZoneInfo("Europe/Paris")
COLORS = {2: ("🟡", "jaune"), 3: ("🟠", "orange"), 4: ("🔴", "rouge")}
PHENOMENA = {
    "1": "vent violent", "2": "pluie-inondation", "3": "orages",
    "4": "inondation", "5": "neige-verglas", "6": "canicule",
    "7": "grand froid", "8": "avalanches", "9": "vagues-submersion",
}
DEPARTMENTS = {
    "01":"Ain","02":"Aisne","03":"Allier","04":"Alpes de Haute Provence","05":"Hautes Alpes","06":"Alpes Maritimes","07":"Ardèche","08":"Ardennes","09":"Ariège","10":"Aube","11":"Aude","12":"Aveyron","13":"Bouches du Rhône","14":"Calvados","15":"Cantal","16":"Charente","17":"Charente Maritime","18":"Cher","19":"Corrèze","2A":"Corse du Sud","2B":"Haute Corse","21":"Côte d'Or","22":"Côtes d'Armor","23":"Creuse","24":"Dordogne","25":"Doubs","26":"Drôme","27":"Eure","28":"Eure et Loir","29":"Finistère","30":"Gard","31":"Haute Garonne","32":"Gers","33":"Gironde","34":"Hérault","35":"Ille et Vilaine","36":"Indre","37":"Indre et Loire","38":"Isère","39":"Jura","40":"Landes","41":"Loir et Cher","42":"Loire","43":"Haute Loire","44":"Loire Atlantique","45":"Loiret","46":"Lot","47":"Lot et Garonne","48":"Lozère","49":"Maine et Loire","50":"Manche","51":"Marne","52":"Haute Marne","53":"Mayenne","54":"Meurthe et Moselle","55":"Meuse","56":"Morbihan","57":"Moselle","58":"Nièvre","59":"Nord","60":"Oise","61":"Orne","62":"Pas de Calais","63":"Puy de Dôme","64":"Pyrénées Atlantiques","65":"Hautes Pyrénées","66":"Pyrénées Orientales","67":"Bas Rhin","68":"Haut Rhin","69":"Rhône","70":"Haute Saône","71":"Saône et Loire","72":"Sarthe","73":"Savoie","74":"Haute Savoie","75":"Paris","76":"Seine Maritime","77":"Seine et Marne","78":"Yvelines","79":"Deux Sèvres","80":"Somme","81":"Tarn","82":"Tarn et Garonne","83":"Var","84":"Vaucluse","85":"Vendée","86":"Vienne","87":"Haute Vienne","88":"Vosges","89":"Yonne","90":"Territoire de Belfort","91":"Essonne","92":"Hauts de Seine","93":"Seine Saint Denis","94":"Val de Marne","95":"Val d'Oise"
}

def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Secret manquant : " + name)
    return value

def checked(response):
    if not 200 <= response.status_code < 300:
        raise RuntimeError("Météo-France : erreur HTTP " + str(response.status_code))
    return response

def summary(product, now):
    periods = product.get("periods", [])
    current = next((period for period in periods if datetime.fromisoformat(period["begin_validity_time"].replace("Z", "+00:00")) <= now < datetime.fromisoformat(period["end_validity_time"].replace("Z", "+00:00"))), None)
    if current is None:
        raise RuntimeError("Aucune période de vigilance actuellement valide.")
    groups = {}
    for item in current.get("timelaps", {}).get("domain_ids", []):
        department = DEPARTMENTS.get(str(item.get("domain_id", "")).zfill(2))
        if not department:
            continue
        for phenomenon in item.get("phenomenon_items", []):
            color = int(phenomenon.get("phenomenon_max_color_id", 1))
            if color in COLORS:
                name = PHENOMENA.get(str(phenomenon.get("phenomenon_id")), "phénomène météo")
                groups.setdefault((color, name), []).append(department)
    lines = ["<b>• Vigilances en cours :</b>"]
    if not groups:
        lines.append("🟢 <b>Vigilance verte :</b> aucun département en vigilance jaune, orange ou rouge.")
    else:
        for (color, name), departments in sorted(groups.items(), key=lambda value: (-value[0][0], value[0][1])):
            emoji, label = COLORS[color]
            lines.append(f"{emoji} <b>{html.escape(name)} :</b> {html.escape(', '.join(sorted(departments))) }.")
    return "\n".join(lines), bool(groups)

def send_messages(bot, chat, message):
    parts, current = [], ""
    for line in message.splitlines(True):
        if current and len(current) + len(line) > 3900:
            parts.append(current)
            current = ""
        current += line
    if current:
        parts.append(current)
    for part in parts:
        result = requests.post("https://api.telegram.org/bot" + bot + "/sendMessage", data={"chat_id": chat, "text": part, "parse_mode": "HTML", "disable_web_page_preview": "true"}, timeout=60)
        if not result.ok or not result.json().get("ok"):
            raise RuntimeError("Telegram a refusé la publication.")

def official_map_pdf():
    page = checked(requests.get("https://vigilance.meteofrance.fr/fr", timeout=60)).text
    links = re.findall(r'https://rwg\.meteofrance\.com[^"\']+', page)
    url = next((html.unescape(link) for link in links if "report_type=vigilancev6" in link and "version%20PDF" in link), None)
    if not url:
        raise RuntimeError("Carte officielle Météo-France introuvable.")
    document = checked(requests.get(url, timeout=60))
    if not document.content.startswith(b"%PDF"):
        raise RuntimeError("La carte officielle n'est pas au format PDF.")
    return document.content


def send_official_map(bot, chat, document):
    result = requests.post(
        "https://api.telegram.org/bot" + bot + "/sendDocument",
        data={"chat_id": chat, "caption": "🗺 <b>Carte officielle Météo-France</b>", "parse_mode": "HTML"},
        files={"document": ("carte-vigilance-meteo-france.pdf", document, "application/pdf")},
        timeout=90,
    )
    if not result.ok or not result.json().get("ok"):
        raise RuntimeError("Telegram a refusé l'envoi de la carte.")


def main():
    dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"
    headers = {"apikey": required("MF_API_KEY")}
    response = checked(requests.get(BASE + "cartevigilance/encours", headers=headers, timeout=60))
    carte = response.json()
    product = carte["product"]
    published = datetime.fromisoformat(product["update_time"].replace("Z", "+00:00"))
    now = datetime.now(PARIS)
    if published.tzinfo is None or not timedelta(0) <= now - published <= timedelta(hours=12):
        raise RuntimeError("Carte trop ancienne ou date incohérente : aucun envoi.")
    message, has_vigilance = summary(product, now)
    message += "\n\nSource : https://vigilance.meteofrance.fr/fr"
    document = official_map_pdf() if has_vigilance else None
    os.makedirs("output", exist_ok=True)
    with open("output/carte.json", "w", encoding="utf-8") as file:
        json.dump(carte, file, ensure_ascii=False, indent=2)
    with open("output/message.html", "w", encoding="utf-8") as file:
        file.write(message)
    if dry_run:        print(message)
        return
    bot = required("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "@Alerte_meteo")
    send_messages(bot, chat, message)
    if document:
        send_official_map(bot, chat, document)
    print("Résumé des vigilances départementales envoyé.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, RuntimeError) else "Échec technique (" + type(error).__name__ + ").", file=sys.stderr)
        sys.exit(1)
