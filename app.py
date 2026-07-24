import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import io
import json
import hashlib
import secrets
import warnings
warnings.filterwarnings('ignore')

# ================================a+============================
# WOODMAT — ROTATION DU STOCK (Web App)
# ============================================================

st.set_page_config(page_title="WOODMAT — Rotation du stock", layout="wide",
                    page_icon="📦", initial_sidebar_state="expanded")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_HISTORIQUE = os.path.join(APP_DIR, "base_mouvements.pkl")  # base 2020-2025, livrée avec l'app
USERS_FILE = os.path.join(APP_DIR, "woodmat_users.json")
SEUIL = 0.001

CLASS_COLORS = {
    'Rupture': '#FFC7CE', 'Critique': '#FF8A8A', 'Stock faible': '#FFD9A0',
    'Normal': '#FFEB9C', 'Bon niveau': '#C6EFCE', 'Surstock': '#BDD7EE',
    'Surstock important': '#9FA8B5', 'Dormant': '#F4B942', 'Sans mouvement': '#E0E0E0',
}

# ============================================================
# AUTHENTIFICATION
# ============================================================

def inject_global_styles():
    st.markdown(
        """
        <style>
        :root {
            --woodmat-blue: #1F3864;
            --woodmat-blue-dark: #13233F;
            --woodmat-gold: #B88A44;
            --woodmat-bg: #F5F7FB;
            --woodmat-card: #FFFFFF;
            --woodmat-border: rgba(31, 56, 100, 0.14);
        }
        .stApp { background: var(--woodmat-bg); }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #13233F 0%, #1F3864 100%);
        }
        [data-testid="stSidebar"] * { color: #F8FAFC !important; }
        [data-testid="stSidebar"] .stButton > button, [data-testid="stSidebar"] button {
            border-radius: 12px;
        }
        .block-container { padding-top: 1.25rem; padding-bottom: 2rem; }
        .woodmat-login-shell {
            max-width: 460px; margin: 7vh auto 0; padding: 2.2rem;
            background: #FFFFFF; border: 1px solid var(--woodmat-border);
            border-radius: 22px; box-shadow: 0 20px 60px rgba(19,35,63,0.14);
        }
        .woodmat-logo {
            width: 64px; height: 64px; border-radius: 18px; margin: 0 auto 0.8rem;
            display: flex; align-items: center; justify-content: center;
            background: linear-gradient(135deg, var(--woodmat-blue), var(--woodmat-gold));
            color: white; font-size: 1.8rem; font-weight: 800;
        }
        .woodmat-header {
            position: sticky; top: 0; z-index: 50; margin-bottom: 1.2rem;
            display: flex; align-items: center; justify-content: space-between; gap: 1rem;
            padding: 0.85rem 1.1rem; background: rgba(255,255,255,0.95);
            border: 1px solid var(--woodmat-border); border-radius: 18px;
            box-shadow: 0 8px 24px rgba(19,35,63,0.07); backdrop-filter: blur(8px);
        }
        .woodmat-header-title { color: var(--woodmat-blue); font-weight: 800; font-size: 1.1rem; }
        .woodmat-header-meta { color: #64748B; font-size: 0.9rem; text-align: right; }
        .woodmat-page-title { color: var(--woodmat-blue); margin: 0 0 0.25rem; font-weight: 800; }
        .woodmat-panel, .woodmat-kpi-card {
            background: var(--woodmat-card); border: 1px solid var(--woodmat-border);
            border-radius: 18px; padding: 1rem 1.1rem;
            box-shadow: 0 8px 24px rgba(19,35,63,0.06);
        }
        .woodmat-kpi-card { min-height: 150px; }
        .woodmat-kpi-title { color: var(--woodmat-blue); font-size: 0.95rem; font-weight: 700; margin-bottom: 0.45rem; }
        .woodmat-kpi-value { color: #202A35; font-size: 1.55rem; font-weight: 800; line-height: 1.35; }
        .woodmat-kpi-detail { color: #555; font-size: 0.95rem; line-height: 1.45; margin-top: 0.15rem; }
        .woodmat-muted { color: #64748B; font-size: 0.9rem; line-height: 1.35; margin-top: 0.35rem; }
        .woodmat-section-title { color: var(--woodmat-blue); font-size: 1.08rem; font-weight: 800; margin-bottom: 0.1rem; }
        .woodmat-legend { color: #666; font-size: 0.86rem; line-height: 1.45; margin-top: 0.35rem; }
        .woodmat-coming-soon {
            border: 1px dashed rgba(31,56,100,0.28); border-radius: 18px; padding: 1.2rem;
            background: rgba(255,255,255,0.75); color: #475569;
        }
        @media (max-width: 768px) { .woodmat-header { flex-direction: column; align-items: flex-start; } .woodmat-header-meta { text-align: left; } }
        </style>
        """,
        unsafe_allow_html=True)


def hash_password(password, salt=None):
    """Hash PBKDF2 local pour les comptes applicatifs."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored_hash):
    try:
        salt, _digest = stored_hash.split('$', 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored_hash)


def default_users():
    now = pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')
    return [{
        "name": "Administrateur WOODMAT", "email": "admin@woodmat.local",
        "password_hash": hash_password("woodmat2026"), "role": "Administrateur",
        "created_at": now, "last_login": "—", "status": "Actif"
    }]


def load_users():
    if not os.path.exists(USERS_FILE):
        users = default_users()
        save_users(users)
        return users
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default_users()


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def get_current_user():
    email = st.session_state.get("auth_email")
    for u in load_users():
        if u.get("email") == email:
            return u
    return st.session_state.get("auth_user", {})


def user_can_manage_users():
    return get_current_user().get("role") == "Administrateur"


def check_login():
    if st.session_state.get("auth_ok"):
        return True

    inject_global_styles()
    st.markdown(
        """
        <div class='woodmat-login-shell'>
            <div class='woodmat-logo'>W</div>
            <div style='text-align:center'>
                <h1 style='color:#1F3864;margin-bottom:0'>WOODMAT</h1>
                <p style='color:#64748B;margin-top:0.35rem'>Application métier — gestion et analyse des stocks</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.15, 1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="admin@woodmat.local")
            pwd = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("Se connecter", use_container_width=True)
        st.caption("Compte initial : admin@woodmat.local / woodmat2026 — à modifier après la première connexion.")
        if submit:
            users = load_users()
            user = next((u for u in users if u.get("email", "").lower() == email.lower().strip()), None)
            if user and user.get("status") == "Actif" and verify_password(pwd, user.get("password_hash", "")):
                last_login = pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')
                user["last_login"] = last_login
                save_users(users)
                st.session_state["auth_ok"] = True
                st.session_state["auth_email"] = user["email"]
                st.session_state["auth_user"] = user
                st.session_state["last_login"] = last_login
                st.rerun()
            elif user and user.get("status") != "Actif":
                st.error("Compte désactivé. Contactez votre administrateur WOODMAT.")
            else:
                st.error("Identifiants incorrects.")
    return False


