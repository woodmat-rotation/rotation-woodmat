import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import io
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# WOODMAT — ROTATION STOCK (Web App)
# ============================================================

st.set_page_config(page_title="WOODMAT — Rotation Stock", layout="wide",
                    page_icon="📦", initial_sidebar_state="expanded")

BASE_HISTORIQUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_mouvements.pkl")
SEUIL = 0.001

CAT_COLORS = {
    'BOIS BLANC': '#1F3864', 'BOIS ROUGE': '#8B0000', 'CHENE': '#4B2E0A',
    'CONTREPLAQUE': '#1E5631', 'EXOTIQUE': '#1B5E20', 'FRENE': '#33691E',
    'MDF': '#2C3E50', 'MDF DECORE': '#1A5276', 'OSB': '#784212',
    'PANNEAUX PARTICULES': '#37474F', 'PARQUET': '#6D4C41',
}
CLASS_COLORS = {
    'Excellent': '#C6EFCE', 'Bon': '#E2EFDA', 'Stock élevé': '#FFEB9C',
    'Dormant': '#F4B942', 'Rupture': '#FFC7CE',
    'Aucun mouvement 12M': '#E0E0E0', 'Aucun mouvement': '#E0E0E0',
}

# ============================================================
# AUTHENTIFICATION
# ============================================================

def check_login():
    if st.session_state.get("auth_ok"):
        return True

    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(
            "<div style='text-align:center'><h1 style='color:#1F3864'>WOODMAT</h1>"
            "<p style='color:#888'>Rotation de Stock — Accès sécurisé</p></div>",
            unsafe_allow_html=True)
        with st.form("login_form"):
            user = st.text_input("Utilisateur")
            pwd = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("Se connecter", use_container_width=True)
        if submit:
            users = st.secrets.get("credentials", {"admin": "woodmat2026"})
            if user in users and pwd == users[user]:
                st.session_state["auth_ok"] = True
                st.session_state["auth_user"] = user
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
    return False


# ============================================================
# CHARGEMENT / CALCUL (logique reprise de rotation_app_v11.py)
# ============================================================

def parse_qty(q):
    if pd.isna(q) or str(q).strip() == '':
        return 0.0
    q = str(q).replace(' ', '').replace(',', '.').replace('-', '').replace('+', '').strip()
    try:
        return float(q)
    except Exception:
        return 0.0


def charger_mouv(file_bytes):
    df = pd.read_excel(file_bytes)
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

    df['Qty'] = df['Quantite'].apply(parse_qty)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df[df['ES'].isin(['S', 'E', 'ME', 'TE'])]
    df = df.drop_duplicates(subset=['Date', 'ES', 'Document', 'Reference', 'Quantite'])
    return df


