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

# ============================================================
# WOODMAT — ROTATION DU STOCK (Web App)
# ============================================================

st.set_page_config(page_title="WOODMAT — Rotation du stock", layout="wide",
                    page_icon="📦", initial_sidebar_state="expanded")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_HISTORIQUE = os.path.join(APP_DIR, "base_mouvements.pkl")  # base 2020-2025, livrée avec l'app
USERS_FILE = os.path.join(APP_DIR, "woodmat_users.json")
SEUIL = 0.001

CLASS_COLORS = {
    'Excellent': '#C6EFCE', 'Bon': '#E2EFDA', 'Stock élevé': '#FFEB9C',
    'Dormant': '#F4B942', 'Rupture': '#FFC7CE',
    'Aucun mouvement 12M': '#E0E0E0', 'Aucun mouvement': '#E0E0E0',
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
    sm = sm.merge(piv_s, left_on='Référence', right_index=True, how='left')
    sm = sm.merge(piv_t, left_on='Référence', right_index=True, how='left')
    sm = sm.merge(piv_a, left_on='Référence', right_index=True, how='left')
    for c in ['Total_Sorti', 'Nb_Trans', 'S_12M', 'T_12M', 'A_12M'] + cols_annuelles:
        sm[c] = sm[c].fillna(0)

    nb_mois_12m = 12.0
    # Calculs vectorisés (pas d'apply row-wise — rapide même sur beaucoup de références)
    sm['Moy_Mois'] = (sm['S_12M'] / nb_mois_12m).round(3)
    stock_ok = sm['Stock'] > SEUIL

    sm['Taux_Rot'] = 0.0
    m = stock_ok & (sm['Moy_Mois'] > 0)
    sm.loc[m, 'Taux_Rot'] = ((sm.loc[m, 'Moy_Mois'] / sm.loc[m, 'Stock']) * 100).round(1)

    sm['Rotation'] = 0.0
    m = stock_ok & (sm['S_12M'] > 0)
    sm.loc[m, 'Rotation'] = (sm.loc[m, 'S_12M'] / sm.loc[m, 'Stock']).round(2)

    sm['Couverture'] = 0.0
    m = (sm['Moy_Mois'] > 0) & stock_ok
    sm.loc[m, 'Couverture'] = (sm.loc[m, 'Stock'] / sm.loc[m, 'Moy_Mois']).round(1)

    sm['Delai'] = 0.0
    m = sm['Rotation'] > 0
    sm.loc[m, 'Delai'] = (365 / sm.loc[m, 'Rotation']).round(0)

    sm['Taux_Immob'] = 0.0
    m = sm['Couverture'] > 0
    sm.loc[m, 'Taux_Immob'] = (sm.loc[m, 'Couverture'] / 12 * 100).clip(upper=100.0).round(1)
    sm.loc[(~m) & stock_ok, 'Taux_Immob'] = 100.0

    conditions_rupture = sm['Stock'] <= SEUIL
    conditions_dormant = (~conditions_rupture) & (sm['S_12M'] == 0) & (sm['Total_Sorti'] > 0)
    conditions_aucun = (~conditions_rupture) & (sm['S_12M'] == 0) & (sm['Total_Sorti'] == 0)
    conditions_excellent = (~conditions_rupture) & (sm['S_12M'] > 0) & (sm['Taux_Rot'] >= 20)
    conditions_bon = (~conditions_rupture) & (sm['S_12M'] > 0) & (sm['Taux_Rot'] >= 10) & (sm['Taux_Rot'] < 20)

    sm['Class'] = 'Stock élevé'
    sm.loc[conditions_rupture, 'Class'] = 'Rupture'
    sm.loc[conditions_dormant, 'Class'] = 'Dormant'
    sm.loc[conditions_aucun, 'Class'] = 'Aucun mouvement 12M'
    sm.loc[conditions_excellent, 'Class'] = 'Excellent'
    sm.loc[conditions_bon, 'Class'] = 'Bon'

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
            st.session_state["sm"] = smimport streamlit as st
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

# ============================================================
# WOODMAT — ROTATION DU STOCK (Web App)
# ============================================================

st.set_page_config(page_title="WOODMAT — Rotation du stock", layout="wide",
                    page_icon="📦", initial_sidebar_state="expanded")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_HISTORIQUE = os.path.join(APP_DIR, "base_mouvements.pkl")  # base 2020-2025, livrée avec l'app
USERS_FILE = os.path.join(APP_DIR, "woodmat_users.json")
SEUIL = 0.001

CLASS_COLORS = {
    'Excellent': '#C6EFCE', 'Bon': '#E2EFDA', 'Stock élevé': '#FFEB9C',
    'Dormant': '#F4B942', 'Rupture': '#FFC7CE',
    'Aucun mouvement 12M': '#E0E0E0', 'Aucun mouvement': '#E0E0E0',
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
    sm = sm.merge(piv_s, left_on='Référence', right_index=True, how='left')
    sm = sm.merge(piv_t, left_on='Référence', right_index=True, how='left')
    sm = sm.merge(piv_a, left_on='Référence', right_index=True, how='left')
    for c in ['Total_Sorti', 'Nb_Trans', 'S_12M', 'T_12M', 'A_12M'] + cols_annuelles:
        sm[c] = sm[c].fillna(0)

    nb_mois_12m = 12.0
    # Calculs vectorisés (pas d'apply row-wise — rapide même sur beaucoup de références)
    sm['Moy_Mois'] = (sm['S_12M'] / nb_mois_12m).round(3)
    stock_ok = sm['Stock'] > SEUIL

    sm['Taux_Rot'] = 0.0
    m = stock_ok & (sm['Moy_Mois'] > 0)
    sm.loc[m, 'Taux_Rot'] = ((sm.loc[m, 'Moy_Mois'] / sm.loc[m, 'Stock']) * 100).round(1)

    sm['Rotation'] = 0.0
    m = stock_ok & (sm['S_12M'] > 0)
    sm.loc[m, 'Rotation'] = (sm.loc[m, 'S_12M'] / sm.loc[m, 'Stock']).round(2)

    sm['Couverture'] = 0.0
    m = (sm['Moy_Mois'] > 0) & stock_ok
    sm.loc[m, 'Couverture'] = (sm.loc[m, 'Stock'] / sm.loc[m, 'Moy_Mois']).round(1)

    sm['Delai'] = 0.0
    m = sm['Rotation'] > 0
    sm.loc[m, 'Delai'] = (365 / sm.loc[m, 'Rotation']).round(0)

    sm['Taux_Immob'] = 0.0
    m = sm['Couverture'] > 0
    sm.loc[m, 'Taux_Immob'] = (sm.loc[m, 'Couverture'] / 12 * 100).clip(upper=100.0).round(1)
    sm.loc[(~m) & stock_ok, 'Taux_Immob'] = 100.0

    conditions_rupture = sm['Stock'] <= SEUIL
    conditions_dormant = (~conditions_rupture) & (sm['S_12M'] == 0) & (sm['Total_Sorti'] > 0)
    conditions_aucun = (~conditions_rupture) & (sm['S_12M'] == 0) & (sm['Total_Sorti'] == 0)
    conditions_excellent = (~conditions_rupture) & (sm['S_12M'] > 0) & (sm['Taux_Rot'] >= 20)
    conditions_bon = (~conditions_rupture) & (sm['S_12M'] > 0) & (sm['Taux_Rot'] >= 10) & (sm['Taux_Rot'] < 20)

    sm['Class'] = 'Stock élevé'
    sm.loc[conditions_rupture, 'Class'] = 'Rupture'
    sm.loc[conditions_dormant, 'Class'] = 'Dormant'
    sm.loc[conditions_aucun, 'Class'] = 'Aucun mouvement 12M'
    sm.loc[conditions_excellent, 'Class'] = 'Excellent'
    sm.loc[conditions_bon, 'Class'] = 'Bon'

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
    st.markdown("<h2 class='woodmat-page-title'>📈 Analyses avancées</h2>", unsafe_allow_html=True)

    if sm is None:
        st.info("⬅️ Importez le **stock actuel** (et les mouvements de l'année en cours si disponibles) "
                "dans la barre latérale, puis cliquez sur **Générer l'analyse**.")
        st.stop()

    df_mv_a = st.session_state.get("df_mv")
    date_max_a = st.session_state.get("date_max")
    date_12m_debut_a = st.session_state.get("date_12m_debut")

    # ── Filtre catégorie pour les analyses ──────────────────
    cats_a = sorted(sm['Cat'].dropna().unique())
    sel_cats_a = st.multiselect("Filtrer par catégorie", cats_a, default=[], key="analyse_cat")
    df_a = sm.copy()
    if sel_cats_a:
        df_a = df_a[df_a['Cat'].isin(sel_cats_a)]

    # ── Références actives (sorties > 0 sur 12M) ────────────
    df_actif = df_a[df_a['S_12M'] > 0].copy()

    # ════════════════════════════════════════════
    # CALCUL ABC — basé sur les quantités sorties
    # ════════════════════════════════════════════
    df_abc = df_actif.sort_values('S_12M', ascending=False).copy().reset_index(drop=True)
    total_sorties = df_abc['S_12M'].sum() if len(df_abc) > 0 else 1
    df_abc['Cumul_Sorties'] = df_abc['S_12M'].cumsum()
    df_abc['Cumul_Pct'] = (df_abc['Cumul_Sorties'] / total_sorties * 100).round(2)
    df_abc['Classe_ABC'] = 'C'
    df_abc.loc[df_abc['Cumul_Pct'] <= 80, 'Classe_ABC'] = 'A'
    df_abc.loc[(df_abc['Cumul_Pct'] > 80) & (df_abc['Cumul_Pct'] <= 95), 'Classe_ABC'] = 'B'

    # ════════════════════════════════════════════
    # CALCUL XYZ — régularité mensuelle (CV)
    # ════════════════════════════════════════════
    refs_actifs = set(df_actif['Référence'].tolist())
    sorties_12m_raw = df_mv_a[
        (df_mv_a['ES'] == 'S') &
        (df_mv_a['Date'] >= date_12m_debut_a) &
        (df_mv_a['Date'] <= date_max_a) &
        (df_mv_a['Reference'].isin(refs_actifs))
    ].copy()
    sorties_12m_raw['Mois'] = sorties_12m_raw['Date'].dt.to_period('M')

    pivot_mois = sorties_12m_raw.groupby(['Reference', 'Mois'])['Qty'].sum().unstack(fill_value=0)
    all_months = pd.period_range(start=date_12m_debut_a.to_period('M'), periods=12, freq='M')
    for m in all_months:
        if m not in pivot_mois.columns:
            pivot_mois[m] = 0.0
    if len(pivot_mois.columns) > 0:
        pivot_mois = pivot_mois[[m for m in all_months if m in pivot_mois.columns]]

    if len(pivot_mois) > 0:
        _mean = pivot_mois.mean(axis=1)
        _std  = pivot_mois.std(axis=1)
        _cv   = (_std / _mean.replace(0, float('nan'))).fillna(float('inf'))
        xyz_df = pd.DataFrame({'Reference': pivot_mois.index, 'CV': _cv.values})
    else:
        xyz_df = pd.DataFrame({'Reference': [], 'CV': []})
    xyz_df['Classe_XYZ'] = 'Z'
    xyz_df.loc[xyz_df['CV'] < 0.5, 'Classe_XYZ'] = 'X'
    xyz_df.loc[(xyz_df['CV'] >= 0.5) & (xyz_df['CV'] < 1.0), 'Classe_XYZ'] = 'Y'

    # ── Fusion ABC + XYZ ────────────────────────────────────
    df_abc = df_abc.merge(xyz_df, left_on='Référence', right_on='Reference', how='left')
    df_abc['Classe_XYZ']   = df_abc['Classe_XYZ'].fillna('Z')
    df_abc['CV']           = df_abc['CV'].fillna(float('inf'))
    df_abc['Classe_ABCXYZ'] = df_abc['Classe_ABC'] + df_abc['Classe_XYZ']

    ABC_COLORS  = {'A': '#1F3864', 'B': '#B88A44', 'C': '#94A3B8'}
    XYZ_COLORS  = {'X': '#196F3D', 'Y': '#B7410E', 'Z': '#6C3483'}
    ABCXYZ_COLORS = {
        'AX': '#1F3864', 'AY': '#2E5DA8', 'AZ': '#7BA7E0',
        'BX': '#B88A44', 'BY': '#D4A85A', 'BZ': '#EDD090',
        'CX': '#94A3B8', 'CY': '#B0BEC5', 'CZ': '#CFD8DC',
    }

    # ════════════════════════════════════════════
    # ONGLETS
    # ════════════════════════════════════════════
    (tab_dash, tab_abc_t, tab_xyz_t, tab_matrix,
     tab_pareto, tab_topflop, tab_cat, tab_evo) = st.tabs([
        "🎯 Dashboard synthétique", "🅰 Analyse ABC", "🔀 Analyse XYZ",
        "🔢 Matrice ABC/XYZ", "📈 Pareto", "🏆 Top / Flop",
        "📂 Par catégorie", "📅 Évolution mensuelle"
    ])

    # ────────────────────────────────────────────
    # ONGLET 1 : Dashboard synthétique
    # ────────────────────────────────────────────
    with tab_dash:
        st.markdown("<div class='woodmat-section-title'>Tableau de bord — synthèse des analyses</div>", unsafe_allow_html=True)
        st.markdown("<div class='woodmat-muted'>Vue consolidée : ABC, XYZ et rotation du stock sur les 12 derniers mois.</div>", unsafe_allow_html=True)

        n_refs   = len(df_a)
        n_actifs = len(df_actif)
        n_inactifs = n_refs - n_actifs
        pct_a = round(len(df_abc[df_abc['Classe_ABC'] == 'A']) / max(n_actifs, 1) * 100, 1)
        pct_x = round(len(df_abc[df_abc['Classe_XYZ'] == 'X']) / max(n_actifs, 1) * 100, 1)

        dk1, dk2, dk3, dk4, dk5 = st.columns(5)
        dk1.metric("Références totales", f"{n_refs:,}".replace(',', ' '))
        dk2.metric("Références actives (12M)", f"{n_actifs:,}".replace(',', ' '))
        dk3.metric("Sans sortie 12M", f"{n_inactifs:,}".replace(',', ' '))
        dk4.metric("Classe A (critiques)", f"{pct_a} %")
        dk5.metric("Classe X (régulières)", f"{pct_x} %")

        st.divider()
        dc1, dc2, dc3 = st.columns(3)

        with dc1:
            st.markdown("<div class='woodmat-section-title'>Répartition ABC (nbre références)</div>", unsafe_allow_html=True)
            abc_cnt = df_abc['Classe_ABC'].value_counts().reset_index()
            abc_cnt.columns = ['Classe', 'N']
            abc_cnt['Pct'] = (abc_cnt['N'] / abc_cnt['N'].sum() * 100).round(1)
            fig_d1 = px.pie(abc_cnt, names='Classe', values='N', hole=0.5,
                            color='Classe', color_discrete_map=ABC_COLORS,
                            custom_data=['Pct'])
            fig_d1.update_traces(texttemplate='%{label}<br>%{customdata[0]:.1f}%')
            fig_d1.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig_d1, use_container_width=True)

        with dc2:
            st.markdown("<div class='woodmat-section-title'>Répartition XYZ (nbre références)</div>", unsafe_allow_html=True)
            xyz_cnt = df_abc['Classe_XYZ'].value_counts().reset_index()
            xyz_cnt.columns = ['Classe', 'N']
            xyz_cnt['Pct'] = (xyz_cnt['N'] / xyz_cnt['N'].sum() * 100).round(1)
            fig_d2 = px.pie(xyz_cnt, names='Classe', values='N', hole=0.5,
                            color='Classe', color_discrete_map=XYZ_COLORS,
                            custom_data=['Pct'])
            fig_d2.update_traces(texttemplate='%{label}<br>%{customdata[0]:.1f}%')
            fig_d2.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig_d2, use_container_width=True)

        with dc3:
            st.markdown("<div class='woodmat-section-title'>Top 5 sorties 12M</div>", unsafe_allow_html=True)
            top5 = df_abc.nlargest(5, 'S_12M')[['Référence', 'S_12M', 'Cat', 'Classe_ABC']].copy()
            top5['S_12M'] = top5['S_12M'].round(2)
            fig_d3 = px.bar(top5, x='S_12M', y='Référence', orientation='h',
                            color='Classe_ABC', color_discrete_map=ABC_COLORS,
                            labels={'S_12M': 'Qté sortie 12M', 'Référence': ''})
            fig_d3.update_layout(height=300, margin=dict(l=0, r=10, t=10, b=0),
                                  yaxis=dict(autorange='reversed'), showlegend=False)
            st.plotly_chart(fig_d3, use_container_width=True)

        st.divider()
        st.markdown("<div class='woodmat-section-title'>Matrice ABC/XYZ — vue synthétique</div>", unsafe_allow_html=True)
        matrix_dash = df_abc.groupby(['Classe_ABC', 'Classe_XYZ']).agg(
            Nb=('Référence', 'count'), Total_Sorti=('S_12M', 'sum')).reset_index()
        matrix_dash['Pct_Sorties'] = (matrix_dash['Total_Sorti'] / total_sorties * 100).round(1)
        matrix_pivot = matrix_dash.pivot(index='Classe_ABC', columns='Classe_XYZ', values='Nb').fillna(0).astype(int)
        matrix_pivot = matrix_pivot.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'], fill_value=0)
        fig_heat = go.Figure(data=go.Heatmap(
            z=matrix_pivot.values, x=matrix_pivot.columns.tolist(), y=matrix_pivot.index.tolist(),
            text=matrix_pivot.values, texttemplate="%{text}", textfont={"size": 18},
            colorscale=[[0, '#EEF2FF'], [1, '#1F3864']], showscale=False))
        fig_heat.update_layout(height=300, margin=dict(l=40, r=10, t=10, b=40),
                                xaxis_title="Classe XYZ (régularité)", yaxis_title="Classe ABC (volume)")
        st.plotly_chart(fig_heat, use_container_width=True)
        st.markdown("""
        <div class='woodmat-legend'>
        <strong>AX</strong> : produits à fort volume et très réguliers → priorité absolue de stock.<br>
        <strong>AZ</strong> : fort volume mais très irréguliers → surveiller attentivement.<br>
        <strong>CZ</strong> : faible volume et irréguliers → candidats à la rationalisation.
        </div>""", unsafe_allow_html=True)

        # Export
        st.divider()
        export_dash = df_abc[['Référence', 'Designation', 'Cat', 'Unite', 'Stock',
                               'S_12M', 'Classe_ABC', 'Classe_XYZ', 'Classe_ABCXYZ', 'CV']].copy()
        export_dash.columns = ['Référence', 'Désignation', 'Catégorie', 'Unité', 'Stock actuel',
                                'Sorties 12M', 'Classe ABC', 'Classe XYZ', 'Classe ABC/XYZ', 'Coeff. Variation']
        add_export_buttons(export_dash, 'dashboard_analyses', 'Dashboard Analyses', date_max_a)

    # ────────────────────────────────────────────
    # ONGLET 2 : Analyse ABC
    # ────────────────────────────────────────────
    with tab_abc_t:
        st.markdown("<div class='woodmat-section-title'>Analyse ABC — par quantités sorties sur 12 mois</div>", unsafe_allow_html=True)
        st.markdown("""<div class='woodmat-muted'>
        <strong>Classe A</strong> : 80 % du volume de sorties (peu de références, fort impact).<br>
        <strong>Classe B</strong> : 80–95 % du volume.<br>
        <strong>Classe C</strong> : 95–100 % du volume (beaucoup de références, faible impact individuel).
        </div>""", unsafe_allow_html=True)

        abc_summary = df_abc.groupby('Classe_ABC').agg(
            Nb_refs=('Référence', 'count'),
            Total_Sorti=('S_12M', 'sum'),
            Stock_total=('Stock', 'sum')
        ).reset_index()
        abc_summary['% Références'] = (abc_summary['Nb_refs'] / abc_summary['Nb_refs'].sum() * 100).round(1)
        abc_summary['% Sorties']    = (abc_summary['Total_Sorti'] / total_sorties * 100).round(1)
        abc_summary['Total_Sorti']  = abc_summary['Total_Sorti'].round(2)
        abc_summary['Stock_total']  = abc_summary['Stock_total'].round(2)

        ac1, ac2 = st.columns([1, 1.6])
        with ac1:
            st.markdown("**Synthèse par classe**")
            st.dataframe(abc_summary.rename(columns={
                'Classe_ABC': 'Classe', 'Nb_refs': 'Nb références',
                'Total_Sorti': 'Total sorti 12M', 'Stock_total': 'Stock total'}),
                use_container_width=True, height=200)

        with ac2:
            fig_abc_bar = go.Figure()
            for classe, col in ABC_COLORS.items():
                sub = abc_summary[abc_summary['Classe_ABC'] == classe]
                if len(sub) > 0:
                    fig_abc_bar.add_trace(go.Bar(
                        name=f"Classe {classe}", x=[f"Classe {classe}"],
                        y=sub['% Sorties'].values, marker_color=col,
                        text=sub['% Sorties'].values, texttemplate='%{text:.1f}%', textposition='inside'))
            fig_abc_bar.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                                       yaxis_title="% des sorties 12M", showlegend=True)
            st.plotly_chart(fig_abc_bar, use_container_width=True)

        st.divider()
        st.markdown("**Détail des références — classées par Classe ABC puis sorties décroissantes**")
        abc_detail = df_abc[['Classe_ABC', 'Référence', 'Designation', 'Cat', 'Unite',
                              'S_12M', 'Stock', 'Cumul_Pct']].copy()
        abc_detail.columns = ['Classe ABC', 'Référence', 'Désignation', 'Catégorie', 'Unité',
                               'Sorties 12M', 'Stock actuel', 'Cumul %']
        abc_detail['Sorties 12M']  = abc_detail['Sorties 12M'].round(3)
        abc_detail['Stock actuel'] = abc_detail['Stock actuel'].round(3)
        abc_detail['Cumul %']      = abc_detail['Cumul %'].round(2)
        st.dataframe(abc_detail.sort_values(['Classe ABC', 'Sorties 12M'], ascending=[True, False]),
                     use_container_width=True, height=460)
        add_export_buttons(abc_detail, 'analyse_ABC', 'Analyse ABC', date_max_a)

    # ────────────────────────────────────────────
    # ONGLET 3 : Analyse XYZ
    # ────────────────────────────────────────────
    with tab_xyz_t:
        st.markdown("<div class='woodmat-section-title'>Analyse XYZ — régularité des sorties mensuelles</div>", unsafe_allow_html=True)
        st.markdown("""<div class='woodmat-muted'>
        Le coefficient de variation (CV = écart-type / moyenne mensuelle) mesure l'irrégularité des sorties.<br>
        <strong>X</strong> : CV &lt; 0,50 → sorties très régulières. &nbsp;
        <strong>Y</strong> : CV 0,50–1,00 → sorties modérément régulières. &nbsp;
        <strong>Z</strong> : CV &gt; 1,00 → sorties très irrégulières.
        </div>""", unsafe_allow_html=True)

        xyz_summary = df_abc.groupby('Classe_XYZ').agg(
            Nb_refs=('Référence', 'count'),
            CV_moy=('CV', lambda x: x[x < float('inf')].mean()),
            Total_Sorti=('S_12M', 'sum')
        ).reset_index()
        xyz_summary['CV_moy'] = xyz_summary['CV_moy'].round(3)
        xyz_summary['% Références'] = (xyz_summary['Nb_refs'] / xyz_summary['Nb_refs'].sum() * 100).round(1)

        xc1, xc2 = st.columns([1, 1.6])
        with xc1:
            st.markdown("**Synthèse par classe**")
            st.dataframe(xyz_summary.rename(columns={
                'Classe_XYZ': 'Classe', 'Nb_refs': 'Nb références',
                'CV_moy': 'CV moyen', 'Total_Sorti': 'Total sorti 12M'}),
                use_container_width=True, height=200)

        with xc2:
            fig_xyz = px.bar(xyz_summary, x='Classe_XYZ', y='Nb_refs',
                             color='Classe_XYZ', color_discrete_map=XYZ_COLORS,
                             text='% Références', labels={'Nb_refs': 'Nb références', 'Classe_XYZ': 'Classe XYZ'})
            fig_xyz.update_traces(texttemplate='%{text:.1f}%', textposition='inside')
            fig_xyz.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            st.plotly_chart(fig_xyz, use_container_width=True)

        st.divider()
        # Distribution des CV
        df_cv_plot = df_abc[df_abc['CV'] < float('inf')].copy()
        fig_cv = px.histogram(df_cv_plot, x='CV', color='Classe_XYZ', nbins=40,
                              color_discrete_map=XYZ_COLORS,
                              labels={'CV': 'Coefficient de variation', 'count': 'Nb références'},
                              title="Distribution des coefficients de variation")
        fig_cv.add_vline(x=0.5, line_dash='dash', line_color='#B88A44', annotation_text='X/Y (0.5)')
        fig_cv.add_vline(x=1.0, line_dash='dash', line_color='#1F3864', annotation_text='Y/Z (1.0)')
        fig_cv.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_cv, use_container_width=True)

        st.markdown("**Détail des références XYZ**")
        xyz_detail = df_abc[['Classe_XYZ', 'Référence', 'Designation', 'Cat', 'Unite', 'S_12M', 'CV']].copy()
        xyz_detail['CV'] = xyz_detail['CV'].apply(lambda v: round(v, 3) if v < float('inf') else '∞')
        xyz_detail.columns = ['Classe XYZ', 'Référence', 'Désignation', 'Catégorie', 'Unité', 'Sorties 12M', 'CV']
        st.dataframe(xyz_detail.sort_values(['Classe XYZ', 'Sorties 12M'], ascending=[True, False]),
                     use_container_width=True, height=420)
        export_xyz = xyz_detail.copy()
        export_xyz['CV'] = export_xyz['CV'].astype(str)
        add_export_buttons(export_xyz, 'analyse_XYZ', 'Analyse XYZ', date_max_a)

    # ────────────────────────────────────────────
    # ONGLET 4 : Matrice ABC/XYZ
    # ────────────────────────────────────────────
    with tab_matrix:
        st.markdown("<div class='woodmat-section-title'>Matrice ABC/XYZ — croisement volume × régularité</div>", unsafe_allow_html=True)
        st.markdown("""<div class='woodmat-muted'>
        Chaque cellule donne le nombre de références dans cette combinaison.
        La couleur indique l'intensité (nombre de références). Les 9 combinaisons guident les décisions de stock et d'approvisionnement.
        </div>""", unsafe_allow_html=True)

        matrix_full = df_abc.groupby(['Classe_ABC', 'Classe_XYZ']).agg(
            Nb=('Référence', 'count'),
            Sorties=('S_12M', 'sum')
        ).reset_index()
        matrix_full['Pct_Vol'] = (matrix_full['Sorties'] / total_sorties * 100).round(1)

        matrix_nb  = matrix_full.pivot(index='Classe_ABC', columns='Classe_XYZ', values='Nb').fillna(0).astype(int)
        matrix_pct = matrix_full.pivot(index='Classe_ABC', columns='Classe_XYZ', values='Pct_Vol').fillna(0)
        matrix_nb  = matrix_nb.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'], fill_value=0)
        matrix_pct = matrix_pct.reindex(index=['A', 'B', 'C'], columns=['X', 'Y', 'Z'], fill_value=0.0)

        text_matrix = [[
            f"<b>{matrix_nb.loc[r, c]}</b> réf.<br>{matrix_pct.loc[r, c]:.1f}% vol."
            for c in ['X', 'Y', 'Z']]
            for r in ['A', 'B', 'C']]

        fig_matrix = go.Figure(data=go.Heatmap(
            z=matrix_nb.values, x=['X — Régulier', 'Y — Variable', 'Z — Irrégulier'],
            y=['A — Fort volume', 'B — Volume moyen', 'C — Faible volume'],
            text=text_matrix, texttemplate='%{text}',
            colorscale=[[0, '#EEF2FF'], [0.5, '#93C5FD'], [1, '#1F3864']],
            showscale=True, colorbar=dict(title='Nb réf.')))
        fig_matrix.update_layout(height=380, margin=dict(l=150, r=20, t=20, b=60),
                                  xaxis_title="Régularité (XYZ)", yaxis_title="Volume (ABC)",
                                  yaxis=dict(autorange='reversed'))
        st.plotly_chart(fig_matrix, use_container_width=True)

        st.divider()
        st.markdown("**Recommandations par combinaison**")
        recommandations = {
            'AX': ('Fort volume, très régulier', '🟢 Stock de sécurité élevé, réapprovisionnement automatique'),
            'AY': ('Fort volume, variable', '🟡 Stock tampon conseillé, suivi rapproché'),
            'AZ': ('Fort volume, très irrégulier', '🔴 Anticiper les pics, éviter les ruptures'),
            'BX': ('Volume moyen, régulier', '🟢 Réapprovisionnement planifié'),
            'BY': ('Volume moyen, variable', '🟡 Stock de sécurité modéré'),
            'BZ': ('Volume moyen, irrégulier', '🟠 Commandes à la demande'),
            'CX': ('Faible volume, régulier', '🟢 Petits stocks permanents suffisants'),
            'CY': ('Faible volume, variable', '🟡 Réapprovisionnement ponctuel'),
            'CZ': ('Faible volume, irrégulier', '🔴 Rationaliser — candidat à l\'abandon'),
        }
        rec_df = pd.DataFrame([
            {'Combinaison': k, 'Description': v[0], 'Recommandation': v[1]}
            for k, v in recommandations.items()
        ])
        st.dataframe(rec_df, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**Détail des références par combinaison ABC/XYZ**")
        matrix_detail = df_abc[['Classe_ABCXYZ', 'Classe_ABC', 'Classe_XYZ', 'Référence',
                                 'Designation', 'Cat', 'Unite', 'S_12M', 'Stock', 'CV']].copy()
        matrix_detail['CV'] = matrix_detail['CV'].apply(lambda v: round(v, 3) if v < float('inf') else float('inf'))
        matrix_detail.columns = ['Combinaison', 'Classe ABC', 'Classe XYZ', 'Référence',
                                  'Désignation', 'Catégorie', 'Unité', 'Sorties 12M', 'Stock actuel', 'CV']
        st.dataframe(matrix_detail.sort_values(['Combinaison', 'Sorties 12M'], ascending=[True, False]),
                     use_container_width=True, height=440)
        export_mat = matrix_detail.copy()
        export_mat['CV'] = export_mat['CV'].astype(str)
        add_export_buttons(export_mat, 'matrice_ABCXYZ', 'Matrice ABC-XYZ', date_max_a)

    # ────────────────────────────────────────────
    # ONGLET 5 : Pareto
    # ────────────────────────────────────────────
    with tab_pareto:
        st.markdown("<div class='woodmat-section-title'>Courbe de Pareto — loi 80/20 sur les sorties 12M</div>", unsafe_allow_html=True)
        st.markdown("<div class='woodmat-muted'>La courbe montre le pourcentage cumulé des sorties en fonction du nombre de références, triées par volume décroissant.</div>", unsafe_allow_html=True)

        pareto_df = df_abc[['Référence', 'S_12M', 'Classe_ABC', 'Cumul_Pct']].copy().reset_index(drop=True)
        pareto_df['Nb_Refs_Cum'] = range(1, len(pareto_df) + 1)
        pareto_df['Pct_Refs']    = (pareto_df['Nb_Refs_Cum'] / len(pareto_df) * 100).round(2)

        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(
            x=pareto_df['Pct_Refs'], y=pareto_df['S_12M'],
            marker_color=pareto_df['Classe_ABC'].map(ABC_COLORS),
            name='Sorties 12M', opacity=0.7))
        fig_pareto.add_trace(go.Scatter(
            x=pareto_df['Pct_Refs'], y=pareto_df['Cumul_Pct'],
            mode='lines', name='Cumul %', yaxis='y2',
            line=dict(color='#B88A44', width=2.5)))
        fig_pareto.add_hline(y=80, line_dash='dash', line_color='#1F3864',
                              annotation_text='80 %', yref='y2')
        fig_pareto.add_hline(y=95, line_dash='dot', line_color='#94A3B8',
                              annotation_text='95 %', yref='y2')
        fig_pareto.update_layout(
            height=420, margin=dict(l=10, r=10, t=10, b=30),
            xaxis_title='% des références (triées par volume décroissant)',
            yaxis=dict(title='Sorties 12M'),
            yaxis2=dict(title='Cumul %', overlaying='y', side='right', range=[0, 105]),
            legend=dict(orientation='h', y=1.05))
        st.plotly_chart(fig_pareto, use_container_width=True)

        # Seuils A/B/C
        seuil_a = pareto_df[pareto_df['Classe_ABC'] == 'A']['Pct_Refs'].max() if 'A' in pareto_df['Classe_ABC'].values else 0
        seuil_b = pareto_df[pareto_df['Classe_ABC'].isin(['A', 'B'])]['Pct_Refs'].max() if 'B' in pareto_df['Classe_ABC'].values else 0
        nb_a = len(pareto_df[pareto_df['Classe_ABC'] == 'A'])
        nb_b = len(pareto_df[pareto_df['Classe_ABC'] == 'B'])
        nb_c = len(pareto_df[pareto_df['Classe_ABC'] == 'C'])
        st.markdown(f"""<div class='woodmat-legend'>
        <strong>Classe A</strong> : {nb_a} références ({seuil_a:.1f}% du catalogue) → 80% des sorties.<br>
        <strong>Classe B</strong> : {nb_b} références ({seuil_b - seuil_a:.1f}% du catalogue) → 15% des sorties.<br>
        <strong>Classe C</strong> : {nb_c} références ({100 - seuil_b:.1f}% du catalogue) → 5% des sorties.
        </div>""", unsafe_allow_html=True)

        st.divider()
        pareto_export = pareto_df[['Référence', 'S_12M', 'Classe_ABC', 'Cumul_Pct', 'Pct_Refs']].copy()
        pareto_export.columns = ['Référence', 'Sorties 12M', 'Classe ABC', 'Cumul sorties %', '% Refs cumulées']
        add_export_buttons(pareto_export, 'pareto_sorties', 'Pareto Sorties', date_max_a)

    # ────────────────────────────────────────────
    # ONGLET 6 : Top / Flop
    # ────────────────────────────────────────────
    with tab_topflop:
        st.markdown("<div class='woodmat-section-title'>Top et Flop des références — sorties 12 mois</div>", unsafe_allow_html=True)
        n_topflop = st.slider("Nombre de références à afficher", 5, 30, 10, key="n_topflop")

        top_n  = df_abc.nlargest(n_topflop, 'S_12M')
        flop_n = df_abc[df_abc['S_12M'] > 0].nsmallest(n_topflop, 'S_12M')

        tf1, tf2 = st.columns(2)
        with tf1:
            st.markdown(f"**🏆 Top {n_topflop} — plus fortes sorties**")
            fig_top = px.bar(top_n.sort_values('S_12M'), x='S_12M', y='Référence',
                             orientation='h', color='Classe_ABC', color_discrete_map=ABC_COLORS,
                             text='S_12M', labels={'S_12M': 'Qté sortie 12M', 'Référence': ''})
            fig_top.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_top.update_layout(height=max(320, n_topflop * 28), margin=dict(l=0, r=60, t=10, b=10),
                                   showlegend=False, yaxis=dict(autorange='reversed' if False else True))
            st.plotly_chart(fig_top, use_container_width=True)

        with tf2:
            st.markdown(f"**📉 Flop {n_topflop} — plus faibles sorties (actives)**")
            fig_flop = px.bar(flop_n.sort_values('S_12M', ascending=False), x='S_12M', y='Référence',
                              orientation='h', color='Classe_ABC', color_discrete_map=ABC_COLORS,
                              text='S_12M', labels={'S_12M': 'Qté sortie 12M', 'Référence': ''})
            fig_flop.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_flop.update_layout(height=max(320, n_topflop * 28), margin=dict(l=0, r=60, t=10, b=10),
                                    showlegend=False)
            st.plotly_chart(fig_flop, use_container_width=True)

        st.divider()
        tf_c1, tf_c2 = st.columns(2)
        with tf_c1:
            top_exp = top_n[['Référence', 'Designation', 'Cat', 'Unite', 'S_12M', 'Stock', 'Classe_ABC']].copy()
            top_exp.columns = ['Référence', 'Désignation', 'Catégorie', 'Unité', 'Sorties 12M', 'Stock', 'Classe ABC']
            st.markdown(f"**Détail Top {n_topflop}**")
            st.dataframe(top_exp.sort_values('Sorties 12M', ascending=False), use_container_width=True, height=300)
        with tf_c2:
            flop_exp = flop_n[['Référence', 'Designation', 'Cat', 'Unite', 'S_12M', 'Stock', 'Classe_ABC']].copy()
            flop_exp.columns = ['Référence', 'Désignation', 'Catégorie', 'Unité', 'Sorties 12M', 'Stock', 'Classe ABC']
            st.markdown(f"**Détail Flop {n_topflop}**")
            st.dataframe(flop_exp.sort_values('Sorties 12M'), use_container_width=True, height=300)

        buf_tf = io.BytesIO()
        with pd.ExcelWriter(buf_tf, engine='openpyxl') as writer:
            top_exp.to_excel(writer, index=False, sheet_name=f'Top {n_topflop}')
            flop_exp.to_excel(writer, index=False, sheet_name=f'Flop {n_topflop}')
        st.download_button("⬇️ Exporter Top/Flop Excel", buf_tf.getvalue(),
                           file_name=f"top_flop_{date_max_a.strftime('%d_%m_%Y')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ────────────────────────────────────────────
    # ONGLET 7 : Analyse par catégorie
    # ────────────────────────────────────────────
    with tab_cat:
        st.markdown("<div class='woodmat-section-title'>Analyse par catégorie</div>", unsafe_allow_html=True)
        st.markdown("<div class='woodmat-muted'>Agrégation des indicateurs de rotation et de stock par famille de produits.</div>", unsafe_allow_html=True)

        cat_agg = df_a.groupby('Cat').agg(
            Nb_refs=('Référence', 'count'),
            Stock_total=('Stock', 'sum'),
            Sorties_12M=('S_12M', 'sum'),
            Refs_actives=('S_12M', lambda x: (x > 0).sum()),
            Refs_dormantes=('Class', lambda x: (x == 'Dormant').sum()),
            Refs_rupture=('Class', lambda x: (x == 'Rupture').sum()),
        ).reset_index()
        cat_agg['% Refs actives'] = (cat_agg['Refs_actives'] / cat_agg['Nb_refs'].replace(0, 1) * 100).round(1)
        cat_agg['Pct_Vol']        = (cat_agg['Sorties_12M'] / cat_agg['Sorties_12M'].sum().replace(0, 1) * 100).round(1)
        cat_agg = cat_agg.sort_values('Sorties_12M', ascending=False)

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Sorties 12M par catégorie**")
            fig_cat1 = px.bar(cat_agg, x='Sorties_12M', y='Cat', orientation='h',
                              color='Pct_Vol', color_continuous_scale=['#EEF2FF', '#1F3864'],
                              text='Pct_Vol', labels={'Sorties_12M': 'Qté sortie 12M', 'Cat': '',
                                                       'Pct_Vol': '% du total'})
            fig_cat1.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_cat1.update_layout(height=max(320, len(cat_agg) * 30),
                                    margin=dict(l=0, r=60, t=10, b=10), coloraxis_showscale=False)
            st.plotly_chart(fig_cat1, use_container_width=True)

        with cc2:
            st.markdown("**Taux de références actives par catégorie**")
            fig_cat2 = px.bar(cat_agg.sort_values('% Refs actives', ascending=True),
                              x='% Refs actives', y='Cat', orientation='h',
                              color='% Refs actives', color_continuous_scale=['#FFC7CE', '#C6EFCE'],
                              text='% Refs actives', labels={'Cat': ''})
            fig_cat2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_cat2.update_layout(height=max(320, len(cat_agg) * 30),
                                    margin=dict(l=0, r=60, t=10, b=10), coloraxis_showscale=False)
            st.plotly_chart(fig_cat2, use_container_width=True)

        st.divider()
        st.markdown("**Répartition Ruptures / Dormants par catégorie**")
        cat_alert = cat_agg[cat_agg['Refs_rupture'] + cat_agg['Refs_dormantes'] > 0].copy()
        if len(cat_alert) > 0:
            fig_alert = go.Figure()
            fig_alert.add_trace(go.Bar(name='Ruptures', x=cat_alert['Cat'], y=cat_alert['Refs_rupture'],
                                        marker_color='#FFC7CE'))
            fig_alert.add_trace(go.Bar(name='Dormants', x=cat_alert['Cat'], y=cat_alert['Refs_dormantes'],
                                        marker_color='#F4B942'))
            fig_alert.update_layout(barmode='stack', height=320,
                                     margin=dict(l=10, r=10, t=10, b=60),
                                     xaxis_title='Catégorie', yaxis_title='Nb références',
                                     xaxis_tickangle=-30)
            st.plotly_chart(fig_alert, use_container_width=True)
        else:
            st.info("Aucune rupture ni dormant dans la sélection courante.")

        st.divider()
        cat_export = cat_agg.copy()
        cat_export.columns = ['Catégorie', 'Nb références', 'Stock total', 'Sorties 12M',
                               'Réf. actives', 'Réf. dormantes', 'Réf. rupture',
                               '% Réf. actives', '% du volume']
        cat_export[['Stock total', 'Sorties 12M']] = cat_export[['Stock total', 'Sorties 12M']].round(2)
        st.dataframe(cat_export, use_container_width=True, height=300)
        add_export_buttons(cat_export, 'analyse_categorie', 'Analyse Catégories', date_max_a)

    # ────────────────────────────────────────────
    # ONGLET 8 : Évolution mensuelle
    # ────────────────────────────────────────────
    with tab_evo:
        st.markdown("<div class='woodmat-section-title'>Évolution mensuelle des sorties</div>", unsafe_allow_html=True)

        # Filtre catégorie spécifique pour cet onglet
        cats_evo = sorted(sm['Cat'].dropna().unique())
        sel_cats_evo = st.multiselect("Afficher par catégorie(s)", cats_evo, default=[], key="evo_cat")

        if sel_cats_evo:
            refs_evo = sm[sm['Cat'].isin(sel_cats_evo)]['Référence'].tolist()
        elif sel_cats_a:
            refs_evo = df_a['Référence'].tolist()
        else:
            refs_evo = None

        sorties_evo = df_mv_a[df_mv_a['ES'] == 'S'].copy()
        if refs_evo is not None:
            sorties_evo = sorties_evo[sorties_evo['Reference'].isin(refs_evo)]
        sorties_evo['Mois'] = sorties_evo['Date'].dt.to_period('M').dt.to_timestamp()
        sorties_evo['Annee'] = sorties_evo['Date'].dt.year

        # Évolution globale mensuelle
        evo_global = sorties_evo.groupby('Mois', as_index=False)['Qty'].sum()
        evo_global = evo_global.sort_values('Mois')

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Scatter(
            x=evo_global['Mois'], y=evo_global['Qty'],
            mode='lines+markers', name='Sorties mensuelles',
            line=dict(color='#1F3864', width=2.5),
            fill='tozeroy', fillcolor='rgba(31,56,100,0.08)'))
        # Moyenne mobile 3 mois
        evo_global['MA3'] = evo_global['Qty'].rolling(3, center=True).mean()
        fig_evo.add_trace(go.Scatter(
            x=evo_global['Mois'], y=evo_global['MA3'],
            mode='lines', name='Moyenne mobile 3M',
            line=dict(color='#B88A44', width=2, dash='dash')))
        fig_evo.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                               xaxis_title=None, yaxis_title='Quantité sortie',
                               legend=dict(orientation='h', y=1.05))
        st.plotly_chart(fig_evo, use_container_width=True)

        # Évolution par catégorie
        if sel_cats_evo:
            sorties_cat = df_mv_a[
                (df_mv_a['ES'] == 'S') &
                (df_mv_a['Reference'].isin(sm[sm['Cat'].isin(sel_cats_evo)]['Référence'].tolist()))
            ].copy()
        else:
            sorties_cat = df_mv_a[df_mv_a['ES'] == 'S'].copy()
        sorties_cat = sorties_cat.merge(sm[['Référence', 'Cat']].rename(columns={'Référence': 'Reference'}),
                                         on='Reference', how='left')
        sorties_cat['Mois'] = sorties_cat['Date'].dt.to_period('M').dt.to_timestamp()
        evo_cat = sorties_cat.groupby(['Mois', 'Cat'], as_index=False)['Qty'].sum()

        cats_present = evo_cat['Cat'].dropna().unique()
        if len(cats_present) > 0:
            st.markdown("<div class='woodmat-section-title'>Par catégorie</div>", unsafe_allow_html=True)
            fig_cat_evo = px.line(evo_cat.dropna(subset=['Cat']), x='Mois', y='Qty', color='Cat',
                                   labels={'Qty': 'Qté sortie', 'Mois': '', 'Cat': 'Catégorie'},
                                   markers=True)
            fig_cat_evo.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                                       legend=dict(orientation='h', y=-0.2))
            st.plotly_chart(fig_cat_evo, use_container_width=True)

        # Comparaison par année
        st.markdown("<div class='woodmat-section-title'>Comparaison annuelle (sorties par mois calendaire)</div>", unsafe_allow_html=True)
        sorties_ann = sorties_evo.copy()
        sorties_ann['Mois_Cal'] = sorties_ann['Date'].dt.month
        evo_ann = sorties_ann.groupby(['Annee', 'Mois_Cal'], as_index=False)['Qty'].sum()
        mois_labels = {1:'Jan',2:'Fév',3:'Mar',4:'Avr',5:'Mai',6:'Jun',
                       7:'Jul',8:'Aoû',9:'Sep',10:'Oct',11:'Nov',12:'Déc'}
        evo_ann['Mois_Lib'] = evo_ann['Mois_Cal'].map(mois_labels)
        evo_ann['Annee'] = evo_ann['Annee'].astype(str)
        fig_ann = px.line(evo_ann.sort_values('Mois_Cal'), x='Mois_Cal', y='Qty', color='Annee',
                          markers=True,
                          labels={'Qty': 'Qté sortie', 'Mois_Cal': 'Mois', 'Annee': 'Année'})
        fig_ann.update_xaxes(tickvals=list(range(1, 13)), ticktext=list(mois_labels.values()))
        fig_ann.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                               legend=dict(orientation='h', y=1.08))
        st.plotly_chart(fig_ann, use_container_width=True)

        # Export
        st.divider()
        evo_export = evo_global[['Mois', 'Qty', 'MA3']].copy()
        evo_export['Mois'] = evo_export['Mois'].dt.strftime('%Y-%m')
        evo_export.columns = ['Mois', 'Sorties', 'Moyenne mobile 3M']
        evo_export['Sorties'] = evo_export['Sorties'].round(3)
        evo_export['Moyenne mobile 3M'] = evo_export['Moyenne mobile 3M'].round(3)
        add_export_buttons(evo_export, 'evolution_mensuelle', 'Evolution Mensuelle', date_max_a)

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
    f"Fenêtre d'analyse : 12 derniers mois  |  "
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
    'Excellent': '🟢 Excellent', 'Bon': '🟢 Bon', 'Stock élevé': '🟡 Stock élevé',
    'Dormant': '🟠 Dormant', 'Rupture': '🔴 Rupture',
    'Aucun mouvement 12M': '⚪ Aucun mouvement 12M', 'Aucun mouvement': '⚪ Aucun mouvement',
}