def render_user_management():
    st.markdown("<h2 class='woodmat-page-title'>👥 Gestion des utilisateurs</h2>", unsafe_allow_html=True)
    if not user_can_manage_users():
        st.error("Accès réservé à l'Administrateur.")
        st.stop()
    users = load_users()
    st.caption("Création, modification, désactivation et réinitialisation des accès WOODMAT.")
    with st.expander("➕ Ajouter un utilisateur", expanded=True):
        with st.form("add_user"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nom")
            email = c2.text_input("Email")
            role = c1.selectbox("Rôle", ["Direction", "Commercial", "Administrateur"])
            pwd = c2.text_input("Mot de passe initial", type="password")
            if st.form_submit_button("Créer l'utilisateur", type="primary"):
                if not name or not email or not pwd:
                    st.error("Nom, email et mot de passe sont obligatoires.")
                elif any(u.get("email", "").lower() == email.lower().strip() for u in users):
                    st.error("Cet email existe déjà.")
                else:
                    users.append({"name": name, "email": email.lower().strip(), "password_hash": hash_password(pwd),
                                  "role": role, "created_at": pd.Timestamp.now().strftime('%d/%m/%Y %H:%M'),
                                  "last_login": "—", "status": "Actif"})
                    save_users(users); st.success("Utilisateur créé."); st.rerun()

    display = pd.DataFrame([{k: u.get(k) for k in ["name", "email", "role", "created_at", "last_login", "status"]} for u in users])
    st.dataframe(display.rename(columns={"name":"Nom", "email":"Email", "role":"Rôle", "created_at":"Date de création", "last_login":"Dernière connexion", "status":"Statut"}), use_container_width=True)
    selected = st.selectbox("Utilisateur à administrer", [u["email"] for u in users])
    user = next(u for u in users if u["email"] == selected)
    with st.form("edit_user"):
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("Nom", value=user.get("name", ""))
        new_role = c2.selectbox("Rôle", ["Administrateur", "Direction", "Commercial"], index=["Administrateur", "Direction", "Commercial"].index(user.get("role", "Direction")))
        new_status = c3.selectbox("Statut", ["Actif", "Désactivé"], index=0 if user.get("status") == "Actif" else 1)
        new_pwd = st.text_input("Nouveau mot de passe (laisser vide pour ne pas changer)", type="password")
        a, b, c = st.columns(3)
        save_btn = a.form_submit_button("Modifier")
        reset_btn = b.form_submit_button("Réinitialiser le mot de passe")
        delete_btn = c.form_submit_button("Supprimer")
        if save_btn or reset_btn or delete_btn:
            if delete_btn:
                if user["email"] == st.session_state.get("auth_email"):
                    st.error("Vous ne pouvez pas supprimer votre propre compte connecté.")
                else:
                    users = [u for u in users if u["email"] != selected]
                    save_users(users); st.success("Utilisateur supprimé."); st.rerun()
            else:
                user["name"], user["role"], user["status"] = new_name, new_role, new_status
                if new_pwd:
                    user["password_hash"] = hash_password(new_pwd)
                if reset_btn and not new_pwd:
                    st.warning("Saisissez un nouveau mot de passe avant de réinitialiser.")
                else:
                    save_users(users); st.success("Utilisateur mis à jour."); st.rerun()


# ============================================================
# CHARGEMENT / CALCUL — vectorisé pour performance (60 000+ lignes)
# ============================================================

def parse_qty_series(s):
    """Nettoyage + conversion numérique vectorisée (rapide sur gros volumes)."""
    s = s.astype(str).str.strip()
    s = (s.str.replace(' ', '', regex=False)
          .str.replace(',', '.', regex=False)
          .str.replace('-', '', regex=False)
          .str.replace('+', '', regex=False))
    return pd.to_numeric(s, errors='coerce').fillna(0.0)


def parse_dates_series(s):
    d = pd.to_datetime(s, format='%d-%m-%y %H:%M:%S', errors='coerce')
    mask = d.isna()
    if mask.any():
        d.loc[mask] = pd.to_datetime(s[mask], dayfirst=True, errors='coerce')
    return d


def normaliser_mouv(df):
    if not str(df.columns[0]).upper().startswith('DATE'):
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

    ncols = len(df.columns)
    if ncols >= 14:
        df.columns = ['Date', 'ES', 'Document', 'Tiers', 'Reference', 'Quantite', 'Unite',
                      'PU_HT', 'Solde', 'CUMP', 'Depot', 'Categorie', 'Sous_Cat', 'Marque'][:ncols]
    else:
        df.columns = ['Date', 'ES', 'Document', 'Tiers', 'Reference', 'Quantite', 'Unite',
                      'PU_HT', 'Solde', 'Depot', 'Categorie', 'Sous_Cat', 'Marque'][:ncols]

    df['Qty'] = parse_qty_series(df['Quantite'])
    df['Date'] = parse_dates_series(df['Date'])
    df = df[df['ES'].isin(['S', 'E', 'ME', 'TE'])]
    df = df.drop_duplicates(subset=['Date', 'ES', 'Document', 'Reference', 'Quantite'])
    return df


def charger_mouv_upload(file_bytes):
    df = pd.read_excel(file_bytes)
    return normaliser_mouv(df)


@st.cache_resource(show_spinner=False)
def charger_base_historique():
    """Base 2020-2025 livrée avec l'app — lue une seule fois, gardée en mémoire serveur."""
    return pd.read_pickle(BASE_HISTORIQUE)


def _stock_moyen_pondere(events_df, date_debut, date_fin, stock_actuel):
    """
    Reconstruit le STOCK MOYEN réel (pondéré dans le temps) sur [date_debut, date_fin],
    par référence, à partir :
      - du Stock actuel (connu avec certitude à date_fin, issu de l'export ERP du jour) ;
      - de l'historique des mouvements (entrées positives, sorties négatives) survenus
        dans la fenêtre, avec leur date exacte.

    Logique : en partant du niveau connu à date_fin, on "remonte" mouvement par
    mouvement pour reconstituer le niveau de stock à chaque instant du passé, puis on
    calcule la moyenne pondérée par la durée de chaque palier (et non une simple
    moyenne arithmétique des mouvements, qui ignorerait le temps réellement passé à
    chaque niveau de stock).

    Hypothèse (à connaître) : cette reconstruction suppose que les mouvements ES
    ('S','E','ME','TE') couvrent bien toutes les variations de stock sur la période
    (pas d'ajustement d'inventaire hors mouvement, pas de perte/casse non enregistrée).
    Les niveaux reconstruits sont plafonnés à 0 (un stock ne peut pas être négatif) —
    si ce plafonnage se déclenche souvent, c'est le signe d'un écart entre la date de
    l'export stock et la couverture réelle des mouvements.
    """
    total_duration = (date_fin - date_debut).total_seconds()
    resultat = stock_actuel.astype(float).copy()
    if total_duration <= 0 or events_df.empty:
        return resultat

    for ref, g in events_df.sort_values('Date').groupby('Reference'):
        if ref not in resultat.index:
            continue
        s_now = stock_actuel.get(ref, 0.0)
        niveau = s_now - g['Delta'].sum()  # niveau au début de la fenêtre
        t_prec = date_debut
        somme_ponderee = 0.0
        for d, delta in zip(g['Date'], g['Delta']):
            duree = (d - t_prec).total_seconds()
            if duree > 0:
                somme_ponderee += max(niveau, 0.0) * duree
            niveau += delta
            t_prec = d
        duree = (date_fin - t_prec).total_seconds()
        if duree > 0:
            somme_ponderee += max(niveau, 0.0) * duree
        resultat.loc[ref] = somme_ponderee / total_duration

    return resultat


@st.cache_data(show_spinner=False)
def calculer_indicateurs(df_mv, df_st_bytes):
    df_st = pd.read_excel(df_st_bytes)
    # L'unité fiable est celle d'ACHAT ("Unité P.") — l'unité de VENTE ("Unité V.") contient
    # des erreurs de saisie ponctuelles (ex: une référence en M2 étiquetée "P" à la vente).
    _unite_col = next((c for c in df_st.columns if str(c).strip().upper() == 'UNITÉ P.'), None)
    if _unite_col is None:
        _unite_col = next(
            (c for c in df_st.columns if str(c).strip().upper().startswith('UNIT') and 'P' in str(c).upper()),
            None)
    if _unite_col is None:
        _unite_col = next(
            (c for c in df_st.columns if str(c).strip().upper().startswith('UNIT') and 'V' in str(c).upper()),
            None)
    if _unite_col and _unite_col != 'Unité':
        df_st.rename(columns={_unite_col: 'Unité'}, inplace=True)
    elif _unite_col is None:
        df_st['Unité'] = 'M3'
    if 'Désignation' not in df_st.columns:
        df_st['Désignation'] = ''
    df_st['Qty_s'] = parse_qty_series(df_st['Quantité'])
    df_st_c = df_st.groupby('Référence').agg(
        Stock=('Qty_s', 'sum'), Cat=('Catégorie', 'first'), Unite=('Unité', 'first'),
        Designation=('Désignation', 'first')).reset_index()
    df_st_c = df_st_c[df_st_c['Cat'].notna()]
    df_st_c.loc[df_st_c['Cat'].isin(['BOIS BLANC', 'BOIS ROUGE']), 'Unite'] = 'M3'

    date_max = df_mv['Date'].max()
    date_12m_debut = date_max - pd.DateOffset(months=12)

    sorties = df_mv[df_mv['ES'] == 'S']
    entrees = df_mv[df_mv['ES'].isin(['E', 'ME', 'TE'])]

    mv_s_all = sorties.groupby('Reference').agg(
        Total_Sorti=('Qty', 'sum'), Nb_Trans=('Qty', 'count'), Dern_Sortie=('Date', 'max')).reset_index()
    mv_e_all = entrees.groupby('Reference').agg(Dern_Entree=('Date', 'max')).reset_index()

    s_12m_df = sorties[(sorties['Date'] >= date_12m_debut) & (sorties['Date'] <= date_max)]
    e_12m_df = entrees[(entrees['Date'] >= date_12m_debut) & (entrees['Date'] <= date_max)]
    mv_s_12m = s_12m_df.groupby('Reference').agg(S_12M=('Qty', 'sum'), T_12M=('Qty', 'count')).reset_index()
    mv_e_12m = e_12m_df.groupby('Reference')['Qty'].sum().rename('A_12M').reset_index()

    # ── Fenêtre 4 mois (tendance récente) ──
    date_4m_debut = date_max - pd.DateOffset(months=4)
    s_4m_df = sorties[(sorties['Date'] >= date_4m_debut) & (sorties['Date'] <= date_max)]
    e_4m_df = entrees[(entrees['Date'] >= date_4m_debut) & (entrees['Date'] <= date_max)]
    mv_s_4m = s_4m_df.groupby('Reference')['Qty'].sum().rename('S_4M').reset_index()

    # ── Historique des mouvements signés (entrée = +, sortie = -), pour reconstituer
    #    le stock moyen réel sur chaque fenêtre à partir du stock actuel connu ──
    events_12m = pd.concat([
        s_12m_df[['Reference', 'Date', 'Qty']].assign(Delta=lambda d: -d['Qty']),
        e_12m_df[['Reference', 'Date', 'Qty']].assign(Delta=lambda d: d['Qty']),
    ], ignore_index=True) if (len(s_12m_df) or len(e_12m_df)) else pd.DataFrame(columns=['Reference', 'Date', 'Qty', 'Delta'])
    events_4m = pd.concat([
        s_4m_df[['Reference', 'Date', 'Qty']].assign(Delta=lambda d: -d['Qty']),
        e_4m_df[['Reference', 'Date', 'Qty']].assign(Delta=lambda d: d['Qty']),
    ], ignore_index=True) if (len(s_4m_df) or len(e_4m_df)) else pd.DataFrame(columns=['Reference', 'Date', 'Qty', 'Delta'])

    # ── Historique par année (S_2020, S_2021 ... / A_2020, A_2021 ...) ──
    sorties_y = sorties.assign(Annee=sorties['Date'].dt.year)
    entrees_y = entrees.assign(Annee=entrees['Date'].dt.year)
    piv_s = sorties_y.groupby(['Reference', 'Annee'])['Qty'].sum().unstack(fill_value=0)
    piv_t = sorties_y.groupby(['Reference', 'Annee'])['Qty'].count().unstack(fill_value=0)
    piv_a = entrees_y.groupby(['Reference', 'Annee'])['Qty'].sum().unstack(fill_value=0)
    piv_s.columns = [f'S_{int(y)}' for y in piv_s.columns]
    piv_t.columns = [f'T_{int(y)}' for y in piv_t.columns]
    piv_a.columns = [f'A_{int(y)}' for y in piv_a.columns]
    cols_annuelles = sorted(set(piv_s.columns) | set(piv_a.columns) | set(piv_t.columns))

    sm = df_st_c.copy()
    sm = sm.merge(mv_s_all, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_e_all, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_s_12m, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_e_12m, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_s_4m, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(piv_s, left_on='Référence', right_index=True, how='left')
    sm = sm.merge(piv_t, left_on='Référence', right_index=True, how='left')
    sm = sm.merge(piv_a, left_on='Référence', right_index=True, how='left')
    for c in ['Total_Sorti', 'Nb_Trans', 'S_12M', 'T_12M', 'A_12M', 'S_4M'] + cols_annuelles:
        sm[c] = sm[c].fillna(0)

    stock_ok = sm['Stock'] > SEUIL

    # ── Stock moyen réel 12M / 4M (reconstruit depuis le stock actuel + l'historique
    #    des mouvements datés — voir _stock_moyen_pondere) ──
    stock_actuel_series = sm.set_index('Référence')['Stock']
    stock_moyen_12m = _stock_moyen_pondere(events_12m, date_12m_debut, date_max, stock_actuel_series)
    stock_moyen_4m = _stock_moyen_pondere(events_4m, date_4m_debut, date_max, stock_actuel_series)
    sm['Stock_moyen_12M'] = sm['Référence'].map(stock_moyen_12m).fillna(sm['Stock']).round(3)
    sm['Stock_moyen_4M'] = sm['Référence'].map(stock_moyen_4m).fillna(sm['Stock']).round(3)

    # ── Moyennes mensuelles ──
    sm['Moy_Mois_12M'] = (sm['S_12M'] / 12.0).round(3)
    sm['Moy_Mois_4M'] = (sm['S_4M'] / 4.0).round(3)

    # ── Rotation actuelle = Sorties 12M ÷ Stock ACTUEL (même formule que le KPI
    #    Dashboard, au niveau article). Sert de repère "vue instantanée" à côté de la
    #    Rotation 12M historique — les deux sont affichées séparément, jamais fondues. ──
    sm['Rotation_Actuelle'] = 0.0
    m = stock_ok & (sm['S_12M'] > 0)
    sm.loc[m, 'Rotation_Actuelle'] = (sm.loc[m, 'S_12M'] / sm.loc[m, 'Stock']).round(2)

    # ── Rotation 12M et 4M HISTORIQUES = Sorties ÷ STOCK MOYEN de la période (pas le
    #    stock actuel), ce qui évite l'explosion du ratio quand le stock actuel est
    #    quasi nul. Indicateur analytique — ne pilote jamais seul la Classification. ──
    sm['Rotation_12M'] = 0.0
    m = (sm['Stock_moyen_12M'] > SEUIL) & (sm['S_12M'] > 0)
    sm.loc[m, 'Rotation_12M'] = (sm.loc[m, 'S_12M'] / sm.loc[m, 'Stock_moyen_12M']).round(2)

    sm['Rotation_4M'] = 0.0
    m = (sm['Stock_moyen_4M'] > SEUIL) & (sm['S_4M'] > 0)
    sm.loc[m, 'Rotation_4M'] = (sm.loc[m, 'S_4M'] / sm.loc[m, 'Stock_moyen_4M']).round(2)

    # ── Tendance de la demande : Moy/Mois 4M vs Moy/Mois 12M ──
    sm['Tendance_Ratio'] = float('nan')
    m = sm['Moy_Mois_12M'] > 0
    sm.loc[m, 'Tendance_Ratio'] = sm.loc[m, 'Moy_Mois_4M'] / sm.loc[m, 'Moy_Mois_12M']
    sm['Tendance_Pct'] = (sm['Tendance_Ratio'] - 1) * 100

    def _label_tendance(row):
        ratio, pct = row['Tendance_Ratio'], row['Tendance_Pct']
        if pd.isna(ratio):
            return '📈 Hausse (nouvelle activité)' if row['Moy_Mois_4M'] > 0 else '⚪ Aucune demande'
        if ratio > 1.10:
            return f'📈 Hausse de la demande ({pct:+.0f}%)'
        if ratio < 0.90:
            return f'📉 Baisse de la demande ({pct:+.0f}%)'
        return f'➡️ Demande stable ({pct:+.0f}%)'
    sm['Tendance_Label'] = sm.apply(_label_tendance, axis=1)

    # ── Couverture = Stock actuel ÷ Moy/Mois 4M (mesure la tenue face à la demande
    #    RÉCENTE, pas historique). NaN si aucune sortie sur 4M : la notion de "nombre
    #    de mois de couverture" n'a pas de sens si rien ne sort — géré via la
    #    Classification (Dormant / Sans mouvement) plutôt qu'inventé à 0 ou l'infini ──
    sm['Couverture'] = float('nan')
    sm.loc[~stock_ok, 'Couverture'] = 0.0
    m = stock_ok & (sm['Moy_Mois_4M'] > 0)
    sm.loc[m, 'Couverture'] = (sm.loc[m, 'Stock'] / sm.loc[m, 'Moy_Mois_4M']).round(1)

    sm['Taux_Immob'] = 0.0
    m = sm['Couverture'] > 0
    sm.loc[m, 'Taux_Immob'] = (sm.loc[m, 'Couverture'] / 12 * 100).clip(upper=100.0).round(1)
    sm.loc[(~m) & stock_ok, 'Taux_Immob'] = 100.0

    # ── Classification : priorité à la Couverture / au niveau de stock, plus jamais
    #    une Rotation élevée seule. Un article sans sortie récente (4M) n'est jamais
    #    classé comme "bon niveau" au seul motif d'une grande couverture. ──
    cov = sm['Couverture']
    conditions_rupture = ~stock_ok
    conditions_sans_mouvement = stock_ok & (sm['S_4M'] == 0) & (sm['Total_Sorti'] == 0)
    conditions_dormant = stock_ok & (sm['S_4M'] == 0) & (sm['Total_Sorti'] > 0)
    m_actif = stock_ok & (sm['S_4M'] > 0)

    sm['Class'] = 'Normal'
    sm.loc[m_actif & (cov < 1), 'Class'] = 'Critique'
    sm.loc[m_actif & (cov >= 1) & (cov < 3), 'Class'] = 'Stock faible'
    sm.loc[m_actif & (cov >= 3) & (cov < 6), 'Class'] = 'Normal'
    sm.loc[m_actif & (cov >= 6) & (cov < 12), 'Class'] = 'Bon niveau'
    sm.loc[m_actif & (cov >= 12) & (cov < 18), 'Class'] = 'Surstock'
    sm.loc[m_actif & (cov >= 18), 'Class'] = 'Surstock important'
    sm.loc[conditions_dormant, 'Class'] = 'Dormant'
    sm.loc[conditions_sans_mouvement, 'Class'] = 'Sans mouvement'
    sm.loc[conditions_rupture, 'Class'] = 'Rupture'

    return sm, date_max, date_12m_debut, cols_annuelles




def format_nombre_fr(value, decimals=2):
    """Formatage sobre des nombres pour l'affichage des indicateurs."""
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(',', ' ')


def format_unite_stock(unite):
    """Libellé court des unités affichées dans les KPI, sans modifier les calculs."""
    u = str(unite).strip().upper()
    return {
        'M3': 'm³', 'M³': 'm³', 'M2': 'm²', 'M²': 'm²',
        'P': 'P', 'PC': 'P', 'PCS': 'P', 'PIECE': 'P', 'PIÈCE': 'P',
        'ML': 'ML', 'M/L': 'ML', 'M.L': 'ML',
    }.get(u, u or 'Unité')

def evolution_mensuelle(df_mv, references=None):
    d = df_mv[df_mv['ES'] == 'S']
    if references is not None:
        d = d[d['Reference'].isin(references)]
    d = d.copy()
    d['Mois'] = d['Date'].dt.to_period('M').dt.to_timestamp()
    return d.groupby('Mois', as_index=False)['Qty'].sum()



def make_pdf_bytes(title, df, date_max):
    """Génère un PDF texte simple sans dépendance externe."""
    lines = [f"WOODMAT - {title}", f"Analyse du {date_max.strftime('%d/%m/%Y')}", ""]
    lines.extend([" | ".join(map(str, row[:8])) for row in df.head(80).itertuples(index=False, name=None)])
    content = "BT /F1 10 Tf 40 800 Td "
    escaped = []
    for line in lines:
        safe = str(line).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')[:120]
        escaped.append(f"({safe}) Tj 0 -14 Td")
    stream = (content + " ".join(escaped) + " ET").encode('latin-1', errors='replace')
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf)); pdf += obj + b"\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return pdf