@st.cache_data(show_spinner=False)
def calculer_indicateurs(df_mv, df_st_bytes):
    df_st = pd.read_excel(df_st_bytes)
    _unite_col = next(
        (c for c in df_st.columns if str(c).strip().upper().startswith('UNIT') and 'V' in str(c).upper()),
        None)
    if _unite_col and _unite_col != 'Unité V.':
        df_st.rename(columns={_unite_col: 'Unité V.'}, inplace=True)
    elif _unite_col is None:
        df_st['Unité V.'] = 'M3'
    df_st['Qty_s'] = df_st['Quantité'].apply(parse_qty)
    df_st_c = df_st.groupby('Référence').agg(
        Stock=('Qty_s', 'sum'), Cat=('Catégorie', 'first'), Unite=('Unité V.', 'first')).reset_index()
    df_st_c = df_st_c[df_st_c['Cat'].notna()]
    df_st_c.loc[df_st_c['Cat'].isin(['BOIS BLANC', 'BOIS ROUGE']), 'Unite'] = 'M3'

    date_max = df_mv['Date'].max()
    date_12m_debut = date_max - pd.DateOffset(months=12)
    nb_mois_12m = 12.0

    sorties = df_mv[df_mv['ES'] == 'S']
    entrees = df_mv[df_mv['ES'].isin(['E', 'ME', 'TE'])]

    mv_s_all = sorties.groupby('Reference').agg(
        Total_Sorti=('Qty', 'sum'), Nb_Trans=('Qty', 'count'), Dern_Sortie=('Date', 'max')).reset_index()
    mv_e_all = entrees.groupby('Reference').agg(Dern_Entree=('Date', 'max')).reset_index()

    s_12m_df = sorties[(sorties['Date'] >= date_12m_debut) & (sorties['Date'] <= date_max)]
    e_12m_df = entrees[(entrees['Date'] >= date_12m_debut) & (entrees['Date'] <= date_max)]
    mv_s_12m = s_12m_df.groupby('Reference').agg(S_12M=('Qty', 'sum'), T_12M=('Qty', 'count')).reset_index()
    mv_e_12m = e_12m_df.groupby('Reference')['Qty'].sum().rename('A_12M').reset_index()

    sm = df_st_c.copy()
    sm = sm.merge(mv_s_all, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_e_all, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_s_12m, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    sm = sm.merge(mv_e_12m, left_on='Référence', right_on='Reference', how='left').drop(columns='Reference', errors='ignore')
    for c in ['Total_Sorti', 'Nb_Trans', 'S_12M', 'T_12M', 'A_12M']:
        sm[c] = sm[c].fillna(0)

    sm['Moy_Mois'] = (sm['S_12M'] / nb_mois_12m).round(3)
    sm['Taux_Rot'] = sm.apply(lambda r: round((r['Moy_Mois'] / r['Stock']) * 100, 1)
                               if r['Stock'] > SEUIL and r['Moy_Mois'] > 0 else 0, axis=1)
    sm['Rotation'] = sm.apply(lambda r: round(r['S_12M'] / r['Stock'], 2)
                               if r['Stock'] > SEUIL and r['S_12M'] > 0 else 0, axis=1)
    sm['Couverture'] = sm.apply(lambda r: round(r['Stock'] / r['Moy_Mois'], 1)
                                 if r['Moy_Mois'] > 0 and r['Stock'] > SEUIL else 0, axis=1)
    sm['Delai'] = sm.apply(lambda r: round(365 / r['Rotation'], 0) if r['Rotation'] > 0 else 0, axis=1)
    sm['Taux_Immob'] = sm.apply(lambda r: round(min(100.0, (r['Couverture'] / 12) * 100), 1)
                                 if r['Couverture'] > 0 else (100.0 if r['Stock'] > SEUIL else 0), axis=1)

    def cls(row):
        if row['Stock'] <= SEUIL:
            return 'Rupture'
        if row['S_12M'] == 0:
            return 'Dormant' if row['Total_Sorti'] > 0 else 'Aucun mouvement 12M'
        t = row['Taux_Rot']
        if t >= 20:
            return 'Excellent'
        elif t >= 10:
            return 'Bon'
        else:
            return 'Stock élevé'

    sm['Class'] = sm.apply(cls, axis=1)
    return sm, date_max, date_12m_debut


def evolution_mensuelle(df_mv, references=None):
    d = df_mv[df_mv['ES'] == 'S'].copy()
    if references is not None:
        d = d[d['Reference'].isin(references)]
    d['Mois'] = d['Date'].dt.to_period('M').dt.to_timestamp()
    return d.groupby('Mois')['Qty'].sum().reset_index()


# ============================================================
# INTERFACE
# ============================================================

if not check_login():
    st.stop()

with st.sidebar:
    st.markdown(f"### 📦 WOODMAT\n**Connecté :** {st.session_state.get('auth_user','')}")
    if st.button("Se déconnecter"):
        st.session_state.clear()
        st.rerun()
    st.divider()

    st.markdown("**1. Base historique mouvements**")
    base_ok = os.path.exists(BASE_HISTORIQUE)
    if base_ok:
        st.success("Base chargée sur le serveur ✅")
    f_base = st.file_uploader("Importer / remplacer la base (xlsx)", type=["xlsx", "xls"], key="base")
    if f_base is not None:
        with st.spinner("Import de la base historique..."):
            df_new = charger_mouv(f_base)
            df_new.to_pickle(BASE_HISTORIQUE)
            st.cache_data.clear()
        st.success(f"Base importée : {len(df_new):,} lignes")
        st.rerun()

    st.markdown("**2. Mouvements récents (optionnel)**")
    f_mouv = st.file_uploader("Fichier mouvements période récente", type=["xlsx", "xls"], key="mouv")

    st.markdown("**3. Stock actuel (export ERP)**")
    f_stock = st.file_uploader("Fichier stock actuel", type=["xlsx", "xls"], key="stock")

    lancer = st.button("🔄 Générer l'analyse", type="primary", use_container_width=True)

st.markdown("<h2 style='color:#1F3864;margin-bottom:0'>WOODMAT — Rotation de Stock</h2>", unsafe_allow_html=True)
st.caption("Dashboard interactif — indicateurs calculés sur une fenêtre glissante de 12 mois")

if "sm" not in st.session_state:
    st.session_state["sm"] = None

if lancer:
    if not os.path.exists(BASE_HISTORIQUE):
        st.error("Importez d'abord la base historique dans la barre latérale.")
    elif f_stock is None:
        st.error("Choisissez le fichier stock actuel.")
    else:
        with st.spinner("Calcul des indicateurs de rotation..."):
            df_base = pd.read_pickle(BASE_HISTORIQUE)
            if f_mouv is not None:
                df_recent = charger_mouv(f_mouv)
                df_mv = pd.concat([df_base, df_recent], ignore_index=True)
                df_mv = df_mv.drop_duplicates(subset=['Date', 'ES', 'Document', 'Reference', 'Quantite'])
            else:
                df_mv = df_base
            sm, date_max, date_12m_debut = calculer_indicateurs(df_mv, f_stock)
            st.session_state["sm"] = sm
            st.session_state["df_mv"] = df_mv
            st.session_state["date_max"] = date_max
            st.session_state["date_12m_debut"] = date_12m_debut

sm = st.session_state.get("sm")

if sm is None:
    st.info("⬅️ Importez vos fichiers dans la barre latérale puis cliquez sur **Générer l'analyse**.")
    st.stop()

df_mv = st.session_state["df_mv"]
date_max = st.session_state["date_max"]
date_12m_debut = st.session_state["date_12m_debut"]

st.caption(f"Stock au {date_max.strftime('%d/%m/%Y')}  |  Fenêtre 12 mois : "
           f"{date_12m_debut.strftime('%m/%Y')} → {date_max.strftime('%m/%Y')}")

# ── Filtres ──────────────────────────────────────────────
fc1, fc2, fc3 = st.columns([2, 2, 2])
with fc1:
    cats = sorted(sm['Cat'].dropna().unique())
    sel_cats = st.multiselect("Catégorie de bois", cats, default=[])
with fc2:
    classes = sorted(sm['Class'].unique())
    sel_class = st.multiselect("Classification", classes, default=[])
with fc3:
    recherche = st.text_input("🔍 Recherche référence")

f = sm.copy()
if sel_cats:
    f = f[f['Cat'].isin(sel_cats)]
if sel_class:
    f = f[f['Class'].isin(sel_class)]
if recherche:
    f = f[f['Référence'].astype(str).str.contains(recherche, case=False, na=False)]

# ── KPIs ─────────────────────────────────────────────────
vol_m3 = f[f['Unite'] == 'M3']['Stock'].sum()
rot_moy = f.loc[f['Rotation'] > 0, 'Rotation'].mean()
n_alertes = len(f[f['Class'].isin(['Rupture', 'Dormant'])])
n_rupture = len(f[f['Class'] == 'Rupture'])
n_dormant = len(f[f['Class'] == 'Dormant'])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Volume Stock (m³)", f"{vol_m3:,.1f}".replace(',', ' '))
k2.metric("Rotation moyenne (12M)", f"{rot_moy:.2f}" if pd.notna(rot_moy) else "—")
k3.metric("⚠️ Alertes (Rupture + Dormant)", n_alertes)
k4.metric("Articles analysés", len(f))

st.divider()

# ── Graphique évolution des ventes ──────────────────────
gcol, tcol = st.columns([1.3, 1])
with gcol:
    st.markdown("#### Évolution des sorties (mensuel)")
    refs_filtrees = f['Référence'].tolist() if (sel_cats or sel_class or recherche) else None
    evo = evolution_mensuelle(df_mv, refs_filtrees)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=evo['Mois'], y=evo['Qty'], mode='lines+markers',
                              line=dict(color='#1F3864', width=2), fill='tozeroy',
                              fillcolor='rgba(31,56,100,0.1)'))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title=None, yaxis_title="Qté sortie")
    st.plotly_chart(fig, use_container_width=True)

