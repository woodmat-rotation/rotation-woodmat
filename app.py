import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import io
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# WOODMAT — ROTATION DU STOCK (Web App)
# ============================================================

st.set_page_config(page_title="WOODMAT — Rotation du stock", layout="wide",
                    page_icon="📦", initial_sidebar_state="expanded")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_HISTORIQUE = os.path.join(APP_DIR, "base_mouvements.pkl")  # base 2020-2025, livrée avec l'app
SEUIL = 0.001

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
            "<p style='color:#888'>Rotation du stock — Accès sécurisé</p></div>",
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
        _unite_col = next((c for c in df_st.columns if str(c).strip().upper() == 'UNITÉ'), None)
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
    _qte_col = 'Quantité' if 'Quantité' in df_st.columns else ('Stock' if 'Stock' in df_st.columns else None)
    df_st['Qty_s'] = parse_qty_series(df_st[_qte_col]) if _qte_col else 0.0
    # Valeur du stock = Stock × CUMP (coût unitaire moyen pondéré) — calculée en interne
    # uniquement si la colonne CUMP est présente dans le fichier importé. CUMP lui-même
    # n'est jamais affiché comme KPI, seule la valeur monétaire l'est.
    has_cump = 'CUMP' in df_st.columns
    if has_cump:
        df_st['CUMP_s'] = parse_qty_series(df_st['CUMP'])
        df_st['Valeur_s'] = df_st['Qty_s'] * df_st['CUMP_s']
    agg_dict = {'Stock': ('Qty_s', 'sum'), 'Cat': ('Catégorie', 'first'), 'Unite': ('Unité', 'first'),
                'Designation': ('Désignation', 'first')}
    if has_cump:
        agg_dict['Valeur'] = ('Valeur_s', 'sum')
    df_st_c = df_st.groupby('Référence').agg(**agg_dict).reset_index()
    if not has_cump:
        df_st_c['Valeur'] = 0.0
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

with st.sidebar:
    st.markdown(f"### 📦 WOODMAT\n**Connecté :** {st.session_state.get('auth_user','')}")
    if st.button("Se déconnecter"):
        st.session_state.clear()
        st.rerun()
    st.divider()
    st.caption("La base historique 2020–2025 est intégrée à l'application — rien à importer.")

    st.markdown("**1. Mouvements de l'année en cours** _(optionnel)_")
    f_mouv = st.file_uploader("Export ERP mouvements (ex : 2026)", type=["xlsx", "xls"], key="mouv")

    st.markdown("**2. Stock actuel** _(obligatoire, export du jour)_")
    f_stock = st.file_uploader("Export ERP stock actuel", type=["xlsx", "xls"], key="stock")

    lancer = st.button("🔄 Générer l'analyse", type="primary", use_container_width=True)

st.markdown(
    """
    <style>
    .woodmat-kpi-card {
        background: #FFFFFF;
        border: 1px solid rgba(31, 56, 100, 0.14);
        border-radius: 10px;
        padding: 1rem 1.1rem;
        min-height: 150px;
        box-shadow: 0 1px 3px rgba(31, 56, 100, 0.06);
    }
    .woodmat-kpi-title {
        color: #1F3864;
        font-size: 0.95rem;
        font-weight: 700;
        margin-bottom: 0.45rem;
    }
    .woodmat-kpi-value {
        color: #202A35;
        font-size: 1.55rem;
        font-weight: 700;
        line-height: 1.35;
    }
    .woodmat-kpi-detail {
        color: #555;
        font-size: 0.95rem;
        line-height: 1.45;
        margin-top: 0.15rem;
    }
    .woodmat-muted {
        color: #777;
        font-size: 0.88rem;
        line-height: 1.35;
        margin-top: 0.35rem;
    }
    .woodmat-section-title {
        color: #1F3864;
        font-size: 1.08rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }
    .woodmat-legend {
        color: #666;
        font-size: 0.86rem;
        line-height: 1.45;
        margin-top: 0.35rem;
    }
    </style>
    <h2 style='color:#1F3864;margin-bottom:0'>WOODMAT — Rotation du stock</h2>
    """,
    unsafe_allow_html=True)
st.caption("Dashboard interactif — indicateurs calculés sur une fenêtre glissante de 12 mois")

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
        if f_mouv is not None:
            st.success("Mouvements fusionnés et base historique mise à jour sur le serveur ✅")

sm = st.session_state.get("sm")

if sm is None:
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
with fc1:
    cats = sorted(sm['Cat'].dropna().unique())
    sel_cats = st.multiselect("Catégorie de bois", cats, default=[])
with fc2:
    classes = sorted(sm['Class'].unique())
    sel_class = st.multiselect("Classification", classes, default=[])
