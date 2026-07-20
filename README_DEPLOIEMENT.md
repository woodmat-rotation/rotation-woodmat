# WOODMAT — Rotation du stock (Web App)

## Fichiers du dossier
- `app.py` — l'application
- `base_mouvements.pkl` — **la base historique 2020-2025, déjà intégrée** (60 631 mouvements).
  Ce fichier doit être uploadé sur GitHub **à côté de** `app.py`, à la racine du repo.
- `requirements.txt`, `secrets_exemple.toml` — exemple indiquant qu’aucun secret Streamlit n’est nécessaire pour l’authentification

## Ce que fait l'app
- La base historique 2020-2025 est **intégrée en permanence** — l'utilisateur ne l'importe
  plus jamais. Elle est chargée automatiquement au démarrage (lecture pickle, quasi instantanée).
- Chaque analyse ne demande que 2 fichiers : **Stock actuel** (obligatoire, tous les jours) et
  **Mouvements de l'année en cours** (optionnel — dès qu'un nouvel export 2026 est disponible).
- Quand un fichier "mouvements année en cours" est importé, il est **fusionné automatiquement**
  avec la base et la base est **réenregistrée sur le serveur** — la fois suivante, ces mouvements
  font déjà partie de l'historique, plus besoin de les réimporter.
- Dashboard large (wide) avec KPIs : Volume stock (m³), rotation moyenne, alertes
- Filtres par catégorie de bois, classification, recherche référence
- Graphique évolution des sorties (mensuel) + répartition par classification
- Tableau dynamique avec mise en forme conditionnelle (couleur par classification)
- Onglet dédié Stock Dormant
- Export Excel de la vue filtrée
- Login applicatif obligatoire (email/mot de passe WOODMAT) après chargement de l’app
- Performance : parsing vectorisé (pas de boucle ligne par ligne) — supporte 60 000+ lignes
  de mouvements sans ralentissement notable.

## Lancer en local (test)
```
pip install -r requirements.txt
streamlit run app.py
```
Ça ouvre `http://localhost:8501`.

## Authentification
L'application ne doit pas utiliser l'authentification Streamlit Cloud, GitHub, Google, OIDC
ou un middleware externe : le lien public doit charger directement `app.py`, puis afficher
uniquement la page de connexion WOODMAT intégrée à l'application.

Le compte initial est créé automatiquement au premier démarrage dans `woodmat_users.json`
avec l'email `admin@woodmat.local` et le mot de passe `woodmat2026`. Après la première
connexion, créez vos comptes Direction/Commercial/Administrateur dans le menu
`👥 Gestion des utilisateurs`, puis changez ou désactivez ce compte initial.

`woodmat_users.json` est un fichier runtime local ignoré par Git. Il ne faut pas configurer
`st.login()`, `st.logout()`, `st.user`, `st.experimental_user`, `streamlit_authenticator`,
OIDC, Google ou GitHub dans Streamlit pour cette application.

## Déployer pour avoir un lien accessible depuis un navigateur

### Option 1 — Streamlit Community Cloud (gratuit, le plus simple)
1. Mettez le dossier sur un dépôt GitHub (privé de préférence).
2. Allez sur https://share.streamlit.io, connectez votre GitHub, choisissez le repo et `app.py`.
3. Dans les réglages Streamlit Cloud, laissez l'application en accès public et ne configurez
   aucun fournisseur d'identité Streamlit/OIDC/GitHub/Google.
4. Vous obtenez un lien du type `https://woodmat-rotation.streamlit.app` — accessible
   depuis n'importe quel navigateur, sans connexion Streamlit préalable ; seule la page de
   connexion WOODMAT de l'application doit apparaître.
5. Un vrai nom de domaine perso (`https://stock.woodmat.ma`) demande un plan payant
   ou un reverse proxy chez vous — je peux détailler cette étape si besoin.

### Option 2 — Serveur interne WOODMAT
Si vous avez un serveur/VPS, on héberge l'app avec Docker + Nginx (reverse proxy + HTTPS
via Let's Encrypt) pour un vrai `https://votre-domaine.com`. Dites-le-moi si c'est le
scénario voulu, je prépare le Dockerfile et le nginx.conf.

## Limites à connaître
- La base est réenregistrée sur le serveur après fusion des nouveaux mouvements.
  Sur Streamlit Community Cloud, ce stockage est **éphémère** : un redéploiement (ex: après
  une mise à jour du code) peut réinitialiser `base_mouvements.pkl` à sa version GitHub —
  il faudra alors réimporter les mouvements de l'année en cours une fois. Si ça pose problème,
  on peut faire télécharger automatiquement le `.pkl` mis à jour pour que vous le remplaciez
  dans le repo GitHub — dites-le-moi si vous voulez cette option.
- Les comptes applicatifs sont stockés dans `woodmat_users.json` sur le serveur Streamlit.
  Sur Streamlit Community Cloud, ce stockage peut être réinitialisé lors d'un redéploiement ;
  recréez alors les comptes depuis le compte administrateur initial.