def add_export_buttons(df, basename, sheet_name, date_max):
    c1, c2 = st.columns([1, 1])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    c1.download_button("⬇️ Exporter Excel", buf.getvalue(),
                       file_name=f"{basename}_{date_max.strftime('%d_%m_%Y')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button("⬇️ Exporter PDF", make_pdf_bytes(sheet_name, df, date_max),
                       file_name=f"{basename}_{date_max.strftime('%d_%m_%Y')}.pdf",
                       mime="application/pdf")


def replenishment_action(couverture):
    if pd.isna(couverture):
        return "⚪ Sans sortie récente (4M) — à vérifier"
    if couverture < 1:
        return "🔴 Commander immédiatement"
    if couverture <= 2:
        return "🟠 Commander prochainement"
    return "🟢 Rien à faire"


# ============================================================
# FEUILLE STOCK BOIS ROUGE (Qualité × Fournisseur × Dimension)
# ENSO et STORA ENSO sont le même fournisseur → fusionnés en une seule colonne
# ============================================================

import re as _re
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BR_QUAL = ['US', 'V', 'VI', 'VII', 'SCHAAL']
BR_MAIN = ['UPM', 'STORA ENSO', 'KAJA', 'WISA', 'KAUKAS', 'HASA', 'KEITELE', 'JULA', 'SEIKKU']
BR_QCOL = {
    'US': ('1F4E79', 'AED6F1'), 'V': ('196F3D', 'A9DFBF'), 'VI': ('6C3483', 'D7BDE2'),
    'VII': ('B7410E', 'F5CBA7'), 'SCHAAL': ('17594A', 'A2D9CE'),
}
BR_TITLE, BR_TOT, BR_SUB, BR_GRAND = '5C2D0A', '8B4513', 'D5B49A', 'A0522D'
BR_DIM1, BR_DIM2 = 'FDF0E8', 'FFFFFF'


