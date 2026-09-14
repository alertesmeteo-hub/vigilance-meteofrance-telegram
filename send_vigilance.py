import html, json, os, sys
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

    current = next(
        (
            period for period in product.get("periods", [])
            if datetime.fromisoformat(period["begin_validity_time"].replace("Z", "+00:00"))
            <= now <
            datetime.fromisoformat(period["end_validity_time"].replace("Z", "+00:00"))
        ),
        None,
    )
    if current is None:
        raise RuntimeError("Aucune période de vigilance valide.")

    groups = {}
    for item in current.get("timelaps", {}).get("domain_ids", []):
        department = str(item.get("domain_id", "")).zfill(2)
        for phenomenon in item.get("phenomenon_items", []):
            color = int(phenomenon.get("phenomenon_max_color_id", 1))
            if color in COLORS:
                name = PHENOMENA.get(
                    str(phenomenon.get("phenomenon_id")),
                    "phénomène météo",
                )
                groups.setdefault((color, name), []).append(department)

    lines = ["<b>• Vigilances en cours :</b>"]
    if not groups:
        lines.append(
            "🟢 <b>Vigilance verte :</b> aucun département en vigilance jaune, orange ou rouge."
        )
    else:
        for (color, name), departments in sorted(groups.items(), reverse=True):
            lines.append(
                f"{COLORS[color]} <b>{html.escape(name)} :</b> "
                f"{html.escape(', '.join(sorted(departments)))}."
            )

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
        "https://api.telegram.org/bot"
        + need("TELEGRAM_BOT_TOKEN")
        + "/sendMessage",
        data={
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", "@Alerte_meteo"),
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=60,
    )
    telegram.raise_for_status()

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