with fc3:
    recherche = st.text_input("🔍 Recherche référence ou désignation")

f = sm.copy()
if sel_cats:
    f = f[f['Cat'].isin(sel_cats)]
if sel_class:
    f = f[f['Class'].isin(sel_class)]
if recherche:
    f = f[f['Référence'].astype(str).str.contains(recherche, case=False, na=False)
          | f['Designation'].astype(str).str.contains(recherche, case=False, na=False)]

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
valeur_stock = f['Valeur'].sum() if 'Valeur' in f.columns else 0.0
# Rotation globale pondérée = total sorties 12M / total stock (plus robuste que la
# moyenne simple des ratios individuels, qui explose si une référence a un stock
# quasi nul avec des sorties non nulles)
_base_rot = f[f['Rotation'] > 0]
rot_moy = _base_rot['S_12M'].sum() / _base_rot['Stock'].sum() if _base_rot['Stock'].sum() > 0 else float('nan')
n_rupture = len(f[f['Class'] == 'Rupture'])
n_dormant = len(f[f['Class'] == 'Dormant'])
n_alertes = n_rupture + n_dormant

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(
        f"<div class='woodmat-kpi-card'><div class='woodmat-kpi-title'>Volume Stock</div>"
        f"<div class='woodmat-kpi-value'>{volume_stock_html}</div></div>",
        unsafe_allow_html=True)
with k2:
    st.markdown(
        f"<div class='woodmat-kpi-card'><div class='woodmat-kpi-title'>Valeur du Stock</div>"
        f"<div class='woodmat-kpi-value'>{format_nombre_fr(valeur_stock, 0) + ' DH' if valeur_stock > 0 else '—'}</div></div>",
        unsafe_allow_html=True)
    st.markdown("<div class='woodmat-muted'>Stock × CUMP (coût unitaire moyen pondéré)</div>", unsafe_allow_html=True)
with k3:
    st.metric(
        "Rotation du stock",
        f"{rot_moy:.2f} tours/an" if pd.notna(rot_moy) else "—",
        help="Nombre moyen de renouvellements du stock sur les 12 derniers mois.")
    st.markdown("<div class='woodmat-muted'>Calcul sur les 12 derniers mois</div>", unsafe_allow_html=True)
with k4:
    st.metric(
        "⚠️ Alertes",
        "Articles nécessitant une action",
        help="Les alertes regroupent les articles en rupture de stock ainsi que les articles sans mouvement depuis plus de 12 mois.")
    st.markdown(
        f"<div class='woodmat-kpi-detail'>Rupture : {n_rupture}<br>"
        f"Dormant : {n_dormant}<br><strong>Total : {n_alertes}</strong></div>",
        unsafe_allow_html=True)
with k5:
    st.metric("Articles analysés (références)", len(f))

st.divider()

# ── Graphique évolution des ventes ──────────────────────
gcol, tcol = st.columns([1.3, 1])
with gcol:
    st.markdown("<div class='woodmat-section-title'>Historique des sorties mensuelles</div>", unsafe_allow_html=True)
    st.markdown("<div class='woodmat-muted'>Quantités sorties par mois sur les 12 derniers mois.</div>", unsafe_allow_html=True)
    refs_filtrees = f['Référence'].tolist() if (sel_cats or sel_class or recherche) else None
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

display_cols = ['Référence', 'Designation', 'Cat', 'Unite', 'Stock', 'Valeur', 'Class', 'S_12M', 'Moy_Mois',
                 'Rotation', 'Taux_Rot', 'Couverture', 'Delai', 'Taux_Immob', 'Dern_Sortie']
rename_cols = {'Designation': 'Désignation', 'Cat': 'Catégorie', 'Unite': 'Unité', 'Valeur': 'Valeur (DH)', 'Class': 'Classification',
               'S_12M': 'Sorties 12M', 'Moy_Mois': 'Moy/Mois', 'Taux_Rot': 'Taux Rot. (%)',
               'Couverture': 'Couv. (mois)', 'Delai': 'Délai (j)', 'Taux_Immob': 'Immob. (%)',
               'Dern_Sortie': 'Dern. Sortie'}


CLASS_BADGE = {
    'Excellent': '🟢 Excellent', 'Bon': '🟢 Bon', 'Stock élevé': '🟡 Stock élevé',
    'Dormant': '🟠 Dormant', 'Rupture': '🔴 Rupture',
    'Aucun mouvement 12M': '⚪ Aucun mouvement 12M', 'Aucun mouvement': '⚪ Aucun mouvement',
}


def badge_class(series):
    return series.map(lambda v: CLASS_BADGE.get(v, v))


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