def _br_extract_qual(ref):
    for q in ['SCHAAL', 'VII', 'VI', 'V', 'US']:
        if _re.search(r'[\s_]' + q + r'$', str(ref)):
            return q
    return None


def _br_extract_four(ref):
    ref2 = _re.sub(r'^BOIS\s+ROUGE\s+', '', str(ref).upper().strip())
    # ENSO et STORA ENSO fusionnés — même fournisseur
    for f, canon in [('STORA ENSO', 'STORA ENSO'), ('STORA', 'STORA ENSO'), ('ENSO', 'STORA ENSO'),
                      ('KAUKAS', 'KAUKAS'), ('WISA', 'WISA'), ('KAJA', 'KAJA'), ('UPM', 'UPM'),
                      ('JULA', 'JULA'), ('HASA', 'HASA'), ('KEITELE', 'KEITELE'), ('SEIKKU', 'SEIKKU')]:
        if ref2.startswith(f):
            return canon
    return None


def _br_extract_dim(ref, texte5=None):
    ref2 = _re.sub(r'\s*[Xx]\s*', 'X', str(ref).upper())
    m = _re.search(r'(\d{2,3}X\d{2,3})', ref2)
    if m:
        return m.group(1)
    if texte5 is not None and pd.notna(texte5):
        return _re.sub(r'\s*[Xx]\s*', 'X', str(texte5).strip().upper())
    return 'INCONNU'


def _br_dim_key(d):
    p = _re.findall(r'\d+', d)
    return [int(x) for x in p] if p else [0]