with tcol:
    st.markdown("#### Répartition par classification")
    dist = f['Class'].value_counts().reset_index()
    dist.columns = ['Classification', 'Nb']
    fig2 = px.pie(dist, names='Classification', values='Nb', hole=0.45,
                  color='Classification', color_discrete_map=CLASS_COLORS)
    fig2.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Tableau dynamique ───────────────────────────────────
tab1, tab2 = st.tabs(["📋 Tableau complet", "😴 Stock dormant"])

display_cols = ['Référence', 'Cat', 'Unite', 'Stock', 'Class', 'S_12M', 'Moy_Mois',
                 'Rotation', 'Taux_Rot', 'Couverture', 'Delai', 'Taux_Immob', 'Dern_Sortie']
rename_cols = {'Cat': 'Catégorie', 'Unite': 'Unité', 'Class': 'Classification',
               'S_12M': 'Sorties 12M', 'Moy_Mois': 'Moy/Mois', 'Taux_Rot': 'Taux Rot. (%)',
               'Couverture': 'Couv. (mois)', 'Delai': 'Délai (j)', 'Taux_Immob': 'Immob. (%)',
               'Dern_Sortie': 'Dern. Sortie'}


def style_class(val):
    color = CLASS_COLORS.get(val, '#FFFFFF')
    return f'background-color: {color}'


with tab1:
    tdf = f[display_cols].rename(columns=rename_cols).sort_values('Taux Rot. (%)', ascending=False)
    st.dataframe(
        tdf.style.applymap(style_class, subset=['Classification']),
        use_container_width=True, height=480)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        tdf.to_excel(writer, index=False, sheet_name='Rotation Stock')
    st.download_button("⬇️ Exporter Excel (vue actuelle)", buf.getvalue(),
                        file_name=f"rotation_{date_max.strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab2:
    dorm = f[f['Class'] == 'Dormant'][display_cols].rename(columns=rename_cols)
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
