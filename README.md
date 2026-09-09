# Vigilance Météo-France vers Telegram

Publication quotidienne à 7 h, fuseau Europe/Paris, sur **@Alerte_meteo**, avec le bot **@AlertesMeteo_bot**. L'envoi est prévu chaque jour, y compris lorsque la carte est verte.

## État de l'installation

Le programme et GitHub Actions sont installés. L'envoi réel reste désactivé jusqu'à la configuration des secrets et de la variable d'activation. Les appels aux services et la livraison Telegram doivent encore être validés avec vos accès.

## Produits envoyés

1. Carte officielle de la métropole pour aujourd'hui et demain, sous forme d'image, accompagnée de la date du produit carte.
2. Archive ZIP officielle du flux de vigilance outre-mer DROM, avec ses bulletins d'origine et leurs propres dates de validité. Cette archive ne couvre pas tous les territoires français. Elle n'est pas transformée en résumé des alertes.

La couverture complète de tous les territoires et un résumé lisible des bulletins outre-mer restent à compléter. Il ne faut pas assimiler la couleur de la carte métropole à une vigilance pour toute la France outre-mer comprise.

## Configuration

Dans Settings → Secrets and variables → Actions → Secrets, ajouter :

| Secret | Valeur |
| --- | --- |
| TELEGRAM_BOT_TOKEN | Token privé fourni par BotFather pour @AlertesMeteo_bot |
| MF_APPLICATION_ID | Identifiant d'application OAuth2 Météo-France, valeur après Basic dans la commande de génération de token du portail |

Créer ou utiliser un compte sur https://portail-api.meteofrance.fr et souscrire à l'API Bulletin Vigilance. Dans la génération OAuth2, récupérer l'identifiant d'application. Le programme demande un nouveau token temporaire à chaque exécution. Ne pas utiliser comme identifiant le token temporaire d'une heure.

Ne jamais mettre ces secrets dans un fichier, une issue, un message ou le README. Le bot doit être administrateur du canal avec le droit de publier.

## Premier essai et activation

1. Ouvrir Actions → Vigilance quotidienne Telegram → Run workflow.
2. Garder « Prévisualiser sans envoyer sur Telegram » coché. Le script télécharge les produits sans publier. Télécharger l'artefact vigilance pour vérifier la carte et les fichiers.
3. Après vérification, relancer manuellement en décochant la prévisualisation pour envoyer au canal.
4. Dans Settings → Secrets and variables → Actions → Variables, créer VIGILANCE_ENABLED avec la valeur true pour activer les envois quotidiens.
5. Mettre cette variable à false pour suspendre les envois programmés.

Le planning suit les changements d'heure été/hiver. GitHub Actions peut démarrer en retard ; 7 h est l'heure demandée, pas une garantie à la minute. Sur un dépôt public sans activité, GitHub peut désactiver les planifications après 60 jours : vérifier périodiquement l'onglet Actions.

## Comportement en cas d'erreur

Une carte vieille de plus de 12 heures, hors validité, un PNG ou ZIP invalide, ou un changement du produit carte pendant le téléchargement bloque l'envoi. Le programme ne remplace jamais une donnée manquante par une vigilance verte.

Une erreur apparaît dans Actions. Les messages d'erreur réseau sont masqués pour éviter de publier le token Telegram dans les logs. Les envois POST ne sont pas automatiquement répétés après un timeout, car Telegram pourrait déjà avoir reçu le message.

Les deux publications sont séparées : la carte peut être envoyée alors que l'archive échoue. Avant toute relance, vérifier le canal ; une relance manuelle peut créer un doublon. Il n'existe pas encore de registre persistant empêchant les doublons entre exécutions.

Les produits sont conservés 7 jours dans les artefacts GitHub Actions. Cette première version est un service Telegram, sans extension WordPress et sans branche de données permanente.

## Validation

Chaque changement du programme ou du workflow lance une vérification de syntaxe Python. Cette vérification ne remplace pas le test réel des API avec les secrets.

## Sources officielles

- [Vigilance Météo-France](https://vigilance.meteofrance.fr/fr)
- [Documentation API Bulletin Vigilance](https://confluence-meteofrance.atlassian.net/wiki/spaces/OpenDataMeteoFrance/pages/854065168)
- [API Telegram](https://core.telegram.org/bots/api)
- [Planification GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