def generer_excel_bois_rouge(df_st_raw, date_max):
    """Reconstruit la feuille Stock Bois Rouge (style identique à l'ancien outil desktop),
    avec ENSO et STORA ENSO fusionnés en un seul fournisseur."""
    # BOIS ROUGE + BOIS BLANC SUEDE (même famille ENSO/STORA ENSO) réunis dans le même tableau
    df_br = df_st_raw[df_st_raw['Catégorie'].isin(['BOIS ROUGE', 'BOIS BLANC SUEDE'])].copy()
    df_br['Quantité'] = parse_qty_series(df_br['Quantité'])
    df_br['_qual'] = df_br['Référence'].apply(_br_extract_qual)
    df_br['_four'] = df_br['Référence'].apply(_br_extract_four)
    if 'Texte 5' in df_br.columns:
        df_br['_dim'] = df_br.apply(lambda r: _br_extract_dim(r['Référence'], r.get('Texte 5')), axis=1)
    else:
        df_br['_dim'] = df_br['Référence'].apply(lambda r: _br_extract_dim(r))

    non_reconnus = df_br[(df_br['Quantité'] > 0) & df_br['_qual'].notna() & df_br['_four'].isna()]
    df_br = df_br[(df_br['Quantité'] > 0) & df_br['_qual'].notna() & df_br['_four'].notna()].copy()

    if df_br.empty:
        return None, non_reconnus

    br_qf = {}
    for q in BR_QUAL:
        present = df_br[df_br['_qual'] == q]['_four'].unique()
        br_qf[q] = [f for f in BR_MAIN if f in present] + sorted([f for f in present if f not in BR_MAIN])

    br_dims = sorted(df_br['_dim'].unique(), key=_br_dim_key)
    br_pivot = df_br.pivot_table(index='_dim', columns=['_qual', '_four'], values='Quantité',
                                  aggfunc='sum', fill_value=0).reindex(br_dims)

    def gv(dim, q, fr):
        try:
            k = (q, fr)
            if k in br_pivot.columns:
                v = br_pivot.loc[dim, k]
                return float(v) if pd.notna(v) else 0.0
        except Exception:
            pass
        return 0.0

    br_flat = []
    for q in BR_QUAL:
        for fr in br_qf[q]:
            br_flat.append((q, fr, 'data'))
        br_flat.append((q, 'TOTAL', 'subtotal'))
    br_flat.append(('', 'TOTAL', 'grandtotal'))

    def mf(h):
        return PatternFill("solid", fgColor=h)
    thin = Side(style='thin', color='BBBBBB')
    brd = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(title="Stock BOIS ROUGE")
    ws.sheet_view.showGridLines = False
    n_cols = len(br_flat)
    dt = date_max.strftime('%d/%m/%Y')

    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=1 + n_cols)
    c = ws.cell(1, 1, f"WOODMAT  —  STOCK BOIS ROUGE + BOIS BLANC SUEDE (ENSO)  —  Quantités en M³  |  {dt}")
    c.font = Font(name='Arial', bold=True, size=13, color='FFFFFF')
    c.fill = mf(BR_TITLE)
    c.alignment = Alignment(horizontal='center', vertical='center')

    ws.row_dimensions[2].height = 20
    ws.cell(2, 1, '').fill = mf(BR_TITLE)
    cc = 2
    for q in BR_QUAL:
        n = len(br_qf[q]) + 1
        ws.merge_cells(start_row=2, start_column=cc, end_row=2, end_column=cc + n - 1)
        c = ws.cell(2, cc, q)
        c.font = Font(name='Arial', bold=True, size=11, color='FFFFFF')
        c.fill = mf(BR_QCOL[q][0])
        c.alignment = Alignment(horizontal='center', vertical='center')
        cc += n
    c = ws.cell(2, cc, 'TOTAL')
    c.font = Font(name='Arial', bold=True, size=11, color='FFFFFF')
    c.fill = mf(BR_TOT)
    c.alignment = Alignment(horizontal='center', vertical='center')

    ws.row_dimensions[3].height = 20
    c = ws.cell(3, 1, 'DIMENSION')
    c.font = Font(name='Arial', bold=True, size=10, color='FFFFFF')
    c.fill = mf(BR_TITLE)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = brd
    ws.column_dimensions['A'].width = 13

    for ci, (q, fr, ctype) in enumerate(br_flat):
        col = 2 + ci
        bg = BR_TOT if ctype == 'grandtotal' else (BR_QCOL[q][0] if ctype == 'subtotal' else BR_QCOL[q][1])
        fg = 'FFFFFF' if ctype != 'data' else '1A1A1A'
        c = ws.cell(3, col, fr)
        c.font = Font(name='Arial', bold=(ctype != 'data'), size=8, color=fg)
        c.fill = mf(bg)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = brd
        ws.column_dimensions[get_column_letter(col)].width = 8 if ctype == 'data' else 10

    for ri, dim in enumerate(br_dims):
        row = ri + 4
        ws.row_dimensions[row].height = 15
        dim_bg = BR_DIM1 if ri % 2 == 0 else BR_DIM2
        c = ws.cell(row, 1, dim)
        c.font = Font(name='Arial', size=9, color='3B1500')
        c.fill = mf(dim_bg)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = brd

        row_grand = 0.0
        for ci, (q, fr, ctype) in enumerate(br_flat):
            col = 2 + ci
            if ctype == 'data':
                val = gv(dim, q, fr)
            elif ctype == 'subtotal':
                val = sum(gv(dim, q, ff) for ff in br_qf[q])
                row_grand += val
            else:
                val = row_grand
            c = ws.cell(row, col)
            if val < 0.0005:
                c.value = None
                c.fill = mf('F2F2F2' if ctype == 'data' else ('E0D0C4' if ctype == 'subtotal' else 'E8CEB8'))
            else:
                c.value = round(val, 3)
                c.number_format = '#,##0.000'
                c.fill = mf(BR_GRAND if ctype == 'grandtotal' else (BR_SUB if ctype == 'subtotal' else dim_bg))
            c.font = Font(name='Arial', bold=(ctype != 'data'), size=9,
                          color=('FFFFFF' if ctype == 'grandtotal' else ('5C2D0A' if ctype == 'subtotal' else '3B1500')))
            c.alignment = Alignment(horizontal='right', vertical='center')
            c.border = brd

    tot_row = len(br_dims) + 4
    ws.row_dimensions[tot_row].height = 18
    c = ws.cell(tot_row, 1, 'TOTAL')
    c.font = Font(name='Arial', bold=True, size=10, color='FFFFFF')
    c.fill = mf(BR_TOT)
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = brd

    grand_col_total = 0.0
    for ci, (q, fr, ctype) in enumerate(br_flat):
        col = 2 + ci
        if ctype == 'data':
            col_sum = sum(gv(dim, q, fr) for dim in br_dims)
        elif ctype == 'subtotal':
            col_sum = sum(sum(gv(dim, q, ff) for ff in br_qf[q]) for dim in br_dims)
            grand_col_total += col_sum
        else:
            col_sum = grand_col_total
        c = ws.cell(tot_row, col)
        c.value = round(col_sum, 3) if col_sum > 0.0005 else None
        c.number_format = '#,##0.000'
        c.font = Font(name='Arial', bold=True, size=9, color='FFFFFF')
        c.fill = mf(BR_TOT)
        c.alignment = Alignment(horizontal='right', vertical='center')
        c.border = brd

    ws.freeze_panes = 'B4'
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), non_reconnus


# ============================================================
# INTERFACE
# ============================================================

if not check_login():
    st.stop()

if not os.path.exists(BASE_HISTORIQUE):
    st.error("⚠️ La base historique (base_mouvements.pkl) n'est pas présente dans le déploiement. "
             "Elle doit être livrée avec l'application — contactez l'administrateur.")
    st.stop()

inject_global_styles()

MENU_ITEMS = [
    "🏠 Dashboard", "📦 Rotation du stock", "📦 Réapprovisionnement", "📈 Analyses", "⚠️ Alertes",
    "📄 Rapports", "📚 Historique", "😴 Stock dormant", "🪵 Stock Bois Rouge"
]
if user_can_manage_users():
    MENU_ITEMS.append("👥 Gestion des utilisateurs")

