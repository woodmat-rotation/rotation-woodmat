# WOODMAT — Rotation Stock (Web App)

## Ce que fait l'app
- Dashboard large (wide) avec KPIs : Volume stock (m³), rotation moyenne, alertes
- Filtres par catégorie de bois, classification, recherche référence
- Graphique évolution des sorties (mensuel) + répartition par classification
- Tableau dynamique avec mise en forme conditionnelle (couleur par classification)
- Onglet dédié Stock Dormant
- Export Excel de la vue filtrée
- Login obligatoire (utilisateur/mot de passe) avant tout accès

## Lancer en local (test)
```
pip install -r requirements.txt
streamlit run app.py
```
Ça ouvre `http://localhost:8501`.

## Mettre le mot de passe (IMPORTANT avant toute mise en ligne)
Ne laissez jamais le mot de passe par défaut. Créez un fichier `.streamlit/secrets.toml`
(copiez `secrets_exemple.toml`) avec vos vrais identifiants :
```
[credentials]
admin = "votre_mot_de_passe_ici"
```
Ce fichier ne doit **jamais** être mis sur un dépôt GitHub public.

## Déployer pour avoir un lien accessible depuis un navigateur

### Option 1 — Streamlit Community Cloud (gratuit, le plus simple)
1. Mettez le dossier sur un dépôt GitHub (privé de préférence).
2. Allez sur https://share.streamlit.io, connectez votre GitHub, choisissez le repo et `app.py`.
3. Dans les réglages de l'app (Settings → Secrets), collez le contenu de `secrets.toml`.
4. Vous obtenez un lien du type `https://woodmat-rotation.streamlit.app` — accessible
   depuis n'importe quel navigateur, sans rien installer sur les postes.
5. Un vrai nom de domaine perso (`https://stock.woodmat.ma`) demande un plan payant
   ou un reverse proxy chez vous — je peux détailler cette étape si besoin.

### Option 2 — Serveur interne WOODMAT
Si vous avez un serveur/VPS, on héberge l'app avec Docker + Nginx (reverse proxy + HTTPS
via Let's Encrypt) pour un vrai `https://votre-domaine.com`. Dites-le-moi si c'est le
scénario voulu, je prépare le Dockerfile et le nginx.conf.

## Limites à connaître
- La base historique importée est stockée sur le serveur de l'app (fichier `.pkl`).
  Sur Streamlit Community Cloud, ce stockage est **éphémère** : il peut être effacé
  au redéploiement — il faudra réimporter la base après une mise à jour du code.
- Le login ici est volontairement simple (un mot de passe partagé par utilisateur).
  Pour des comptes individuels avec rôles/permissions, il faut une vraie couche
  d'authentification (ex: Auth0, ou base utilisateurs) — possible à ajouter ensuite.
