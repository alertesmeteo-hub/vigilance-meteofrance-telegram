"""Publication quotidienne des produits officiels de vigilance Météo-France."""
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BASE = "https://public-api.meteofrance.fr/public/DPVigilance/v1/"
PARIS = ZoneInfo("Europe/Paris")


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Secret manquant : " + name)
    return value


def checked(response, service):
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"{service} : erreur HTTP {response.status_code}")
    return response


def main():
    dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"
    print("Authentification par API Key", flush=True)
    headers = {"apikey": required("MF_API_KEY")}

    def fetch(endpoint):
        return checked(requests.get(BASE + endpoint, headers=headers, timeout=60), "Météo-France")

    print("Téléchargement carte JSON", flush=True)
    carte = fetch("cartevigilance/encours").json()
    product = carte["product"]
    published = datetime.fromisoformat(product["update_time"].replace("Z", "+00:00"))
    now = datetime.now(PARIS)
    if published.tzinfo is None or not timedelta(0) <= now - published <= timedelta(hours=12):
        raise RuntimeError("Carte trop ancienne ou date incohérente : aucun envoi.")
    periods = product["periods"]
    if not periods or not any(
        datetime.fromisoformat(p["begin_validity_time"].replace("Z", "+00:00")) <= now
        < datetime.fromisoformat(p["end_validity_time"].replace("Z", "+00:00")) for p in periods
    ):
        raise RuntimeError("Carte hors période de validité : aucun envoi.")
    print("Téléchargement image", flush=True)
    png_response = fetch("vignettenationale-J-et-J1/encours")
    png = png_response.content
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Image officielle PNG invalide.")
    # Vérifier que le produit n'a pas changé pendant le téléchargement.
    after = fetch("cartevigilance/encours").json()
    if after["product"]["update_time"] != product["update_time"]:
        raise RuntimeError("Bulletin en cours de mise à jour : relancer plus tard.")
    print("Téléchargement outre-mer", flush=True)
    om = fetch("vigilanceom/flux/dernier").content
    with zipfile.ZipFile(io.BytesIO(om)) as archive:
        if not archive.namelist() or archive.testzip() is not None:
            raise RuntimeError("Archive outre-mer invalide.")
    stamp = published.astimezone(PARIS).strftime("%d/%m/%Y à %H h %M")
    caption = (
        "Vigilance Météo-France — " + now.strftime("%d/%m/%Y")
        + "\nCarte nationale : métropole, aujourd'hui et demain."
        + "\nProduit carte mis à jour le " + stamp
        + "\nDiffusion quotidienne, y compris en vigilance verte."
        + "\nBulletins outre-mer dans le fichier joint séparément."
        + "\nSource : https://vigilance.meteofrance.fr/fr"
    )
    om_caption = (
        "Vigilance outre-mer — dernier flux officiel Météo-France (archive ZIP)."
        "\nLes bulletins conservent leurs propres dates et périodes de validité."
        "\nCe flux DROM ne constitue pas une couverture de tous les territoires français."
        "\nSource : Météo-France, API Bulletin Vigilance."
    )
    os.makedirs("output", exist_ok=True)
    with open("output/carte.json", "w", encoding="utf-8") as file:
        json.dump(carte, file, ensure_ascii=False, indent=2)
    with open("output/carte.png", "wb") as file:
        file.write(png)
    with open("output/vigilance-outre-mer.zip", "wb") as file:
        file.write(om)
    with open("output/message.txt", "w", encoding="utf-8") as file:
        file.write(caption + "\n\n" + om_caption)
    if dry_run:
        print("Prévisualisation créée ; aucun message envoyé.")
        return
    bot = required("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "@Alerte_meteo")

    def send(method, data, files):
        # Ne pas relancer automatiquement un POST : un timeout peut masquer un envoi réussi.
        response = checked(requests.post(
            "https://api.telegram.org/bot" + bot + "/" + method,
            data={"chat_id": chat, **data}, files=files, timeout=60,
        ), "Telegram")
        if not response.json().get("ok"):
            raise RuntimeError("Telegram a refusé la publication.")

    send("sendPhoto", {"caption": caption}, {"photo": ("vigilance.png", png, "image/png")})
    print("Carte métropole envoyée.")
    send("sendDocument", {"caption": om_caption}, {"document": ("vigilance-outre-mer.zip", om, "application/zip")})
    print("Archive outre-mer envoyée.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Les exceptions réseau peuvent contenir l'URL privée du bot : ne jamais les afficher.
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print("Échec technique (" + type(error).__name__ + "). Vérifier les accès et les données.", file=sys.stderr)
        sys.exit(1)