with st.sidebar:
    st.markdown("### 🪵 WOODMAT")
    st.caption(f"Connecté : {get_current_user().get('name', '')}")
    st.divider()
    page = st.radio("Navigation", MENU_ITEMS, label_visibility="collapsed")
    st.divider()
    st.caption("La base historique 2020–2025 est intégrée à l'application — rien à importer.")

    f_mouv = None
    f_stock = None
    lancer = False
    if page in ["🏠 Dashboard", "📦 Rotation du stock", "📦 Réapprovisionnement", "📈 Analyses", "⚠️ Alertes", "📄 Rapports", "📚 Historique", "😴 Stock dormant", "🪵 Stock Bois Rouge"]:
        st.markdown("**1. Mouvements de l'année en cours** _(optionnel)_")
        f_mouv = st.file_uploader("Export ERP mouvements (ex : 2026)", type=["xlsx", "xls"], key="mouv")

        st.markdown("**2. Stock actuel** _(obligatoire, export du jour)_")
        f_stock = st.file_uploader("Export ERP stock actuel", type=["xlsx", "xls"], key="stock")

        lancer = st.button("🔄 Générer l'analyse", type="primary", use_container_width=True)

current_user = get_current_user()
user = current_user.get('name', current_user.get('email', ''))
role = current_user.get('role', '—')
today = pd.Timestamp.now().strftime('%d/%m/%Y')
st.markdown(
    f"""
    <div class='woodmat-header'>
        <div style='display:flex;align-items:center;gap:0.75rem'>
            <div class='woodmat-logo' style='width:42px;height:42px;border-radius:13px;font-size:1.2rem;margin:0'>W</div>
            <div><div class='woodmat-header-title'>WOODMAT — Rotation du stock</div><div class='woodmat-muted'>Application métier</div></div>
        </div>
        <div class='woodmat-header-meta'>📅 {today}<br>👤 {user}<br>🔐 {role}</div>
    </div>
    """,
    unsafe_allow_html=True)
if st.button("Déconnexion", key="logout_header"):
    st.session_state.clear()
    st.rerun()

if "sm" not in st.session_state:
    st.session_state["sm"] = None

if lancer:
    if f_stock is None:
        st.error("Choisissez le fichier stock actuel.")
    else:
        with st.spinner("Calcul des indicateurs de rotation..."):
            df_base = charger_base_historique()
            if f_mouv is not None:
                df_recent = charger_mouv_upload(f_mouv)
                df_mv = pd.concat([df_base, df_recent], ignore_index=True)
                df_mv = df_mv.drop_duplicates(subset=['Date', 'ES', 'Document', 'Reference', 'Quantite'])
                # Fusion + sauvegarde automatique de la base pour les prochaines analyses
                df_mv.to_pickle(BASE_HISTORIQUE)
                charger_base_historique.clear()
            else:
                df_mv = df_base
            sm, date_max, date_12m_debut, cols_annuelles = calculer_indicateurs(df_mv, f_stock)
            f_stock.seek(0)
            df_st_raw = pd.read_excel(f_stock)
            st.session_state["sm"] = sm
            st.session_state["df_mv"] = df_mv
            st.session_state["date_max"] = date_max
            st.session_state["date_12m_debut"] = date_12m_debut
            st.session_state["cols_annuelles"] = cols_annuelles
            st.session_state["df_st_raw"] = df_st_raw
            st.session_state.setdefault("analysis_history", []).append({
                "Date": pd.Timestamp.now().strftime('%d/%m/%Y %H:%M'),
                "Utilisateur": get_current_user().get("name", ""),
                "Catégorie": "Toutes",
                "Nombre d'articles": len(sm),
                "Durée d'analyse": "—",
            })
        if f_mouv is not None:
            st.success("Mouvements fusionnés et base historique mise à jour sur le serveur ✅")

sm = st.session_state.get("sm")

if page == "👥 Gestion des utilisateurs":
    render_user_management()
    st.stop()

if page == "📚 Historique":
    st.markdown("<h2 class='woodmat-page-title'>Historique des analyses</h2>", unsafe_allow_html=True)
    hist = pd.DataFrame(st.session_state.get("analysis_history", []),
                        columns=["Date", "Utilisateur", "Catégorie", "Nombre d'articles", "Durée d'analyse"])
    st.markdown("<div class='woodmat-panel'>", unsafe_allow_html=True)
    st.dataframe(hist, use_container_width=True, height=420)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

if page == "📈 Analyses":
    st.markdown("<h2 class='woodmat-page-title'>Analyses</h2>", unsafe_allow_html=True)
    st.markdown("<div class='woodmat-coming-soon'>Ce module est prêt à accueillir les prochaines analyses métier.</div>", unsafe_allow_html=True)
    st.stop()

if sm is None:
    st.markdown(f"<h2 class='woodmat-page-title'>{page}</h2>", unsafe_allow_html=True)
    st.info("⬅️ Importez le **stock actuel** (et les mouvements de l'année en cours si disponibles) "
            "dans la barre latérale, puis cliquez sur **Générer l'analyse**.")
    st.stop()

df_mv = st.session_state["df_mv"]
date_max = st.session_state["date_max"]
date_12m_debut = st.session_state["date_12m_debut"]

st.caption(
    f"Analyse réalisée le : {date_max.strftime('%d/%m/%Y')}  |  "
    f"Fenêtre d'analyse : 12 et 4 derniers mois  |  "
    f"Mouvements analysés : {len(df_mv):,}".replace(',', ' ')
)

# ── Filtres ──────────────────────────────────────────────
fc1, fc2, fc3 = st.columns([2, 2, 2])
fc4, fc5 = st.columns([2, 2])
with fc1:
    cats = sorted(sm['Cat'].dropna().unique())
    sel_cats = st.multiselect("Catégorie", cats, default=[])
with fc2:
    classes = sorted(sm['Class'].unique())
    sel_class = st.multiselect("Classification", classes, default=[])
with fc3:
    unites = sorted(sm['Unite'].dropna().astype(str).unique())
    sel_unites = st.multiselect("Unité", unites, default=[])
with fc4:
    references = sorted(sm['Référence'].dropna().astype(str).unique())
    sel_refs = st.multiselect("Référence", references, default=[])
with fc5:
    recherche = st.text_input("🔍 Recherche référence ou désignation")

f = sm.copy()
if sel_cats:
    f = f[f['Cat'].isin(sel_cats)]
if sel_class:
    f = f[f['Class'].isin(sel_class)]
if sel_unites:
    f = f[f['Unite'].astype(str).isin(sel_unites)]
if sel_refs:
    f = f[f['Référence'].astype(str).isin(sel_refs)]
if recherche:
    f = f[f['Référence'].astype(str).str.contains(recherche, case=False, na=False)
          | f['Designation'].astype(str).str.contains(recherche, case=False, na=False)]

CLASS_BADGE = {
    'Rupture': '🔴 Rupture', 'Critique': '🔴 Critique', 'Stock faible': '🟠 Stock faible',
    'Normal': '🟡 Normal', 'Bon niveau': '🟢 Bon niveau', 'Surstock': '🔵 Surstock',
    'Surstock important': '⚫ Surstock important / Dormant', 'Dormant': '⚫ Dormant',
    'Sans mouvement': '📦 Sans mouvement',
}

def badge_class(series):
    return series.map(lambda v: CLASS_BADGE.get(v, v))

st.markdown(f"<h2 class='woodmat-page-title'>{page}</h2>", unsafe_allow_html=True)

display_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class',
                 'S_12M', 'Moy_Mois_12M', 'S_4M', 'Moy_Mois_4M',
                 'Rotation_Actuelle', 'Rotation_12M', 'Rotation_4M', 'Tendance_Label',
                 'Couverture', 'Taux_Immob', 'Dern_Sortie']
rename_cols = {'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Class': 'Classification',
               'S_12M': 'Sorties 12M', 'Moy_Mois_12M': 'Moy/Mois 12M',
               'S_4M': 'Sorties 4M', 'Moy_Mois_4M': 'Moy/Mois 4M',
               'Rotation_Actuelle': 'Rotation actuelle', 'Rotation_12M': 'Rotation 12M historique',
               'Rotation_4M': 'Rotation 4M',
               'Tendance_Label': 'Tendance 4M vs 12M',
               'Couverture': 'Couv. (mois)', 'Taux_Immob': 'Immob. (%)',
               'Dern_Sortie': 'Dern. Sortie'}