def badge_class(series):
    return series.map(lambda v: CLASS_BADGE.get(v, v))

st.markdown(f"<h2 class='woodmat-page-title'>{page}</h2>", unsafe_allow_html=True)

display_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class', 'S_12M', 'Moy_Mois',
                 'Rotation', 'Taux_Rot', 'Couverture', 'Delai', 'Taux_Immob', 'Dern_Sortie']
rename_cols = {'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Class': 'Classification',
               'S_12M': 'Sorties 12M', 'Moy_Mois': 'Moy/Mois', 'Taux_Rot': 'Taux Rot. (%)',
               'Couverture': 'Couv. (mois)', 'Delai': 'Délai (j)', 'Taux_Immob': 'Immob. (%)',
               'Dern_Sortie': 'Dern. Sortie'}

if page == "📦 Réapprovisionnement":
    st.caption("Aide à la décision : articles nécessitant une commande selon leur couverture. Le CUMP n'est pas utilisé.")
    rep = f.copy()
    rep['Action'] = rep['Couverture'].apply(replenishment_action)
    rep['Priorité'] = rep['Couverture'].apply(lambda v: '🔴 Articles critiques' if v < 1 else ('🟠 Réapprovisionnement conseillé' if v <= 2 else '🟢 Stock suffisant'))
    kc1, kc2, kc3 = st.columns(3)
    filters = {
        '🔴 Articles critiques': rep[rep['Couverture'] < 1],
        '🟠 Réapprovisionnement conseillé': rep[(rep['Couverture'] >= 1) & (rep['Couverture'] <= 2)],
        '🟢 Stock suffisant': rep[rep['Couverture'] > 2],
    }
    for col, label in zip([kc1, kc2, kc3], filters):
        if col.button(f"{label}\n\n{len(filters[label])} article(s)", use_container_width=True):
            st.session_state['reappro_filter'] = label
    selected_priority = st.session_state.get('reappro_filter')
    if selected_priority:
        st.info(f"Filtre actif : {selected_priority}")
        rep = filters[selected_priority]
    rep_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Rotation', 'Couverture', 'Class', 'Action']
    rep_df = rep[rep_cols].rename(columns={'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Stock': 'Stock actuel', 'Class': 'Classification', 'Couverture': 'Couverture (mois)'})
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
    alert_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class', 'S_12M', 'Dern_Sortie']
    alert_df = f[f['Class'].isin(['Rupture', 'Dormant'])][alert_cols].rename(columns={
        'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité',
        'Class': 'Classification', 'S_12M': 'Sorties 12M', 'Dern_Sortie': 'Dern. Sortie'
    })
    if 'Classification' in alert_df.columns:
        alert_df['Classification'] = badge_class(alert_df['Classification']) if 'badge_class' in globals() else alert_df['Classification']
    st.dataframe(alert_df, use_container_width=True, height=520)
    st.stop()