if page == "📦 Réapprovisionnement":
    st.caption("Aide à la décision : articles nécessitant une commande selon leur couverture. Le CUMP n'est pas utilisé.")
    rep = f.copy()
    rep['Action'] = rep['Couverture'].apply(replenishment_action)
    rep['Priorité'] = rep['Couverture'].apply(
        lambda v: '⚪ Sans sortie récente (4M)' if pd.isna(v) else
        ('🔴 Articles critiques' if v < 1 else ('🟠 Réapprovisionnement conseillé' if v <= 2 else '🟢 Stock suffisant')))
    kc1, kc2, kc3, kc4 = st.columns(4)
    filters = {
        '🔴 Articles critiques': rep[rep['Couverture'] < 1],
        '🟠 Réapprovisionnement conseillé': rep[(rep['Couverture'] >= 1) & (rep['Couverture'] <= 2)],
        '🟢 Stock suffisant': rep[rep['Couverture'] > 2],
        '⚪ Sans sortie récente (4M)': rep[rep['Couverture'].isna()],
    }
    for col, label in zip([kc1, kc2, kc3, kc4], filters):
        if col.button(f"{label}\n\n{len(filters[label])} article(s)", use_container_width=True):
            st.session_state['reappro_filter'] = label
    selected_priority = st.session_state.get('reappro_filter')
    if selected_priority:
        st.info(f"Filtre actif : {selected_priority}")
        rep = filters[selected_priority]
    rep_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Rotation_12M', 'Couverture', 'Class', 'Action']
    rep_df = rep[rep_cols].rename(columns={'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Stock': 'Stock actuel', 'Class': 'Classification', 'Couverture': 'Couverture (mois)', 'Rotation_12M': 'Rotation 12M historique'})
    rep_df['Classification'] = badge_class(rep_df['Classification'])
    add_export_buttons(rep_df, 'reapprovisionnement', 'Réapprovisionnement', date_max)
    st.dataframe(rep_df.sort_values('Couverture (mois)'), use_container_width=True, height=520)
    st.stop()

if page == "😴 Stock dormant":
    st.caption("Articles classés Dormant uniquement — recherche, filtres et exports dédiés.")
    dorm = f[f['Class'] == 'Dormant'][display_cols].rename(columns=rename_cols)
    dorm['Classification'] = badge_class(dorm['Classification'])
    add_export_buttons(dorm, 'stock_dormant', 'Stock Dormant', date_max)
    st.dataframe(dorm.sort_values('Immob. (%)', ascending=False), use_container_width=True, height=520)
    st.stop()

if page == "🪵 Stock Bois Rouge":
    st.caption("Articles BOIS ROUGE uniquement — recherche, filtres et exports dédiés.")
    br = f[f['Cat'].astype(str).str.upper().eq('BOIS ROUGE')][display_cols].rename(columns=rename_cols)
    br['Classification'] = badge_class(br['Classification'])
    add_export_buttons(br, 'stock_bois_rouge_articles', 'Articles Bois Rouge', date_max)
    st.dataframe(br, use_container_width=True, height=520)
    st.divider()
    df_st_raw = st.session_state.get("df_st_raw")
    if df_st_raw is not None:
        br_bytes, non_reconnus = generer_excel_bois_rouge(df_st_raw, date_max)
        if br_bytes:
            st.download_button("⬇️ Télécharger la synthèse Qualité × Fournisseur × Dimension", br_bytes,
                               file_name=f"stock_bois_rouge_synthese_{date_max.strftime('%d_%m_%Y')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    st.stop()

if page == "⚠️ Alertes":
    st.caption("Articles en rupture et articles dormants — mêmes filtres que l'analyse courante.")
    alert_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class', 'S_12M', 'S_4M', 'Dern_Sortie']
    alert_df = f[f['Class'].isin(['Rupture', 'Critique', 'Dormant', 'Sans mouvement'])][alert_cols].rename(columns={
        'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité',
        'Class': 'Classification', 'S_12M': 'Sorties 12M', 'S_4M': 'Sorties 4M', 'Dern_Sortie': 'Dern. Sortie'
    })
    if 'Classification' in alert_df.columns:
        alert_df['Classification'] = badge_class(alert_df['Classification']) if 'badge_class' in globals() else alert_df['Classification']
    st.dataframe(alert_df, use_container_width=True, height=520)
    st.stop()

if page == "📄 Rapports":
    st.caption("Exports disponibles pour la vue filtrée courante.")
    report_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class', 'S_12M', 'Moy_Mois_12M',
                   'S_4M', 'Moy_Mois_4M', 'Rotation_Actuelle', 'Rotation_12M', 'Rotation_4M', 'Tendance_Label']
    report_df = f[report_cols].rename(columns=rename_cols)
    add_export_buttons(report_df, 'rapport_rotation', 'Rapport Rotation', date_max)
    st.dataframe(report_df, use_container_width=True, height=460)
    st.stop()

# ── KPIs ─────────────────────────────────────────────────
stock_par_unite = (
    f.assign(Unite_Affichage=f['Unite'].apply(format_unite_stock))
     .groupby('Unite_Affichage', as_index=False)['Stock']
     .sum()
)
unite_order = {'m³': 0, 'm²': 1, 'P': 2, 'ML': 3}
stock_par_unite['_Ordre'] = stock_par_unite['Unite_Affichage'].map(unite_order).fillna(99)
stock_par_unite = stock_par_unite.sort_values(['_Ordre', 'Unite_Affichage'])
volume_stock_html = "<br>".join(
    f"{format_nombre_fr(row.Stock)} {row.Unite_Affichage}"
    for row in stock_par_unite.itertuples(index=False)
) or "—"
# KPI historique — formule d'origine INCHANGÉE (continuité avec les anciens rapports)
# Calcul retenu (Dashboard "Rotation du stock") :
#   Rotation globale = (Somme des Sorties 12M) ÷ (Somme du Stock ACTUEL)
# Justification : le KPI Dashboard doit rester la vue agrégée "Sorties 12M ÷ Stock ACTUEL".
# Remarque importante : on inclut ici l'ensemble des articles disposant d'un stock
# significatif (> SEUIL) pour éviter d'exclure involontairement des références
# dont le stock actuel est non nul (exclusion précédente sur 'Rotation_12M>0' pouvait
# retirer des articles avec sorties mais stock moyen recalculé à zéro, faussant le ratio).
# Ne pas confondre avec les KPI analytiques `rot_globale_12m` (stock moyen) ou
# `Rotation_12M` / `Rotation_Actuelle` individuels qui restent calculés séparément.
_base_rot = f[f['Stock'] > SEUIL]
rot_moy = _base_rot['S_12M'].sum() / _base_rot['Stock'].sum() if _base_rot['Stock'].sum() > 0 else float('nan')

# Nouveau KPI, séparé : Rotation globale 12M sur stock moyen global (ne remplace pas rot_moy)
rot_globale_12m = _base_rot['S_12M'].sum() / _base_rot['Stock_moyen_12M'].sum() if _base_rot['Stock_moyen_12M'].sum() > 0 else float('nan')

# Nouveau KPI, séparé : Rotation globale 4M sur stock moyen global 4M (jamais mélangé au 12M)
_base_rot4 = f[f['Rotation_4M'] > 0]
rot_globale_4m = _base_rot4['S_4M'].sum() / _base_rot4['Stock_moyen_4M'].sum() if _base_rot4['Stock_moyen_4M'].sum() > 0 else float('nan')

n_rupture = len(f[f['Class'] == 'Rupture'])
n_critique = len(f[f['Class'] == 'Critique'])
n_dormant = len(f[f['Class'].isin(['Dormant', 'Sans mouvement'])])
n_alertes = n_rupture + n_critique + n_dormant

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f"<div class='woodmat-kpi-card'><div class='woodmat-kpi-title'>Volume Stock</div>"
        f"<div class='woodmat-kpi-value'>{volume_stock_html}</div></div>",
        unsafe_allow_html=True)
with k2:
    st.metric(
        "Rotation du stock",
        f"{rot_moy:.2f} tours/an" if pd.notna(rot_moy) else "—",
        help="Sorties des 12 derniers mois ÷ Stock ACTUEL total de la catégorie. KPI de référence du Dashboard — inchangé.")
    st.markdown("<div class='woodmat-muted'>Calcul sur les 12 derniers mois — stock actuel</div>", unsafe_allow_html=True)
with k3:
    st.metric(
        "⚠️ Alertes",
        "Articles nécessitant une action",
        help="Regroupe les ruptures de stock, les articles en couverture critique (<1 mois) et les articles sans sortie récente (Dormant / Sans mouvement).")
    st.markdown(
        f"<div class='woodmat-kpi-detail'>Rupture : {n_rupture}<br>"
        f"Critique : {n_critique}<br>"
        f"Dormant / Sans mouvement : {n_dormant}<br><strong>Total : {n_alertes}</strong></div>",
        unsafe_allow_html=True)
with k4:
    st.metric("Articles analysés (références)", len(f))

st.divider()

# ── Graphique évolution des ventes ──────────────────────
gcol, tcol = st.columns([1.3, 1])
with gcol:
    st.markdown("<div class='woodmat-section-title'>Historique des sorties mensuelles</div>", unsafe_allow_html=True)
    st.markdown("<div class='woodmat-muted'>Quantités sorties par mois sur les 12 derniers mois.</div>", unsafe_allow_html=True)
    refs_filtrees = f['Référence'].tolist() if (sel_cats or sel_class or sel_unites or sel_refs or recherche) else None
    evo = evolution_mensuelle(df_mv, refs_filtrees)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=evo['Mois'], y=evo['Qty'], mode='lines+markers',
                              line=dict(color='#1F3864', width=2), fill='tozeroy',
                              fillcolor='rgba(31,56,100,0.1)'))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title=None, yaxis_title="Quantité sortie")
    st.plotly_chart(fig, use_container_width=True)

with tcol:
    st.markdown("<div class='woodmat-section-title'>Répartition des articles par niveau de rotation</div>", unsafe_allow_html=True)
    dist = f['Class'].value_counts().reset_index()
    dist.columns = ['Classification', 'Nb']
    fig2 = px.pie(dist, names='Classification', values='Nb', hole=0.45,
                  color='Classification', color_discrete_map=CLASS_COLORS)
    fig2.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    st.plotly_chart(fig2, use_container_width=True)
    st.markdown("<div class='woodmat-muted'>Classification calculée selon la rotation observée sur les 12 derniers mois.</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='woodmat-legend'>
        <strong>Rupture</strong> → Stock nul.<br>
        <strong>Critique</strong> → Couverture &lt; 1 mois face à la demande récente (4M).<br>
        <strong>Stock faible</strong> → Couverture entre 1 et 3 mois.<br>
        <strong>Normal</strong> → Couverture entre 3 et 6 mois.<br>
        <strong>Bon niveau</strong> → Couverture entre 6 et 12 mois.<br>
        <strong>Surstock</strong> → Couverture entre 12 et 18 mois.<br>
        <strong>Surstock important / Dormant</strong> → Couverture ≥ 18 mois.<br>
        <strong>Dormant</strong> → Déjà vendu par le passé mais aucune sortie sur les 4 derniers mois.<br>
        <strong>Sans mouvement</strong> → Aucune sortie enregistrée depuis l'origine de l'historique.
        </div>
        """,
        unsafe_allow_html=True)

st.divider()

# ── Tableau dynamique ───────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📋 Tableau complet", "😴 Stock dormant", "📅 Historique par année",
                                    "🪵 Stock Bois Rouge"])

with tab1:
    tdf = f[display_cols].rename(columns=rename_cols).sort_values('Rotation actuelle', ascending=False)
    tdf['Classification'] = badge_class(tdf['Classification'])
    st.dataframe(tdf, use_container_width=True, height=480)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        tdf.to_excel(writer, index=False, sheet_name='Rotation Stock')
    st.download_button("⬇️ Exporter Excel (vue actuelle)", buf.getvalue(),
                        file_name=f"rotation_{date_max.strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab2:
    dorm = f[f['Class'] == 'Dormant'][display_cols].rename(columns=rename_cols)
    dorm['Classification'] = badge_class(dorm['Classification'])
    st.caption(f"{len(dorm)} référence(s) dormante(s) — aucune sortie sur les 4 derniers mois "
               f"mais historique de sorties existant.")
    st.dataframe(dorm.sort_values('Immob. (%)', ascending=False),
                 use_container_width=True, height=420)
    buf2 = io.BytesIO()
    with pd.ExcelWriter(buf2, engine='openpyxl') as writer:
        dorm.to_excel(writer, index=False, sheet_name='Stock Dormant')
    st.download_button("⬇️ Exporter Stock Dormant", buf2.getvalue(),
                        file_name=f"stock_dormant_{date_max.strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab3:
    cols_annuelles = st.session_state.get("cols_annuelles", [])
    s_cols = sorted([c for c in cols_annuelles if c.startswith('S_')])
    a_cols = sorted([c for c in cols_annuelles if c.startswith('A_')])
    t_cols = sorted([c for c in cols_annuelles if c.startswith('T_')])

    st.caption("Détail des sorties (S), achats/entrées (A) et nombre de transactions (T) "
               "par référence, année par année — même filtres que le tableau principal.")

    vue = st.radio("Vue", ["Sorties par année", "Achats/Entrées par année", "Nb transactions par année"],
                    horizontal=True)
    if vue == "Sorties par année":
        cols_show = s_cols
    elif vue == "Achats/Entrées par année":
        cols_show = a_cols
    else:
        cols_show = t_cols

    hist_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class'] + cols_show
    hist_cols = [c for c in hist_cols if c in f.columns]
    hdf = f[hist_cols].rename(columns={'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Class': 'Classification'})
    if 'Classification' in hdf.columns:
        hdf['Classification'] = badge_class(hdf['Classification'])
    st.dataframe(hdf, use_container_width=True, height=480)

    buf3 = io.BytesIO()
    with pd.ExcelWriter(buf3, engine='openpyxl') as writer:
        hdf.to_excel(writer, index=False, sheet_name='Historique par annee')
    st.download_button("⬇️ Exporter cette vue", buf3.getvalue(),
                        file_name=f"historique_annuel_{date_max.strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab4:
    df_st_raw = st.session_state.get("df_st_raw")
    if df_st_raw is None or 'Catégorie' not in df_st_raw.columns:
        st.info("Générez d'abord l'analyse (fichier stock actuel) pour voir cet onglet.")
    else:
        st.caption("Stock BOIS ROUGE + BOIS BLANC SUEDE (même famille ENSO/STORA ENSO) par Qualité × "
                   "Fournisseur × Dimension — même mise en forme "
                   "que l'ancien fichier Excel. **ENSO** et **STORA ENSO** sont fusionnés (même fournisseur).")
        br_bytes, non_reconnus = generer_excel_bois_rouge(df_st_raw, date_max)
        if br_bytes is None:
            st.warning("Aucune référence BOIS ROUGE exploitable trouvée dans le stock actuel.")
        else:
            if len(non_reconnus) > 0:
                total_absent = non_reconnus['Quantité'].sum() if 'Quantité' in non_reconnus.columns else 0
                st.warning(f"⚠️ {len(non_reconnus)} référence(s) BOIS ROUGE avec un fournisseur non "
                           f"reconnu ({total_absent:.3f} M3) ne figurent pas dans le tableau ci-dessous. "
                           f"Dites-moi les noms de fournisseurs manquants et je les ajoute.")
            st.download_button("⬇️ Télécharger la feuille Stock Bois Rouge (Excel)", br_bytes,
                                file_name=f"stock_bois_rouge_{date_max.strftime('%d_%m_%Y')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                type="primary")