if page == "📄 Rapports":
    st.caption("Exports disponibles pour la vue filtrée courante.")
    report_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Class', 'S_12M', 'Moy_Mois', 'Rotation']
    report_df = f[report_cols].rename(columns={'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Class': 'Classification'})
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
# Rotation globale pondérée = total sorties 12M / total stock (plus robuste que la
# moyenne simple des ratios individuels, qui explose si une référence a un stock
# quasi nul avec des sorties non nulles)
_base_rot = f[f['Rotation'] > 0]
rot_moy = _base_rot['S_12M'].sum() / _base_rot['Stock'].sum() if _base_rot['Stock'].sum() > 0 else float('nan')
n_rupture = len(f[f['Class'] == 'Rupture'])
n_dormant = len(f[f['Class'] == 'Dormant'])
n_alertes = n_rupture + n_dormant

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
        help="Nombre moyen de renouvellements du stock sur les 12 derniers mois.")
    st.markdown("<div class='woodmat-muted'>Calcul sur les 12 derniers mois</div>", unsafe_allow_html=True)
with k3:
    st.metric(
        "⚠️ Alertes",
        "Articles nécessitant une action",
        help="Les alertes regroupent les articles en rupture de stock ainsi que les articles sans mouvement depuis plus de 12 mois.")
    st.markdown(
        f"<div class='woodmat-kpi-detail'>Rupture : {n_rupture}<br>"
        f"Dormant : {n_dormant}<br><strong>Total : {n_alertes}</strong></div>",
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
        <strong>Excellent</strong> → Rotation très élevée.<br>
        <strong>Bon</strong> → Rotation satisfaisante.<br>
        <strong>Stock élevé</strong> → Stock supérieur au besoin.<br>
        <strong>Dormant</strong> → Aucun mouvement depuis plus de 12 mois.<br>
        <strong>Rupture</strong> → Stock nul.<br>
        <strong>Aucun mouvement 12M</strong> → Aucune sortie enregistrée durant les 12 derniers mois.
        </div>
        """,
        unsafe_allow_html=True)

st.divider()

# ── Tableau dynamique ───────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📋 Tableau complet", "😴 Stock dormant", "📅 Historique par année",
                                    "🪵 Stock Bois Rouge"])

with tab1:
    tdf = f[display_cols].rename(columns=rename_cols).sort_values('Taux Rot. (%)', ascending=False)
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
    st.caption(f"{len(dorm)} référence(s) dormante(s) — plus de mouvement de sortie sur 12 mois glissants "
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
