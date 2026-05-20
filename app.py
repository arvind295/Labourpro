import streamlit as st
import pandas as pd
import json
import uuid
import time
from datetime import datetime, date, timedelta
from supabase import create_client
from fpdf import FPDF
import extra_streamlit_components as stx
import io

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(
    page_title="LabourPro",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# LOAD SECRETS (Password Management)
try:
    if "general" in st.secrets:
        ADMIN_DELETE_CODE = st.secrets["general"].get("admin_delete_code", "9512")
        ADMIN_LOGIN_PASS = st.secrets["general"].get("admin_password", "admin123")
    else:
        ADMIN_DELETE_CODE = "9512"
        ADMIN_LOGIN_PASS = "admin123"
except Exception:
    ADMIN_DELETE_CODE = "9512"
    ADMIN_LOGIN_PASS = "admin123"

# --- 2. CONNECT TO SUPABASE ---
try:
    @st.cache_resource(ttl=3600)
    def init_connection():
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    supabase = init_connection()
except Exception:
    st.error("⚠️ Supabase connection failed. Check secrets.toml.")
    st.stop()

# --- 3. SESSION & COOKIE MANAGER ---
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- 4. CUSTOM STYLING ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* === BASE === */
        html, body, [class*="css"] { font-family: 'Segoe UI', system-ui, sans-serif; }
        .stApp { background-color: #F0F2F6 !important; }

        /* === DARK SIDEBAR === */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1A2332 0%, #243447 100%) !important;
            border-right: none !important;
        }
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] div { color: #CBD5E0 !important; }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 { color: #FFFFFF !important; }

        /* Sidebar nav buttons */
        section[data-testid="stSidebar"] .stButton > button {
            background-color: rgba(255,255,255,0.06) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            color: #CBD5E0 !important;
            border-radius: 8px !important;
            text-align: left !important;
            padding: 0.55rem 1rem !important;
            margin-bottom: 3px !important;
            font-size: 0.92rem !important;
            width: 100% !important;
            transition: all 0.15s ease !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background-color: rgba(243,156,18,0.2) !important;
            border-color: rgba(243,156,18,0.5) !important;
            color: #FFFFFF !important;
        }
        section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1) !important; }
        section[data-testid="stSidebar"] .stAlert { background-color: rgba(255,255,255,0.08) !important; border: none !important; }
        section[data-testid="stSidebar"] input {
            background-color: rgba(255,255,255,0.1) !important;
            color: #1A202C !important; /* CHANGED HERE: Dark text so it is visible in the search bar */
            border: 1px solid rgba(255,255,255,0.2) !important;
        }

        /* === INPUTS & SELECTS === */
        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #1A202C !important;
            border: 1px solid #D1D5DB !important;
            border-radius: 6px !important;
        }
        input:focus, textarea:focus { border-color: #F39C12 !important; box-shadow: 0 0 0 2px rgba(243,156,18,0.15) !important; }

        /* === PRIMARY BUTTONS === */
        button[kind="primary"] {
            background: linear-gradient(135deg, #F39C12, #E67E22) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            letter-spacing: 0.02em !important;
        }
        button[kind="primary"]:hover { filter: brightness(1.08) !important; }
        button[disabled] { background: #D1D5DB !important; color: #9CA3AF !important; cursor: not-allowed !important; }

        /* === METRICS === */
        div[data-testid="stMetricValue"] { font-size: 1.5rem !important; color: #F39C12 !important; font-weight: 700 !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.85rem !important; color: #6B7280 !important; font-weight: 500 !important; }
        div[data-testid="metric-container"] {
            background: #FFFFFF !important;
            border-radius: 12px !important;
            padding: 1.1rem 1.2rem !important;
            border: 1px solid #E5E7EB !important;
            box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important;
        }

        /* === DATAFRAMES === */
        div[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden !important; border: 1px solid #E5E7EB !important; box-shadow: 0 1px 6px rgba(0,0,0,0.05) !important; }
        th { background-color: #F39C12 !important; color: #FFFFFF !important; font-weight: 600 !important; border-bottom: 2px solid #E67E22 !important; }
        td { border-bottom: 1px solid #F3F4F6 !important; color: #1A202C !important; }

        /* === TAGS / PILLS === */
        span[data-baseweb="tag"] { background-color: #F39C12 !important; color: #FFFFFF !important; border-radius: 20px !important; font-weight: 500 !important; }

        /* === PAGE TITLE HELPER CLASSES === */
        .lp-page-header {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            margin-bottom: 1.2rem;
            border-left: 4px solid #F39C12;
            box-shadow: 0 1px 6px rgba(0,0,0,0.05);
        }
        .lp-page-title { font-size: 1.5rem; font-weight: 700; color: #1A2332; margin: 0; }
        .lp-page-subtitle { font-size: 0.9rem; color: #6B7280; margin-top: 0.2rem; }

        /* === COST PREVIEW BOX === */
        .cost-preview {
            background: linear-gradient(135deg, #FEF9E7, #FDEBD0);
            border: 2px solid #F39C12;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin: 0.8rem 0;
        }
        .cost-preview-title { font-size: 0.8rem; font-weight: 600; color: #E67E22; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
        .cost-preview-amount { font-size: 2rem; font-weight: 800; color: #1A2332; }
        .cost-preview-breakdown { font-size: 0.82rem; color: #6B7280; margin-top: 0.3rem; }

        /* === STEP CARDS === */
        .step-card {
            background: #FFFFFF;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            border: 1px solid #E5E7EB;
            margin-bottom: 0.8rem;
        }
        .step-label { font-size: 0.72rem; font-weight: 700; color: #F39C12; text-transform: uppercase; letter-spacing: 0.08em; }

        /* === EMPTY STATE === */
        .empty-state {
            text-align: center;
            padding: 2.5rem 1rem;
            color: #9CA3AF;
        }
        .empty-state-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
        .empty-state-title { font-size: 1.1rem; font-weight: 600; color: #6B7280; margin-bottom: 0.3rem; }
        .empty-state-text { font-size: 0.9rem; }

        /* === HELP TEXT === */
        .help-text {
            font-size: 0.82rem;
            color: #9CA3AF;
            font-style: italic;
            margin-top: 0.2rem;
        }

        /* === STATUS BADGE === */
        .badge-active { background: #D1FAE5; color: #065F46; padding: 2px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
        .badge-inactive { background: #FEE2E2; color: #991B1B; padding: 2px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }

        /* === DIVIDER === */
        hr { border-color: #E5E7EB !important; }

        /* === EXPANDERS === */
        div[data-testid="stExpander"] { background: #FFFFFF !important; border-radius: 10px !important; border: 1px solid #E5E7EB !important; }

        /* === TABS === */
        button[data-baseweb="tab"] { font-weight: 500 !important; }
        button[data-baseweb="tab"][aria-selected="true"] { color: #F39C12 !important; border-bottom-color: #F39C12 !important; }

        /* === SUCCESS / ERROR / INFO ALERTS === */
        div[data-testid="stAlert"] { border-radius: 8px !important; }

        /* === MOBILE === */
        @media only screen and (max-width: 600px) {
            h1 { font-size: 1.5rem !important; }
            .lp-page-title { font-size: 1.2rem; }
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_styling()

# --- 5. HELPER FUNCTIONS & PDF ENGINES ---
def fetch_data(table):
    all_data = []
    page_size = 1000
    current_start = 0
    while True:
        try:
            response = supabase.table(table).select("*").range(current_start, current_start + page_size - 1).execute()
            data_chunk = response.data
            all_data.extend(data_chunk)
            if len(data_chunk) < page_size:
                break
            current_start += page_size
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            break
    return pd.DataFrame(all_data)

def get_billing_start_date(entry_date):
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

def upload_evidence(file_obj):
    """Uploads photos/receipts to Supabase storage and returns the URL."""
    try:
        ext = file_obj.name.split('.')[-1]
        unique_name = f"{uuid.uuid4()}.{ext}"
        file_bytes = file_obj.getvalue()
        supabase.storage.from_("evidence").upload(
            file=file_bytes,
            path=unique_name,
            file_options={"content-type": f"image/{ext}"}
        )
        return supabase.storage.from_("evidence").get_public_url(unique_name)
    except Exception as e:
        st.error(f"Image upload failed: {e}")
        return ""

def empty_state(icon, title, text=""):
    st.markdown(f"""
        <div class="empty-state">
            <div class="empty-state-icon">{icon}</div>
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-text">{text}</div>
        </div>
    """, unsafe_allow_html=True)

# --- PDF ENGINE FOR LABOUR BILLS ---
class PDFBill(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Labour Payment Bill', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_bytes(header_name, week_label, billing_data):
    pdf = PDFBill()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Bill For: {header_name}", 0, 1, 'L')
    pdf.cell(0, 10, f"Week: {week_label}", 0, 1, 'L')
    pdf.ln(5)
    for item in billing_data:
        pdf.set_fill_color(220, 220, 220)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"{item['name']}", 0, 1, 'L', fill=True)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Date", 1)
        pdf.cell(20, 8, "Mason", 1)
        pdf.cell(20, 8, "Helper", 1)
        pdf.cell(20, 8, "Ladies", 1)
        pdf.ln()
        pdf.set_font("Arial", '', 10)
        for row in item['rows']:
            pdf.cell(30, 8, str(row['Date']), 1)
            pdf.cell(20, 8, str(row['Mason']), 1)
            pdf.cell(20, 8, str(row['Helper']), 1)
            pdf.cell(20, 8, str(row['Ladies']), 1)
            pdf.ln()
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Totals", 1)
        pdf.cell(20, 8, str(item['totals']['m']), 1)
        pdf.cell(20, 8, str(item['totals']['h']), 1)
        pdf.cell(20, 8, str(item['totals']['l']), 1)
        pdf.ln()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(90, 10, f"Total: Rs. {item['totals']['amt']:,.2f}", 1, 0, 'R')
        pdf.ln(15)
    return pdf.output(dest='S').encode('latin-1')

# --- PDF ENGINE FOR MATERIALS ---
class MaterialPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Material Log Report', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_material_pdf_bytes(site_name, period_label, df_mat):
    pdf = MaterialPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Site: {site_name}", 0, 1, 'L')
    pdf.cell(0, 10, f"Period: {period_label}", 0, 1, 'L')
    pdf.ln(5)
    total_grand = 0
    categories = ["Civil Material", "Steel Material", "Soil Material", "RMC"]
    for cat in categories:
        df_cat = df_mat[df_mat["category"] == cat]
        if not df_cat.empty:
            pdf.set_fill_color(220, 220, 220)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"{cat}", 0, 1, 'L', fill=True)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(25, 8, "Date", 1)
            pdf.cell(50, 8, "Vendor", 1)
            pdf.cell(80, 8, "Material", 1)
            pdf.cell(15, 8, "Qty", 1)
            pdf.cell(20, 8, "Amount", 1)
            pdf.ln()
            pdf.set_font("Arial", '', 9)
            cat_total = 0
            for _, row in df_cat.iterrows():
                pdf.cell(25, 8, str(row.get('date', '')), 1)
                vendor = str(row.get('vendor', ''))[:22]
                material = str(row.get('material_name', ''))[:40]
                pdf.cell(50, 8, vendor, 1)
                pdf.cell(80, 8, material, 1)
                pdf.cell(15, 8, str(row.get('quantity', '')), 1)
                amt = float(row.get('amount', 0))
                cat_total += amt
                pdf.cell(20, 8, f"{amt:,.0f}", 1)
                pdf.ln()
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(170, 8, f"Total {cat}", 1, 0, 'R')
            pdf.cell(20, 8, f"{cat_total:,.0f}", 1, 1, 'L')
            pdf.ln(8)
            total_grand += cat_total
    if total_grand > 0:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Grand Total: Rs. {total_grand:,.2f}", 0, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# --- PDF ENGINE FOR CLIENT INVOICES ---
class ClientInvoicePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 22)
        self.set_text_color(44, 62, 80)
        self.cell(0, 15, 'CLIENT EXPENSE RECOVERY INVOICE', 0, 1, 'C')
        self.ln(3)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()} - Confidential', 0, 0, 'C')

def _pdf_section_header(pdf, number, title, r, g, b):
    pdf.set_font("Arial", 'B', 13)
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, _safe(f"  {number}. {title}"), 0, 1, 'L', fill=True)
    pdf.set_text_color(0, 0, 0)

def _pdf_col_header(pdf, widths, labels):
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(236, 240, 241)
    for w, lbl in zip(widths, labels):
        pdf.cell(w, 9, lbl, 1, 0, 'C', fill=True)
    pdf.ln()

def _safe(text):
    """Sanitize any string for FPDF latin-1 output.
    Replaces known problem chars first, then force-encodes everything else."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        '\u20b9': 'Rs.', '\u2014': '-',  '\u2013': '-',
        '\u2018': "'",   '\u2019': "'",  '\u201c': '"', '\u201d': '"',
        '\u2022': '*',   '\u00a0': ' ',  '\u2026': '...',
        '\u00e2': 'a',   '\u20ac': 'EUR',
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Final safety net: drop anything still outside latin-1
    return text.encode('latin-1', errors='replace').decode('latin-1')

def _pdf_subtotal_row(pdf, label, amount):
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(236, 240, 241)
    pdf.cell(140, 9, _safe(f"  {label}"), 1, 0, 'R', fill=True)
    pdf.cell(50, 9, f"Rs. {amount:,.2f}", 1, 1, 'R', fill=True)

def generate_client_invoice_bytes(site_name, date_range_label, labor_details,
                                   df_client_mats, df_our_mats, grand_total,
                                   weekly_labour_rows=None):
    """
    Generates a client-facing PDF invoice.
    - labor_details       : civil/pre-work labour summary dict
    - df_client_mats      : materials procured in our name (to recover from client)
    - df_our_mats         : our-scope materials (Included in Quote, no charge)
    - grand_total         : labour_total + client_mat_total
    - weekly_labour_rows  : list of dicts with weekly breakdown
                            [{'week': '01-04-2026 to 07-04-2026',
                              'mason': 8, 'helper': 4, 'ladies': 0,
                              'rate_m': 600, 'rate_h': 400, 'rate_l': 350,
                              'amount': 6400.0}, ...]
    """
    pdf = ClientInvoicePDF()
    pdf.add_page()

    # ── META ─────────────────────────────────────────────────────────────────
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(100, 7, _safe(f"Project Site: {site_name}"), 0, 0, 'L')
    pdf.set_font("Arial", '', 10)
    pdf.cell(90, 7, f"Date Generated: {date.today().strftime('%d %b %Y')}", 0, 1, 'R')
    pdf.cell(100, 7, _safe(f"Billing Period: {date_range_label}"), 0, 1, 'L')
    pdf.ln(6)

    # ── SECTION 1: LABOUR — WEEKLY BREAKDOWN ────────────────────────────────
    _pdf_section_header(pdf, 1, "CIVIL & PRE-WORK LABOUR", 44, 62, 80)
    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6,
        "  Labour for civil/wall changes before interior works - not covered in your quote.",
        0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    if weekly_labour_rows:
        # Only show weeks that have actual labour entries (amount > 0)
        active_weeks = [w for w in weekly_labour_rows if w.get('amount', 0.0) > 0]
        if active_weeks:
            _pdf_col_header(pdf, [140, 50], ["Week Period", "Amount (Rs)"])
            pdf.set_font("Arial", '', 9)
            for wrow in active_weeks:
                amt = wrow.get('amount', 0.0)
                pdf.cell(140, 9, _safe(f" {wrow['week']}"), 1, 0, 'L')
                pdf.cell(50, 9, f"{amt:,.2f}", 1, 1, 'R')
        else:
            pdf.cell(190, 9, "  No civil labour charged for this period.", 1, 1, 'C')
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.cell(190, 9, "  No civil labour charged for this period.", 1, 1, 'C')

    _pdf_subtotal_row(pdf, "Sub-Total - Labour:", labor_details['total'])
    pdf.ln(8)

    # ── SECTION 2: MATERIALS ─────────────────────────────────────────────────
    _pdf_section_header(pdf, 2, "MATERIALS", 41, 128, 185)
    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6,
        "  Materials purchased for the project.",
        0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    _pdf_col_header(pdf, [28, 112, 50], ["Date", "Description", "Amount (Rs)"])
    pdf.set_font("Arial", '', 10)
    client_mat_total = 0
    if not df_client_mats.empty:
        for _, r in df_client_mats.iterrows():
            desc = _safe(str(r.get("Description", "")).strip())
            if not desc:
                continue
            m_date = _safe(str(r.get("Date", "")).strip()[:12])
            try:
                amt = float(r.get("Amount (Rs)", 0))
            except:
                amt = 0.0
            client_mat_total += amt
            pdf.cell(28, 9, m_date, 1, 0, 'C')
            pdf.cell(112, 9, _safe(f" {desc[:60]}"), 1, 0, 'L')
            pdf.cell(50, 9, f"{amt:,.2f}", 1, 1, 'R')
    else:
        pdf.cell(190, 9, "  No materials for this period.", 1, 1, 'C')
    _pdf_subtotal_row(pdf, "Sub-Total - Materials:", client_mat_total)
    pdf.ln(8)

    # ── GRAND TOTAL ──────────────────────────────────────────────────────────
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(44, 62, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 14, "  TOTAL AMOUNT:", 1, 0, 'R', fill=True)
    pdf.cell(50, 14, f"Rs. {grand_total:,.2f}", 1, 1, 'R', fill=True)
    pdf.set_text_color(0, 0, 0)

    return pdf.output(dest='S').encode('latin-1')

# --- WEEKLY BILL RENDERER ---
def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty:
        empty_state("📊", "No entries yet", "Start by logging daily attendance in the Daily Entry tab.")
        return

    is_admin = (st.session_state["role"] == "admin")
    if not is_admin:
        assigned_raw = st.session_state.get("assigned_site", "")
        if "All" not in assigned_raw and "None/All" not in assigned_raw:
            user_sites = [s.strip() for s in assigned_raw.split(",")]
            df_entries = df_entries[df_entries["site"].isin(user_sites)]
            if df_entries.empty:
                empty_state("🏗️", "No data for your sites", "Your assigned sites have no entries in this period.")
                return

    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors='coerce')
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"], errors='coerce').dt.date
    df_entries = df_entries.dropna(subset=["date_dt"])
    if df_entries.empty:
        empty_state("📅", "No valid dates found", "Check that your entries have proper dates.")
        return

    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)

    unique_weeks = df_entries[["start_date", "week_label"]].drop_duplicates().sort_values("start_date", ascending=False)
    weeks = unique_weeks["week_label"].tolist()

    st.markdown("#### 📅 Select a Week to View")
    sel_week = st.selectbox("Billing Week", weeks, help="Each week runs Saturday to Friday. Select any week to see the full bill.") if weeks else None

    if not sel_week:
        return

    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    week_start_obj = df_week.iloc[0]["start_date"]
    full_week_dates = [week_start_obj + timedelta(days=i) for i in range(7)]

    if is_admin:
        csv_data = df_week.to_csv(index=False).encode('utf-8')
        st.download_button(f"📊 Download Week Data (CSV)", csv_data, f"Data_{sel_week}.csv", "text/csv",
                           help="Download all raw entries for this week as a CSV/Excel-compatible file.")
        st.divider()

    tab_site, tab_con = st.tabs(["🏢 View by Site", "👷 View by Contractor"])

    with tab_site:
        all_sites = sorted(df_week["site"].unique())
        if not all_sites:
            empty_state("🏗️", "No sites found for this week")
            st.stop()
        sel_site = st.pills("Select a Site", all_sites, key="sb_site", default=all_sites[0] if all_sites else None)
        if sel_site:
            st.divider()
            st.markdown(f"### 📍 {sel_site}")
            df_view = df_week[df_week["site"] == sel_site]
            pdf_data = []

            for con_name in df_view["contractor"].unique():
                df_sub = df_view[df_view["contractor"] == con_name]
                entry_map = {d.date(): r for d, r in zip(df_sub["date_dt"], df_sub.to_dict('records'))}
                rates = df_contractors[df_contractors["name"] == con_name].sort_values("effective_date", ascending=False)
                rm, rh, rl = 0, 0, 0
                if not rates.empty:
                    valid_rates = rates[rates["effective_date"] <= week_start_obj]
                    curr = valid_rates.iloc[0] if not valid_rates.empty else rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]

                rows = []
                tm, th, tl, tamt = 0, 0, 0, 0
                for day_date in full_week_dates:
                    if day_date in entry_map:
                        r = entry_map[day_date]
                        m, h, l = r["count_mason"], r["count_helper"], r["count_ladies"]
                        current_daily_cost = (m * rm) + (h * rh) + (l * rl)
                        dm, dh, dl = ("Nil", "Nil", "Nil") if (m == 0 and h == 0 and l == 0) else (str(m), str(h), str(l))
                    else:
                        m, h, l, current_daily_cost = 0, 0, 0, 0
                        dm, dh, dl = "0", "0", "0"
                    rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
                    tm += m; th += h; tl += l; tamt += current_daily_cost

                pdf_data.append({"name": con_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

                st.markdown(f"#### 👷 {con_name}")
                if is_admin:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 Amount Payable", f"₹{tamt:,.0f}")
                    k2.metric("🧱 Mason Shifts", f"{tm}")
                    k3.metric("🛠️ Helper Shifts", f"{th}")
                    k4.metric("👩 Ladies Shifts", f"{tl}")
                else:
                    k2, k3, k4 = st.columns(3)
                    k2.metric("🧱 Mason Shifts", f"{tm}")
                    k3.metric("🛠️ Helper Shifts", f"{th}")
                    k4.metric("👩 Ladies Shifts", f"{tl}")

                with st.expander(f"📄 View Day-by-Day: {con_name}"):
                    st.caption("Showing all 7 days of the week. Days with no entry show 0. Nil means a holiday/no-work entry was submitted.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if pdf_data:
                try:
                    pdf_bytes = generate_pdf_bytes(sel_site, sel_week, pdf_data)
                    st.download_button(f"⬇️ Download PDF Bill — {sel_site}", pdf_bytes, f"Bill_{sel_site}.pdf", "application/pdf",
                                       help="Download a formatted PDF bill for all contractors at this site for the selected week.")
                except:
                    pass

    with tab_con:
        all_cons = sorted(df_week["contractor"].unique())
        if not all_cons:
            empty_state("👷", "No contractors found for this week")
            st.stop()
        sel_con = st.pills("Select a Contractor", all_cons, key="sb_con", default=all_cons[0] if all_cons else None)
        if sel_con:
            st.divider()
            st.markdown(f"### 👷 {sel_con}")
            df_view = df_week[df_week["contractor"] == sel_con]
            pdf_data = []

            for site_name in df_view["site"].unique():
                df_sub = df_view[df_view["site"] == site_name]
                entry_map = {d.date(): r for d, r in zip(df_sub["date_dt"], df_sub.to_dict('records'))}
                rates = df_contractors[df_contractors["name"] == sel_con].sort_values("effective_date", ascending=False)
                rm, rh, rl = 0, 0, 0
                if not rates.empty:
                    valid_rates = rates[rates["effective_date"] <= week_start_obj]
                    curr = valid_rates.iloc[0] if not valid_rates.empty else rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]

                rows = []
                tm, th, tl, tamt = 0, 0, 0, 0
                for day_date in full_week_dates:
                    if day_date in entry_map:
                        r = entry_map[day_date]
                        m, h, l = r["count_mason"], r["count_helper"], r["count_ladies"]
                        current_daily_cost = (m * rm) + (h * rh) + (l * rl)
                        dm, dh, dl = ("Nil", "Nil", "Nil") if (m == 0 and h == 0 and l == 0) else (str(m), str(h), str(l))
                    else:
                        m, h, l, current_daily_cost = 0, 0, 0, 0
                        dm, dh, dl = "0", "0", "0"
                    rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
                    tm += m; th += h; tl += l; tamt += current_daily_cost

                pdf_data.append({"name": site_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

                st.markdown(f"#### 📍 {site_name}")
                if is_admin:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 Amount Payable", f"₹{tamt:,.0f}")
                    k2.metric("🧱 Mason Shifts", f"{tm}")
                    k3.metric("🛠️ Helper Shifts", f"{th}")
                    k4.metric("👩 Ladies Shifts", f"{tl}")
                else:
                    k2, k3, k4 = st.columns(3)
                    k2.metric("🧱 Mason Shifts", f"{tm}")
                    k3.metric("🛠️ Helper Shifts", f"{th}")
                    k4.metric("👩 Ladies Shifts", f"{tl}")

                with st.expander(f"📄 View Day-by-Day: {site_name}"):
                    st.caption("Showing all 7 days of the week.")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if pdf_data:
                try:
                    pdf_bytes = generate_pdf_bytes(sel_con, sel_week, pdf_data)
                    st.download_button(f"⬇️ Download PDF Bill — {sel_con}", pdf_bytes, f"Bill_{sel_con}.pdf", "application/pdf",
                                       help="Download a formatted PDF bill for this contractor across all sites for the selected week.")
                except:
                    pass

# --- 6. AUTO-LOGIN CHECK ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

if "search_query" not in st.session_state:
    st.session_state["search_query"] = ""
if "search_active" not in st.session_state:
    st.session_state["search_active"] = False

time.sleep(0.1)
stored_token = cookie_manager.get("auth_token")

if not st.session_state["logged_in"] and stored_token:
    try:
        res = supabase.table("users").select("*").eq("session_token", stored_token).execute()
        if res.data:
            user = res.data[0]
            st.session_state.update({
                "logged_in": True,
                "phone": user["phone"],
                "role": user["role"],
                "user_name": user["name"],
                "assigned_site": user.get("assigned_site", "All")
            })
            st.toast(f"👋 Welcome back, {user['name']}!")
        else:
            try:
                cookie_manager.delete("auth_token")
            except KeyError:
                pass
    except Exception:
        pass

# --- 7. LOGIN PROCESS ---
def login_process():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
            <div style='text-align:center; padding: 2.5rem 0 1.5rem 0;'>
                <div style='font-size:3.5rem;'>🏗️</div>
                <h1 style='font-size:2.2rem; font-weight:800; color:#1A2332; margin:0.3rem 0 0.2rem 0;'>LabourPro</h1>
                <p style='color:#6B7280; font-size:1rem; margin:0;'>Construction Site Management Portal</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style='background:#FFFFFF; border-radius:16px; padding:2rem;
                        box-shadow:0 4px 24px rgba(0,0,0,0.08); border:1px solid #E5E7EB; margin-bottom:1rem;'>
                <h3 style='color:#1A2332; margin-top:0; font-size:1.1rem;'>👷 Team Login</h3>
            </div>
        """, unsafe_allow_html=True)

        with st.container():
            with st.form("u_log"):
                ph = st.text_input("📱 Mobile Number", max_chars=10, placeholder="Enter your 10-digit mobile number")
                pin = st.text_input("🔒 4-Digit PIN", type="password", max_chars=4, placeholder="Enter your 4-digit PIN")
                st.markdown("<p style='font-size:0.8rem;color:#9CA3AF;'>Your PIN was set by your admin. Default is 1234 unless changed.</p>", unsafe_allow_html=True)
                if st.form_submit_button("Login  →", type="primary", use_container_width=True):
                    if not ph or not pin:
                        st.warning("⚠️ Please enter both your mobile number and PIN.")
                    elif len(ph) != 10 or not ph.isdigit():
                        st.warning("⚠️ Mobile number must be exactly 10 digits.")
                    elif len(pin) != 4 or not pin.isdigit():
                        st.warning("⚠️ PIN must be exactly 4 digits.")
                    else:
                        try:
                            response = supabase.table("users").select("*").eq("phone", ph).execute()
                            if not response.data:
                                st.error("❌ No account found with this mobile number. Contact your admin.")
                            else:
                                user = response.data[0]
                                user_mpin = user.get("mpin", "1234")
                                if user_mpin is None: user_mpin = "1234"
                                if str(pin) != str(user_mpin):
                                    st.error("❌ Incorrect PIN. Try again or contact your admin to reset.")
                                elif user.get("status") == "Resigned":
                                    st.error("⛔ This account has been deactivated. Contact your admin.")
                                elif user.get("role") == "admin":
                                    st.error("⚠️ Admin accounts must use the 'Admin Login' section below.")
                                else:
                                    new_token = str(uuid.uuid4())
                                    supabase.table("users").update({"session_token": new_token}).eq("phone", ph).execute()
                                    cookie_manager.set("auth_token", new_token, expires_at=datetime.now() + timedelta(days=30))
                                    st.session_state.update({
                                        "logged_in": True,
                                        "phone": user["phone"],
                                        "role": user.get("role", "user"),
                                        "user_name": user["name"],
                                        "assigned_site": user.get("assigned_site", "All")
                                    })
                                    st.success(f"✅ Welcome, {user['name']}!")
                                    time.sleep(1)
                                    st.rerun()
                        except Exception:
                            st.warning("⚠️ Connection error. Please try again in a moment.")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔐 Admin Login"):
            with st.form("a_log"):
                st.caption("For administrators only. Use your registered admin mobile number and password.")
                ph_a = st.text_input("Admin Mobile Number", placeholder="10-digit mobile")
                pw_a = st.text_input("Admin Password", type="password", placeholder="Your admin password")
                if st.form_submit_button("Admin Login", use_container_width=True):
                    if pw_a == ADMIN_LOGIN_PASS:
                        try:
                            response = supabase.table("users").select("*").eq("phone", ph_a).execute()
                            if response.data and response.data[0].get("role") == "admin":
                                user = response.data[0]
                                new_token = str(uuid.uuid4())
                                supabase.table("users").update({"session_token": new_token}).eq("phone", ph_a).execute()
                                cookie_manager.set("auth_token", new_token, expires_at=datetime.now() + timedelta(days=30))
                                st.session_state.update({
                                    "logged_in": True,
                                    "phone": user["phone"],
                                    "role": "admin",
                                    "user_name": user["name"]
                                })
                                st.success("✅ Admin Logged In")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ No admin account found for this mobile number.")
                        except Exception:
                            st.warning("⚠️ Connection error. Please try again.")
                    else:
                        st.error("❌ Incorrect admin password.")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 8. SIDEBAR: USER PANEL + NAVIGATION ---
is_designer = (st.session_state["role"] == "designer")
is_admin    = (st.session_state["role"] == "admin")

# Build tab list per role
if is_admin:
    tabs = ["📝 Daily Entry", "📊 Weekly Bill", "🧱 Materials", "📓 My Diary",
            "📈 Dashboard", "🧾 Client Invoice", "🔍 Site Logs", "📍 Sites",
            "👷 Contractors", "👥 Users", "📂 Archive & Recovery", "🔎 Search Results"]
elif is_designer:
    tabs = ["🎨 Client Materials", "📓 My Diary"]
else:
    tabs = ["📝 Daily Entry", "📊 Weekly Bill", "🧱 Materials", "📓 My Diary"]

if "current_tab" not in st.session_state or st.session_state["current_tab"] not in tabs:
    st.session_state["current_tab"] = tabs[0]

with st.sidebar:
    st.markdown("""
        <div style='text-align:center; padding: 1rem 0 0.5rem 0;'>
            <div style='font-size:2rem;'>🏗️</div>
            <div style='font-size:1.2rem; font-weight:700; color:#FFFFFF; letter-spacing:0.05em;'>LabourPro</div>
        </div>
    """, unsafe_allow_html=True)

    role_badge = "🛡️ Admin" if is_admin else ("🎨 Interior Designer" if is_designer else "👷 Field User")
    user_name = st.session_state.get("user_name", "User")
    st.markdown(f"""
        <div style='background:rgba(243,156,18,0.15); border:1px solid rgba(243,156,18,0.3);
                    border-radius:10px; padding:0.75rem 1rem; margin:0.5rem 0 1rem 0;'>
            <div style='font-size:0.75rem; color:#F39C12; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;'>{role_badge}</div>
            <div style='font-size:1rem; font-weight:700; color:#FFFFFF; margin-top:0.1rem;'>{user_name}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- GLOBAL SEARCH (admin only) ---
    if is_admin:
        st.markdown("<div style='font-size:0.72rem; color:#6B7280; font-weight:600; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.4rem;'>QUICK SEARCH</div>", unsafe_allow_html=True)
        search_input = st.text_input(
            "search_box",
            value=st.session_state["search_query"],
            placeholder="🔎  Site, contractor, or date...",
            label_visibility="collapsed",
            key="sidebar_search_input"
        )
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            if st.button("Search", use_container_width=True, key="do_search"):
                if search_input.strip():
                    st.session_state["search_query"] = search_input.strip()
                    st.session_state["search_active"] = True
                    st.session_state["current_tab"] = "🔎 Search Results"
                    st.rerun()
        with col_s2:
            if st.button("✕", use_container_width=True, key="clear_search", help="Clear search"):
                st.session_state["search_query"] = ""
                st.session_state["search_active"] = False
                if st.session_state["current_tab"] == "🔎 Search Results":
                    st.session_state["current_tab"] = "📝 Daily Entry"
                st.rerun()
        st.markdown("<div style='margin-bottom:0.8rem;'></div>", unsafe_allow_html=True)

    st.markdown("<div style='font-size:0.72rem; color:#6B7280; font-weight:600; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.5rem;'>NAVIGATION</div>", unsafe_allow_html=True)
    for tab in tabs:
        # Hide the Search Results tab from the nav list — it's reached via the search bar only
        if tab == "🔎 Search Results":
            continue
        if st.button(tab, key=f"nav_{tab}", use_container_width=True):
            st.session_state["current_tab"] = tab
            st.rerun()

    st.divider()

    # PIN change for regular users and designers
    if st.session_state["role"] in ("user", "designer"):
        with st.expander("🔐 Change My PIN"):
            st.caption("Choose a new 4-digit numeric PIN for your next login.")
            new_pin = st.text_input("New 4-Digit PIN", max_chars=4, type="password", key="new_u_pin", placeholder="e.g. 5678")
            if st.button("Update PIN"):
                if len(new_pin) == 4 and new_pin.isdigit():
                    try:
                        supabase.table("users").update({"mpin": new_pin}).eq("phone", st.session_state["phone"]).execute()
                        st.success("✅ PIN Updated! Use the new PIN on your next login.")
                    except:
                        st.error("⚠️ Error updating PIN. Please try again.")
                else:
                    st.error("⚠️ PIN must be exactly 4 numeric digits.")
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🚪 Logout", use_container_width=True):
        if st.session_state.get("phone"):
            try:
                supabase.table("users").update({"session_token": None}).eq("phone", st.session_state["phone"]).execute()
            except:
                pass
        try:
            cookie_manager.delete("auth_token")
        except KeyError:
            pass
        st.session_state.clear()
        time.sleep(1)
        st.rerun()

current_tab = st.session_state["current_tab"]

# --- 9. PAGE HEADER HELPER ---
def page_header(title, subtitle=""):
    sub_html = f"<div class='lp-page-subtitle'>{subtitle}</div>" if subtitle else ""
    st.markdown(f"""
        <div class='lp-page-header'>
            <div class='lp-page-title'>{title}</div>
            {sub_html}
        </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# TAB 1: DAILY ENTRY
# ==============================================================================
if current_tab == "📝 Daily Entry":
    page_header("📝 Daily Entry", "Log today's workforce attendance — select a site and contractor to begin")
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")

    if df_sites.empty:
        empty_state("🏗️", "No sites available", "Ask your admin to add construction sites before you can log entries.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        if st.session_state["role"] != "admin":
            u = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
            if u.data and u.data.get("assigned_site"):
                raw_assignments = u.data.get("assigned_site", "")
                assigned_list = [s.strip() for s in raw_assignments.split(",")]
                if "None/All" not in assigned_list and "All" not in assigned_list:
                    av_sites = [s for s in av_sites if s in assigned_list]
            else:
                st.error("⚠️ You have not been assigned to any site. Contact your admin.")
                st.stop()

        if not av_sites:
            empty_state("🔗", "No active sites assigned", "Your assigned sites may have been removed. Contact your admin.")
            st.stop()

        # Step 1: Select Site, Date, Contractor
        st.markdown("""<div class='step-card'><div class='step-label'>Step 1 — Choose Entry Details</div></div>""", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("📅 Date", date.today(), format="DD-MM-YYYY", help="Select the date for this work entry.")
        st_sel = c2.selectbox("🏗️ Site", av_sites, index=None, placeholder="Select a site...", help="Choose the construction site.")

        con_sel_options = []
        if not df_con.empty:
            if "status" in df_con.columns:
                active_df = df_con[df_con["status"] != "Inactive"]
                con_sel_options = active_df["name"].unique().tolist()
            else:
                con_sel_options = df_con["name"].unique().tolist()

        con_sel = c3.selectbox("👷 Contractor", con_sel_options, index=None, placeholder="Select a contractor...", help="Choose the contractor whose workers you are logging.")

        if not st_sel or not con_sel:
            st.info("👆 Please select a **Site** and **Contractor** above to continue.")
        else:
            # Check for existing entry
            exist = None
            try:
                r = supabase.table("entries").select("*").eq("date", str(dt)).eq("site", st_sel).eq("contractor", con_sel).execute()
                if r.data:
                    exist = r.data[0]
            except:
                pass

            mode = "edit" if exist else "new"

            if mode == "edit":
                st.warning(f"✏️ An entry already exists for **{con_sel}** at **{st_sel}** on **{dt.strftime('%d %b %Y')}**. Saving will update it.")
            else:
                st.success(f"✅ Ready to log a **new entry** for **{con_sel}** at **{st_sel}** on **{dt.strftime('%d %b %Y')}**.")

            st.markdown("---")

            # Step 2: Work or Holiday?
            st.markdown("""<div class='step-card'><div class='step-label'>Step 2 — Work Status</div></div>""", unsafe_allow_html=True)
            is_nil_default = bool(exist and exist.get("count_mason") == 0 and exist.get("count_helper") == 0 and exist.get("count_ladies") == 0)
            is_nil = st.checkbox("⛔ Mark as Holiday / No Work (Nil Entry)", value=is_nil_default,
                                 help="Check this if no workers were present today. A nil entry will be recorded.")

            if is_nil:
                default_desc = "No Work / Holiday"
                if exist:
                    default_desc = exist.get("work_description", "No Work / Holiday")
                wdesc = st.text_input("📝 Reason for No Work", value=default_desc, placeholder="e.g. Sunday Holiday, Rain, Festival",
                                      help="Briefly state why no work happened. This appears in bills and logs.")
                nm, nh, nl, cost = 0, 0, 0, 0
                uploaded_photo = None
                st.info("ℹ️ This entry will be saved with zero workers. It shows as 'Nil' in the weekly bill.")
            else:
                # Step 3: Worker counts
                st.markdown("""<div class='step-card'><div class='step-label'>Step 3 — Enter Worker Counts</div></div>""", unsafe_allow_html=True)
                st.caption("Enter the number of workers present today. You can use 0.5 for half-day workers.")
                vm, vh, vl, vd = 0.0, 0.0, 0.0, ""
                if exist:
                    vm = float(exist.get("count_mason", 0))
                    vh = float(exist.get("count_helper", 0))
                    vl = float(exist.get("count_ladies", 0))
                    vd = exist.get("work_description", "")

                c4, c5, c6 = st.columns(3)
                nm = c4.number_input("🧱 Masons", value=vm, step=0.5, min_value=0.0, help="Number of mason workers today.")
                nh = c5.number_input("🛠️ Helpers", value=vh, step=0.5, min_value=0.0, help="Number of helper workers today.")
                nl = c6.number_input("👩 Ladies", value=vl, step=0.5, min_value=0.0, help="Number of ladies workers today.")

                wdesc = st.text_area("📝 Work Description", value=vd, placeholder="What work was done today? e.g. Slab casting on 3rd floor, Brickwork in Block A",
                                     help="Brief description of work done. Appears in audit logs.")

                # Fetch rate and show live cost preview
                rate_row = None
                try:
                    rr = supabase.table("contractors").select("*").eq("name", con_sel).lte("effective_date", str(dt)).order("effective_date", desc=True).limit(1).execute()
                    if rr.data:
                        rate_row = rr.data[0]
                except:
                    pass

                if rate_row:
                    cost = (nm * rate_row['rate_mason']) + (nh * rate_row['rate_helper']) + (nl * rate_row['rate_ladies'])
                    if st.session_state["role"] == "admin":
                        breakdown_parts = []
                        if nm > 0: breakdown_parts.append(f"{nm} Mason × ₹{rate_row['rate_mason']:,}")
                        if nh > 0: breakdown_parts.append(f"{nh} Helper × ₹{rate_row['rate_helper']:,}")
                        if nl > 0: breakdown_parts.append(f"{nl} Ladies × ₹{rate_row['rate_ladies']:,}")
                        breakdown_str = " + ".join(breakdown_parts) if breakdown_parts else "No workers entered yet"
                        st.markdown(f"""
                            <div class="cost-preview">
                                <div class="cost-preview-title">💰 Estimated Cost Preview</div>
                                <div class="cost-preview-amount">₹{cost:,.2f}</div>
                                <div class="cost-preview-breakdown">{breakdown_str}</div>
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("⚠️ No rate found for this contractor on the selected date. The entry will be saved with ₹0 cost. Please check contractor rates.")
                    cost = 0

                # Photo Upload
                st.markdown("""<div class='step-card'><div class='step-label'>Step 4 (Optional) — Upload Site Photo</div></div>""", unsafe_allow_html=True)
                uploaded_photo = st.file_uploader("📸 Upload a site photo or evidence", type=["jpg", "jpeg", "png", "webp"],
                                                  help="Optional. Attach a photo of the work done today for documentation.")
                if exist and exist.get("photo_url") and not uploaded_photo:
                    st.caption("📎 An existing photo is already attached. Upload a new one above to replace it.")

            # Save Button
            st.markdown("---")
            btn_label = "💾 Update Entry" if mode == "edit" else "💾 Save New Entry"
            if st.button(btn_label, type="primary", use_container_width=True):
                photo_link = ""
                if uploaded_photo:
                    with st.spinner("Uploading photo... please wait"):
                        photo_link = upload_evidence(uploaded_photo)
                elif exist and exist.get("photo_url"):
                    photo_link = exist.get("photo_url")

                load = {
                    "date": str(dt), "site": st_sel, "contractor": con_sel,
                    "count_mason": nm, "count_helper": nh, "count_ladies": nl,
                    "total_cost": cost, "work_description": wdesc,
                    "photo_url": photo_link
                }
                try:
                    if mode == "new":
                        supabase.table("entries").insert(load).execute()
                        st.success("✅ Entry saved successfully!")
                    else:
                        supabase.table("entries").update(load).eq("id", exist["id"]).execute()
                        st.success("✅ Entry updated successfully!")
                    time.sleep(1)
                    st.rerun()
                except Exception:
                    st.warning("⚠️ Network timeout while saving. Please click 'Save' again.")

    # Recent entries (admin only)
    if st.session_state["role"] == "admin":
        st.divider()
        st.subheader("📋 Recent Entries (Last 50)")
        st.caption("A quick view of the most recently saved entries across all sites.")
        try:
            response = supabase.table("entries").select("*").order("date", desc=True).limit(50).execute()
            if response.data:
                df_recent = pd.DataFrame(response.data)
                if "photo_url" in df_recent.columns:
                    df_recent["has_photo"] = df_recent["photo_url"].apply(lambda x: "📸 Yes" if x else "—")
                    cols_to_show = ["date", "site", "contractor", "total_cost", "work_description", "has_photo"]
                else:
                    cols_to_show = ["date", "site", "contractor", "total_cost", "work_description"]
                st.dataframe(df_recent[cols_to_show].rename(columns={
                    "date": "Date", "site": "Site", "contractor": "Contractor",
                    "total_cost": "Cost (₹)", "work_description": "Description"
                }), use_container_width=True, hide_index=True)
            else:
                empty_state("📋", "No entries yet", "Entries will appear here once the team starts logging.")
        except:
            pass

# ==============================================================================
# TAB 2: WEEKLY BILL
# ==============================================================================
elif current_tab == "📊 Weekly Bill":
    page_header("📊 Weekly Bill", "View weekly labour bills by site or contractor — download as PDF")
    try:
        df_entries = fetch_data("entries")
    except:
        df_entries = pd.DataFrame()
    render_weekly_bill(df_entries, fetch_data("contractors"))

# ==============================================================================
# TAB 3: MATERIALS
# ==============================================================================
elif current_tab == "🧱 Materials":
    page_header("🧱 Materials", "Track material purchases by site and category")
    df_sites = fetch_data("sites")
    if df_sites.empty:
        empty_state("🏗️", "No sites found", "Ask your admin to add sites before logging materials.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        if st.session_state["role"] != "admin":
            assigned_raw = st.session_state.get("assigned_site", "")
            if "All" not in assigned_raw and "None/All" not in assigned_raw:
                assigned_list = [s.strip() for s in assigned_raw.split(",")]
                av_sites = [s for s in av_sites if s in assigned_list]
            if not av_sites:
                empty_state("🔗", "No sites assigned", "You are not assigned to any active site. Contact your admin.")
                st.stop()

        sel_site = st.selectbox("📍 Select Site", av_sites, help="Choose the site whose material log you want to view or update.")
        st.divider()

        if sel_site:
            try:
                raw_materials = supabase.table("materials").select("*").eq("site", sel_site).execute()
                df_mat = pd.DataFrame(raw_materials.data) if raw_materials.data else pd.DataFrame()
            except Exception:
                df_mat = pd.DataFrame()
                st.error("⚠️ Error fetching materials data. Check your connection.")

            sel_week = "All Time"
            weeks = []

            if not df_mat.empty:
                df_mat["date_dt"] = pd.to_datetime(df_mat["date"], errors='coerce')
                df_mat = df_mat.dropna(subset=["date_dt"])
                if not df_mat.empty:
                    df_mat["start_date"] = df_mat["date_dt"].dt.date.apply(get_billing_start_date)
                    df_mat["end_date"] = df_mat["start_date"] + timedelta(days=6)
                    df_mat["week_label"] = df_mat.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
                    unique_weeks = df_mat[["start_date", "week_label"]].drop_duplicates().sort_values("start_date", ascending=False)
                    weeks = unique_weeks["week_label"].tolist()

            st.markdown("### 📅 Filter by Time Period")
            sel_week = st.selectbox("View Period", ["All Time"] + weeks,
                                    help="Filter the material view and PDF report to a specific week, or view everything.")

            if sel_week != "All Time" and not df_mat.empty:
                df_mat_filtered = df_mat[df_mat["week_label"] == sel_week].copy()
            else:
                df_mat_filtered = df_mat.copy()

            if not df_mat_filtered.empty:
                try:
                    pdf_bytes = generate_material_pdf_bytes(sel_site, sel_week, df_mat_filtered)
                    st.download_button(
                        label="⬇️ Download Material Report (PDF)",
                        data=pdf_bytes,
                        file_name=f"Materials_{sel_site}_{sel_week.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        help="Download a formatted PDF report of all materials for this site and time period."
                    )
                except Exception as e:
                    st.error(f"⚠️ Error generating PDF: {e}")
            else:
                st.info("ℹ️ No records in this period — no PDF to generate yet.")

            st.divider()

            categories = ["Civil Material", "Steel Material", "Soil Material", "RMC"]
            mat_tabs = st.tabs(categories)

            for i, cat in enumerate(categories):
                with mat_tabs[i]:
                    st.markdown(f"### ➕ Log New {cat} Entry")
                    st.caption(f"Fill in the details below to log a new {cat} purchase for **{sel_site}**.")
                    with st.form(f"form_{cat}"):
                        c1, c2, c3 = st.columns(3)
                        m_date = c1.date_input("📅 Purchase Date", date.today(), format="DD-MM-YYYY", key=f"d_{cat}")
                        m_vendor = c2.text_input("🏪 Vendor Name", key=f"v_{cat}", placeholder="e.g. ABC Suppliers")
                        m_material = c3.text_input("📦 Material Description", key=f"m_{cat}", placeholder="e.g. Cement (50kg bags)")
                        c4, c5 = st.columns(2)
                        m_qty = c4.number_input("📏 Quantity", min_value=0.0, step=1.0, key=f"q_{cat}", help="Number of units purchased.")
                        m_amt = c5.number_input("💰 Total Amount (₹)", min_value=0.0, step=100.0, key=f"a_{cat}", help="Total purchase amount in Rupees.")
                        m_receipt = st.file_uploader("🧾 Attach Bill/Receipt (Optional)", type=["jpg", "jpeg", "png"], key=f"rec_{cat}",
                                                     help="Upload a photo of the bill or receipt for documentation.")

                        if st.form_submit_button("💾 Save Material Entry", type="primary", use_container_width=True):
                            if not m_vendor.strip():
                                st.error("⚠️ Vendor name is required.")
                            elif not m_material.strip():
                                st.error("⚠️ Material description is required.")
                            else:
                                receipt_link = ""
                                if m_receipt:
                                    with st.spinner("Uploading receipt..."):
                                        receipt_link = upload_evidence(m_receipt)
                                load = {
                                    "date": str(m_date), "site": sel_site, "category": cat,
                                    "vendor": m_vendor.strip(), "material_name": m_material.strip(),
                                    "quantity": m_qty, "amount": m_amt, "receipt_url": receipt_link
                                }
                                try:
                                    supabase.table("materials").insert(load).execute()
                                    st.success(f"✅ {cat} entry saved successfully!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception:
                                    st.error("⚠️ Failed to save. Check your database connection.")

                    st.markdown("---")
                    st.markdown(f"### 📋 {cat} Log — {sel_week}")
                    if not df_mat_filtered.empty:
                        df_cat = df_mat_filtered[df_mat_filtered["category"] == cat].copy()
                        if not df_cat.empty:
                            df_cat = df_cat.sort_values("date_dt", ascending=False)
                            total_spent = df_cat["amount"].sum()
                            st.metric(f"Total Spent on {cat}", f"₹{total_spent:,.2f}")
                            display_df = df_cat[["date", "vendor", "material_name", "quantity", "amount"]].rename(
                                columns={"date": "Date", "vendor": "Vendor", "material_name": "Material", "quantity": "Qty", "amount": "Amount (₹)"}
                            )
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                        else:
                            empty_state("📦", f"No {cat} logged", f"Log a new {cat} entry using the form above.")
                    else:
                        empty_state("📦", "No materials logged yet", f"Use the form above to add your first {cat} entry for {sel_site}.")

# ==============================================================================
# TAB 4: MY DIARY
# ==============================================================================
elif current_tab == "📓 My Diary":
    page_header("📓 My Diary", "Private notes and site observations — only visible to you")
    st.info("📌 Your diary is completely private. No one else — not even admins — can see these notes.")

    user_phone = st.session_state.get("phone")
    if not user_phone:
        st.error("⚠️ Session error. Please log out and log back in.")
        st.stop()

    with st.form("diary_form"):
        d_date = st.date_input("📅 Date", date.today(), format="DD-MM-YYYY", help="Date for this note.")
        d_content = st.text_area("✍️ Your Note", height=150, placeholder="What happened today? Any observations, reminders, or things to follow up on?")
        if st.form_submit_button("💾 Save Note", type="primary"):
            if not d_content.strip():
                st.error("⚠️ Note cannot be empty. Write something before saving.")
            else:
                load = {"date": str(d_date), "phone": user_phone, "content": d_content.strip()}
                try:
                    supabase.table("diary_entries").insert(load).execute()
                    st.success("✅ Note saved!")
                    time.sleep(1)
                    st.rerun()
                except Exception:
                    st.error("⚠️ Failed to save note. Check your connection.")

    st.divider()
    st.markdown("### 📜 My Past Notes")

    try:
        res = supabase.table("diary_entries").select("*").eq("phone", user_phone).order("date", desc=True).execute()
        df_diary = pd.DataFrame(res.data) if res.data else pd.DataFrame()

        if not df_diary.empty:
            for _, row in df_diary.iterrows():
                formatted_date = pd.to_datetime(row['date']).strftime('%d %b %Y')
                with st.expander(f"📝 {formatted_date}"):
                    st.write(row['content'])
                    if st.button("🗑️ Delete this note", key=f"del_diary_{row['id']}", help="This cannot be undone."):
                        supabase.table("diary_entries").delete().eq("id", row['id']).execute()
                        st.rerun()
        else:
            empty_state("📓", "No notes yet", "Use the form above to write your first diary entry.")

    except Exception:
        st.error("⚠️ Error loading past notes. Try refreshing the page.")

# ==============================================================================
# ADMIN ONLY TABS
# ==============================================================================

elif current_tab == "📈 Dashboard":
    page_header("📈 Dashboard", "Financial analytics and workforce overview across all sites")

    st.markdown("### 📅 Select Date Range")
    st.caption("Adjust the date range to filter all metrics and charts below.")
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input("From", date.today() - timedelta(days=30), format="DD-MM-YYYY")
    with date_col2:
        end_date = st.date_input("To", date.today(), format="DD-MM-YYYY")

    st.divider()

    df_entries = fetch_data("entries")
    df_materials = fetch_data("materials")

    if not df_entries.empty:
        df_entries["date_dt"] = pd.to_datetime(df_entries["date"]).dt.date
        mask_entries = (df_entries["date_dt"] >= start_date) & (df_entries["date_dt"] <= end_date)
        df_e_filtered = df_entries.loc[mask_entries]
        total_labor_spent = df_e_filtered["total_cost"].sum() if not df_e_filtered.empty else 0
        total_masons = df_e_filtered["count_mason"].sum() if not df_e_filtered.empty else 0
        total_helpers = df_e_filtered["count_helper"].sum() if not df_e_filtered.empty else 0
    else:
        df_e_filtered, total_labor_spent, total_masons, total_helpers = pd.DataFrame(), 0, 0, 0

    if not df_materials.empty:
        df_materials["date_dt"] = pd.to_datetime(df_materials["date"]).dt.date
        mask_mat = (df_materials["date_dt"] >= start_date) & (df_materials["date_dt"] <= end_date)
        df_m_filtered = df_materials.loc[mask_mat]
        total_mat_spent = df_m_filtered["amount"].sum() if not df_m_filtered.empty else 0
    else:
        df_m_filtered, total_mat_spent = pd.DataFrame(), 0

    grand_total = total_labor_spent + total_mat_spent

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔥 Total Expenses", f"₹{grand_total:,.0f}", help="Labor + Materials combined for this period.")
    k2.metric("👷 Labour Cost", f"₹{total_labor_spent:,.0f}", help="Total contractor payments for this period.")
    k3.metric("🧱 Material Cost", f"₹{total_mat_spent:,.0f}", help="Total material purchases for this period.")
    k4.metric("📋 Workforce Shifts", f"{int(total_masons + total_helpers)}", help="Total mason + helper shifts logged in this period.")

    st.divider()
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("### 📍 Total Spend by Site")
        site_totals = {}
        if not df_e_filtered.empty:
            for _, r in df_e_filtered.iterrows():
                site_totals[r["site"]] = site_totals.get(r["site"], 0) + r["total_cost"]
        if not df_m_filtered.empty:
            for _, r in df_m_filtered.iterrows():
                site_totals[r["site"]] = site_totals.get(r["site"], 0) + r["amount"]
        if site_totals:
            df_site_cost = pd.DataFrame(list(site_totals.items()), columns=["Site", "Total Cost (₹)"])
            st.bar_chart(df_site_cost.set_index("Site"), color="#F39C12")
        else:
            empty_state("📍", "No data for this date range", "Try expanding the date range.")

    with chart_col2:
        st.markdown("### 🧱 Material Spend by Category")
        if not df_m_filtered.empty:
            cat_cost = df_m_filtered.groupby("category")["amount"].sum().reset_index()
            cat_cost.columns = ["Category", "Amount (₹)"]
            st.bar_chart(cat_cost.set_index("Category"), color="#2E86C1")
        else:
            empty_state("🧱", "No materials logged", "No material entries found in this date range.")

elif current_tab == "🧾 Client Invoice":
    page_header("🧾 Client Invoice", "Bill your client for civil pre-work labour + materials procured on their behalf")

    df_sites = fetch_data("sites")
    if df_sites.empty:
        empty_state("🏗️", "No sites available", "Add sites first before generating invoices.")
    else:
        if "is_client_site" in df_sites.columns:
            client_sites = df_sites[df_sites["is_client_site"] == True]["name"].tolist()
        else:
            client_sites = []
            st.error("⚠️ Database Setup Required: The 'is_client_site' column is missing from your 'sites' table in Supabase. Please add it as a boolean column.")

        if not client_sites:
            st.info("💡 No sites are marked for client billing. Go to **Supabase → Table Editor → sites** and tick **is_client_site** for the relevant sites.")
        else:
            # ── STEP 1: Site & Date Range ──────────────────────────────────────────
            st.markdown("### Step 1 — Select Site & Date Range")
            c1, c2, c3 = st.columns(3)
            inv_site  = c1.selectbox("🏗️ Project Site", client_sites, help="Only sites marked for client billing appear here.")
            inv_start = c2.date_input("📅 From", date.today() - timedelta(days=6), format="DD-MM-YYYY")
            inv_end   = c3.date_input("📅 To",   date.today(),                      format="DD-MM-YYYY")

            st.divider()

            # ── STEP 2: Civil / Pre-work Labour — Weekly Breakdown ─────────────────
            st.markdown("### Step 2 — Civil & Pre-Work Labour")
            st.caption(
                "Labour done before interior work (e.g. wall demolition, civil changes) — "
                "NOT in your interior quote. The entries are grouped week-by-week (Saturday to Friday). "
                "Set the rate you want to charge the client per shift."
            )

            # Pull logged shifts for this site & period
            df_entries = fetch_data("entries")
            df_e_site = pd.DataFrame()

            if not df_entries.empty:
                df_entries["date_dt"] = pd.to_datetime(df_entries["date"]).dt.date
                mask_e = (df_entries["site"] == inv_site) & \
                         (df_entries["date_dt"] >= inv_start) & \
                         (df_entries["date_dt"] <= inv_end)
                df_e_site = df_entries[mask_e].copy()

            # Build week buckets (Sat–Fri) covering the selected range
            def get_week_start(d):
                # Saturday = weekday 5
                days_since_sat = (d.weekday() + 2) % 7
                return d - timedelta(days=days_since_sat)

            # Collect all unique week starts that appear in the data
            week_starts = set()
            if not df_e_site.empty:
                for d in df_e_site["date_dt"]:
                    week_starts.add(get_week_start(d))
            # Also cover the selected range even if no entries some weeks
            cur = get_week_start(inv_start)
            while cur <= inv_end:
                week_starts.add(cur)
                cur += timedelta(days=7)
            week_starts = sorted(week_starts)

            # Summary reference info box
            if not df_e_site.empty:
                tot_m_all = df_e_site["count_mason"].sum()
                tot_h_all = df_e_site["count_helper"].sum()
                tot_l_all = df_e_site["count_ladies"].sum()
                tot_cost_all = df_e_site["total_cost"].sum()
                st.info(
                    f"📊 Logged entries this period — "
                    f"Masons: **{tot_m_all:.0f}**, Helpers: **{tot_h_all:.0f}**, Ladies: **{tot_l_all:.0f}** "
                    f"| Internal payout: **Rs. {tot_cost_all:,.0f}**"
                )
            else:
                st.info("ℹ️ No labour entries logged for this site in the selected period.")

            # Client billing rates (charged to client, can differ from internal rates)
            st.markdown("**Set client billing rates (per shift):**")
            c_r1, c_r2, c_r3 = st.columns(3)
            client_rate_mason  = c_r1.number_input("Rate/shift — Mason (Rs)",  min_value=0.0, value=0.0, step=50.0, key="cr_m")
            client_rate_helper = c_r2.number_input("Rate/shift — Helper (Rs)", min_value=0.0, value=0.0, step=50.0, key="cr_h")
            client_rate_ladies = c_r3.number_input("Rate/shift — Ladies (Rs)", min_value=0.0, value=0.0, step=50.0, key="cr_l")

            # Build weekly rows for display and PDF
            weekly_labour_rows = []
            for ws in week_starts:
                we = ws + timedelta(days=6)
                # Filter entries in this week
                if not df_e_site.empty:
                    mask_w = (df_e_site["date_dt"] >= ws) & (df_e_site["date_dt"] <= we)
                    df_week = df_e_site[mask_w]
                    wm = float(df_week["count_mason"].sum())
                    wh = float(df_week["count_helper"].sum())
                    wl = float(df_week["count_ladies"].sum())
                else:
                    wm = wh = wl = 0.0
                wamt = (wm * client_rate_mason) + (wh * client_rate_helper) + (wl * client_rate_ladies)
                weekly_labour_rows.append({
                    "week":    f"{ws.strftime('%d-%m-%Y')} to {we.strftime('%d-%m-%Y')}",
                    "mason":   wm, "helper": wh, "ladies": wl,
                    "rate_m":  client_rate_mason,
                    "rate_h":  client_rate_helper,
                    "rate_l":  client_rate_ladies,
                    "amount":  wamt
                })

            # Show weekly breakdown table in UI (admin sees full detail including worker counts)
            if weekly_labour_rows:
                st.markdown("**Weekly breakdown (your view — worker counts hidden in client PDF):**")
                display_rows = []
                for wr in weekly_labour_rows:
                    display_rows.append({
                        "Week": wr["week"],
                        "Mason": f"{wr['mason']:.1f}" if wr['mason'] else "-",
                        "Helper": f"{wr['helper']:.1f}" if wr['helper'] else "-",
                        "Ladies": f"{wr['ladies']:.1f}" if wr['ladies'] else "-",
                        "Amount (Rs)": f"{wr['amount']:,.2f}"
                    })
                st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
                st.caption("🔒 The client PDF shows only the week period and amount — worker shift counts and rates are not included.")

            total_labor = sum(r["amount"] for r in weekly_labour_rows)
            tot_mason   = sum(r["mason"]  for r in weekly_labour_rows)
            tot_helper  = sum(r["helper"] for r in weekly_labour_rows)
            tot_ladies  = sum(r["ladies"] for r in weekly_labour_rows)

            st.metric("Total Labour to Recover from Client", f"Rs. {total_labor:,.2f}")

            labor_details = {
                'm_count': tot_mason,   'm_rate': client_rate_mason,
                'h_count': tot_helper,  'h_rate': client_rate_helper,
                'l_count': tot_ladies,  'l_rate': client_rate_ladies,
                'total':   total_labor
            }

            st.divider()

            # ── STEP 3: Materials — two buckets ────────────────────────────────────
            st.markdown("### Step 3 — Materials")
            st.markdown("""
            <div style='background:#EEF9FF; border-left:4px solid #2980B9; border-radius:8px; padding:0.8rem 1.2rem; margin-bottom:1rem;'>
            <b>How this works:</b><br>
            Use <b>🔴 Client-Procured</b> for materials the client purchased but billed to your name (e.g. A/C unit, tiles) — 
            you paid the vendor from your account and need to recover this amount from the client.<br><br>
            Use <b>🟢 Our Scope</b> for materials that are already included in your project quote — 
            these appear in the PDF as "Included in Quote" with <b>no charge</b>.
            </div>
            """, unsafe_allow_html=True)

            # Fetch all materials for this site & period
            df_materials = fetch_data("materials")
            df_m_filtered = pd.DataFrame()

            if not df_materials.empty:
                df_materials["date_dt"] = pd.to_datetime(df_materials["date"]).dt.date
                mask_m = (df_materials["site"] == inv_site) & \
                         (df_materials["date_dt"] >= inv_start) & \
                         (df_materials["date_dt"] <= inv_end)
                df_m_filtered = df_materials[mask_m].copy()
                if not df_m_filtered.empty:
                    df_m_filtered["formatted_date"] = pd.to_datetime(df_m_filtered["date"]).dt.strftime('%d-%m-%Y')

            # Split by invoice_scope column (if it exists), otherwise default all to client
            CLIENT_SCOPE = "Client-Procured"
            OUR_SCOPE    = "Our Scope"

            has_scope_col = not df_m_filtered.empty and "invoice_scope" in df_m_filtered.columns

            if has_scope_col:
                df_client_scope = df_m_filtered[df_m_filtered["invoice_scope"] == CLIENT_SCOPE].copy()
                df_our_scope    = df_m_filtered[df_m_filtered["invoice_scope"] == OUR_SCOPE].copy()
            else:
                # If no scope column yet, treat everything as client-procured by default
                df_client_scope = df_m_filtered.copy()
                df_our_scope    = pd.DataFrame()

            # ── 3a: Client-Procured Materials ────────────────────────────────────
            mat_tab_client, mat_tab_ours = st.tabs(["🔴 Client-Procured Materials (To Recover)", "🟢 Our Scope Materials (Included in Quote)"])

            with mat_tab_client:
                st.caption("Items purchased/billed in your name at the client's request — you paid, now recover.")

                if not df_client_scope.empty:
                    df_show_c = df_client_scope[["formatted_date", "vendor", "material_name", "amount"]].rename(
                        columns={"formatted_date": "Date", "vendor": "Vendor", "material_name": "Description", "amount": "Amount (₹)"}
                    )
                    st.dataframe(df_show_c, use_container_width=True, hide_index=True)
                    total_client_mat = df_client_scope["amount"].sum()
                    st.metric("Total to Recover — Client Materials", f"₹{total_client_mat:,.2f}")
                else:
                    st.info("ℹ️ No client-procured materials logged for this period. Add them below.")
                    total_client_mat = 0

                st.markdown("#### ➕ Add Client-Procured Material")
                with st.form("add_client_mat"):
                    cc1, cc2 = st.columns([1, 2])
                    cm_date   = cc1.date_input("Date", inv_end, format="DD-MM-YYYY")
                    cm_vendor = cc2.text_input("Vendor / Supplier Name", placeholder="e.g. Samsung, XYZ Tiles")
                    cc3, cc4 = st.columns([3, 1])
                    cm_desc   = cc3.text_input("Description", placeholder="e.g. Split A/C 1.5 Ton (billed to our name)")
                    cm_amt    = cc4.number_input("Amount (₹)", min_value=0.0, step=100.0)
                    if st.form_submit_button("💾 Save Client Material", type="primary"):
                        if cm_desc.strip() and cm_vendor.strip():
                            scope_val = CLIENT_SCOPE if has_scope_col else None
                            load = {
                                "date": str(cm_date), "site": inv_site, "category": "Bill",
                                "vendor": cm_vendor.strip(), "material_name": cm_desc.strip(),
                                "quantity": 1, "amount": cm_amt, "receipt_url": ""
                            }
                            if has_scope_col:
                                load["invoice_scope"] = CLIENT_SCOPE
                            supabase.table("materials").insert(load).execute()
                            st.success("✅ Client material saved!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("⚠️ Please enter both a vendor name and a description.")

                # Edit / Delete for client-scope materials
                if not df_client_scope.empty:
                    with st.expander("✏️ Edit or Delete a Client-Procured Entry"):
                        edit_opts_c = {
                            f"{row['formatted_date']} — {row['material_name']} — ₹{row['amount']}": row
                            for _, row in df_client_scope.iterrows()
                        }
                        sel_c = st.selectbox("Select entry", list(edit_opts_c.keys()), key="sel_edit_c")
                        row_c = edit_opts_c[sel_c]
                        with st.form("edit_client_mat"):
                            ec1, ec2 = st.columns([1, 2])
                            ec_date   = ec1.date_input("Date", pd.to_datetime(row_c["date"]).date(), format="DD-MM-YYYY")
                            ec_vendor = ec2.text_input("Vendor", value=str(row_c.get("vendor", "")))
                            ec3, ec4  = st.columns([3, 1])
                            ec_desc   = ec3.text_input("Description", value=str(row_c["material_name"]))
                            ec_amt    = ec4.number_input("Amount (₹)", value=float(row_c["amount"]), step=100.0)
                            col_upd, col_del = st.columns(2)
                            if col_upd.form_submit_button("✅ Update"):
                                upd = {"date": str(ec_date), "vendor": ec_vendor, "material_name": ec_desc, "amount": ec_amt}
                                supabase.table("materials").update(upd).eq("id", int(row_c["id"])).execute()
                                st.success("✅ Updated!")
                                time.sleep(1)
                                st.rerun()
                            if col_del.form_submit_button("🗑️ Delete"):
                                supabase.table("materials").delete().eq("id", int(row_c["id"])).execute()
                                st.success("✅ Deleted.")
                                time.sleep(1)
                                st.rerun()

            with mat_tab_ours:
                st.caption("Materials covered by your project quote — they appear in the PDF as 'Included in Quote' with no additional charge to the client.")

                if not df_our_scope.empty:
                    df_show_o = df_our_scope[["formatted_date", "material_name", "amount"]].rename(
                        columns={"formatted_date": "Date", "material_name": "Description", "amount": "Our Cost (₹)"}
                    )
                    df_show_o["Status"] = "✅ Included in Quote"
                    st.dataframe(df_show_o, use_container_width=True, hide_index=True)
                    st.caption(f"Our-scope total (internal reference only): ₹{df_our_scope['amount'].sum():,.2f} — not billed to client.")
                else:
                    st.info("ℹ️ No our-scope materials logged for this period. Add them below to document what is covered in your quote.")

                st.markdown("#### ➕ Add Our-Scope Material")
                with st.form("add_our_mat"):
                    oc1, oc2 = st.columns([1, 2])
                    om_date  = oc1.date_input("Date", inv_end, format="DD-MM-YYYY", key="om_date")
                    om_desc  = oc2.text_input("Material Description", placeholder="e.g. Paint (included in quote)")
                    oc3, oc4 = st.columns(2)
                    om_cat   = oc3.selectbox("Category", ["Civil Material", "Steel Material", "Soil Material", "RMC", "Other"], key="om_cat")
                    om_amt   = oc4.number_input("Our Cost (₹)", min_value=0.0, step=100.0, key="om_amt",
                                                help="Your internal cost — this is NOT charged to the client.")
                    if st.form_submit_button("💾 Save Our-Scope Material", type="primary"):
                        if om_desc.strip():
                            load = {
                                "date": str(om_date), "site": inv_site, "category": om_cat,
                                "vendor": "Our Scope", "material_name": om_desc.strip(),
                                "quantity": 1, "amount": om_amt, "receipt_url": ""
                            }
                            if has_scope_col:
                                load["invoice_scope"] = OUR_SCOPE
                            supabase.table("materials").insert(load).execute()
                            st.success("✅ Our-scope material saved!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("⚠️ Please enter a material description.")

                if not df_our_scope.empty:
                    with st.expander("✏️ Edit or Delete an Our-Scope Entry"):
                        edit_opts_o = {
                            f"{row['formatted_date']} — {row['material_name']} — ₹{row['amount']}": row
                            for _, row in df_our_scope.iterrows()
                        }
                        sel_o = st.selectbox("Select entry", list(edit_opts_o.keys()), key="sel_edit_o")
                        row_o = edit_opts_o[sel_o]
                        with st.form("edit_our_mat"):
                            eo1, eo2 = st.columns([1, 2])
                            eo_date  = eo1.date_input("Date", pd.to_datetime(row_o["date"]).date(), format="DD-MM-YYYY")
                            eo_desc  = eo2.text_input("Description", value=str(row_o["material_name"]))
                            eo_amt   = st.number_input("Our Cost (₹)", value=float(row_o["amount"]), step=100.0)
                            eoc1, eoc2 = st.columns(2)
                            if eoc1.form_submit_button("✅ Update"):
                                supabase.table("materials").update({
                                    "date": str(eo_date), "material_name": eo_desc, "amount": eo_amt
                                }).eq("id", int(row_o["id"])).execute()
                                st.success("✅ Updated!")
                                time.sleep(1)
                                st.rerun()
                            if eoc2.form_submit_button("🗑️ Delete"):
                                supabase.table("materials").delete().eq("id", int(row_o["id"])).execute()
                                st.success("✅ Deleted.")
                                time.sleep(1)
                                st.rerun()

            # ── Scope column hint ─────────────────────────────────────────────────
            if not has_scope_col and not df_m_filtered.empty:
                st.warning(
                    "⚠️ **Tip:** Your `materials` table doesn't have an `invoice_scope` column yet. "
                    "All existing materials are treated as Client-Procured for now. "
                    "Add a text column named `invoice_scope` to Supabase to separate them properly going forward."
                )

            st.divider()

            # ── STEP 4: Summary & PDF ──────────────────────────────────────────────
            st.markdown("### Step 4 — Invoice Summary & PDF")

            # Build PDF DataFrames
            pdf_client_mats = pd.DataFrame(columns=["Date", "Vendor", "Description", "Amount (Rs)"])
            pdf_our_mats    = pd.DataFrame(columns=["Date", "Description"])

            if not df_client_scope.empty:
                pdf_client_mats = df_client_scope[["formatted_date", "vendor", "material_name", "amount"]].rename(
                    columns={"formatted_date": "Date", "vendor": "Vendor",
                             "material_name": "Description", "amount": "Amount (Rs)"}
                )
            if not df_our_scope.empty:
                pdf_our_mats = df_our_scope[["formatted_date", "material_name"]].rename(
                    columns={"formatted_date": "Date", "material_name": "Description"}
                )

            total_client_mat = df_client_scope["amount"].sum() if not df_client_scope.empty else 0.0
            grand_total = total_labor + total_client_mat

            # Summary box
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Civil Labour (to recover)", f"₹{total_labor:,.2f}")
            col_s2.metric("Client Materials (to recover)", f"₹{total_client_mat:,.2f}")
            col_s3.metric("💰 Grand Total to Recover", f"₹{grand_total:,.2f}")

            st.caption("Grand Total = Civil/Pre-work Labour + Client-Procured Materials. Our-scope items are listed in the PDF but carry no charge.")

            if st.button("📄 Generate Client Invoice PDF", type="primary", use_container_width=True):
                date_label = f"{inv_start.strftime('%d-%m-%Y')} to {inv_end.strftime('%d-%m-%Y')}"
                with st.spinner("Building your invoice..."):
                    pdf_bytes = generate_client_invoice_bytes(
                        inv_site, date_label, labor_details,
                        pdf_client_mats, pdf_our_mats, grand_total,
                        weekly_labour_rows=weekly_labour_rows
                    )
                st.success("✅ Invoice ready!")
                st.download_button(
                    label="⬇️ Download Client Invoice (PDF)",
                    data=pdf_bytes,
                    file_name=f"Client_Invoice_{inv_site}_{inv_start.strftime('%d%b%Y')}.pdf",
                    mime="application/pdf"
                )

elif current_tab == "🎨 Client Materials":
    # ── DESIGNER-ONLY TAB ─────────────────────────────────────────────────────
    # Interior designers can log and manage materials for client invoices.
    # They see NO labour costs, no financial totals — only material entry.
    if not is_designer and not is_admin:
        st.error("⛔ You don't have access to this page.")
        st.stop()

    page_header("🎨 Client Materials", "Log and manage materials for client projects")

    df_sites = fetch_data("sites")
    # Designers see only their assigned sites
    av_sites = df_sites["name"].tolist() if not df_sites.empty else []
    if not is_admin:
        assigned_raw = st.session_state.get("assigned_site", "")
        if "All" not in assigned_raw and "None/All" not in assigned_raw and assigned_raw.strip():
            assigned_list = [s.strip() for s in assigned_raw.split(",")]
            av_sites = [s for s in av_sites if s in assigned_list]

    if not av_sites:
        empty_state("🏗️", "No sites assigned", "Ask your admin to assign you to a project site.")
        st.stop()

    inv_site = st.selectbox("🏗️ Select Project Site", av_sites)
    c_d1, c_d2 = st.columns(2)
    inv_start = c_d1.date_input("📅 From", date.today() - timedelta(days=30), format="DD-MM-YYYY")
    inv_end   = c_d2.date_input("📅 To",   date.today(),                      format="DD-MM-YYYY")

    st.divider()

    # Fetch materials for this site & period
    df_materials = fetch_data("materials")
    df_m_filtered = pd.DataFrame()

    if not df_materials.empty:
        df_materials["date_dt"] = pd.to_datetime(df_materials["date"]).dt.date
        mask_m = (df_materials["site"] == inv_site) & \
                 (df_materials["date_dt"] >= inv_start) & \
                 (df_materials["date_dt"] <= inv_end)
        df_m_filtered = df_materials[mask_m].copy()
        if not df_m_filtered.empty:
            df_m_filtered["formatted_date"] = pd.to_datetime(df_m_filtered["date"]).dt.strftime('%d-%m-%Y')

    CLIENT_SCOPE = "Client-Procured"
    OUR_SCOPE    = "Our Scope"
    has_scope_col = not df_m_filtered.empty and "invoice_scope" in df_m_filtered.columns

    if has_scope_col:
        df_client_scope = df_m_filtered[df_m_filtered["invoice_scope"] == CLIENT_SCOPE].copy()
        df_our_scope    = df_m_filtered[df_m_filtered["invoice_scope"] == OUR_SCOPE].copy()
    else:
        df_client_scope = df_m_filtered.copy()
        df_our_scope    = pd.DataFrame()

    st.markdown("""
    <div style='background:#EEF9FF; border-left:4px solid #2980B9; border-radius:8px; padding:0.8rem 1.2rem; margin-bottom:1rem;'>
    <b>🔴 Client-Procured</b> — Items purchased/billed in the company's name at the client's request (e.g. A/C, tiles).
    The company paid the vendor; the client owes this amount back.<br><br>
    <b>🟢 Our Scope</b> — Materials already included in the project quote. No additional charge to the client.
    </div>
    """, unsafe_allow_html=True)

    mat_tab_client, mat_tab_ours = st.tabs(["🔴 Client-Procured Materials", "🟢 Our Scope Materials"])

    # ── CLIENT-PROCURED TAB ───────────────────────────────────────────────────
    with mat_tab_client:
        st.caption("Items the client selected but were billed to the company — needs to be recovered from client.")

        if not df_client_scope.empty:
            df_show_c = df_client_scope[["formatted_date", "vendor", "material_name"]].rename(
                columns={"formatted_date": "Date", "vendor": "Vendor", "material_name": "Description"}
            )
            st.dataframe(df_show_c, use_container_width=True, hide_index=True)
            st.caption(f"**{len(df_client_scope)} entries** in this period.")
        else:
            st.info("ℹ️ No client-procured materials logged yet. Add them below.")

        st.markdown("#### ➕ Add Client-Procured Material")
        with st.form("designer_add_client_mat"):
            dc1, dc2 = st.columns([1, 2])
            cm_date   = dc1.date_input("Date of Purchase", inv_end, format="DD-MM-YYYY")
            cm_vendor = dc2.text_input("Vendor / Supplier", placeholder="e.g. Samsung, XYZ Tiles, Kohler")
            dc3, dc4  = st.columns([3, 1])
            cm_desc   = dc3.text_input("Description", placeholder="e.g. Split A/C 1.5 Ton, Vitrified Floor Tiles (600×600)")
            cm_qty    = dc4.number_input("Quantity", min_value=0.0, step=1.0, value=1.0)
            cm_amt    = st.number_input("Total Amount (₹)", min_value=0.0, step=100.0,
                                        help="The amount the vendor charged — billed to company, to recover from client.")
            cm_receipt = st.file_uploader("🧾 Attach Bill / Receipt (optional)", type=["jpg", "jpeg", "png"])

            if st.form_submit_button("💾 Save", type="primary"):
                if not cm_desc.strip():
                    st.error("⚠️ Please enter a description.")
                elif not cm_vendor.strip():
                    st.error("⚠️ Please enter the vendor name.")
                else:
                    receipt_link = ""
                    if cm_receipt:
                        with st.spinner("Uploading receipt..."):
                            receipt_link = upload_evidence(cm_receipt)
                    load = {
                        "date": str(cm_date), "site": inv_site, "category": "Bill",
                        "vendor": cm_vendor.strip(), "material_name": cm_desc.strip(),
                        "quantity": cm_qty, "amount": cm_amt, "receipt_url": receipt_link
                    }
                    if has_scope_col:
                        load["invoice_scope"] = CLIENT_SCOPE
                    try:
                        supabase.table("materials").insert(load).execute()
                        st.success("✅ Saved!")
                        time.sleep(1)
                        st.rerun()
                    except Exception:
                        st.error("⚠️ Failed to save. Check your connection.")

        if not df_client_scope.empty:
            with st.expander("✏️ Edit or Delete an Entry"):
                edit_opts = {
                    f"{row['formatted_date']} — {row['material_name']} ({row.get('vendor','')})": row
                    for _, row in df_client_scope.iterrows()
                }
                sel_key = st.selectbox("Select entry", list(edit_opts.keys()), key="des_sel_c")
                sel_row = edit_opts[sel_key]
                with st.form("designer_edit_client_mat"):
                    de1, de2 = st.columns([1, 2])
                    e_date   = de1.date_input("Date", pd.to_datetime(sel_row["date"]).date(), format="DD-MM-YYYY")
                    e_vendor = de2.text_input("Vendor", value=str(sel_row.get("vendor", "")))
                    de3, de4 = st.columns([3, 1])
                    e_desc   = de3.text_input("Description", value=str(sel_row["material_name"]))
                    e_qty    = de4.number_input("Qty", value=float(sel_row.get("quantity", 1)), step=1.0)
                    e_amt    = st.number_input("Amount (₹)", value=float(sel_row["amount"]), step=100.0)
                    btn1, btn2 = st.columns(2)
                    if btn1.form_submit_button("✅ Update"):
                        supabase.table("materials").update({
                            "date": str(e_date), "vendor": e_vendor,
                            "material_name": e_desc, "quantity": e_qty, "amount": e_amt
                        }).eq("id", int(sel_row["id"])).execute()
                        st.success("✅ Updated!")
                        time.sleep(1)
                        st.rerun()
                    if btn2.form_submit_button("🗑️ Delete"):
                        supabase.table("materials").delete().eq("id", int(sel_row["id"])).execute()
                        st.success("✅ Deleted.")
                        time.sleep(1)
                        st.rerun()

    # ── OUR-SCOPE TAB ─────────────────────────────────────────────────────────
    with mat_tab_ours:
        st.caption("Materials already covered in the project quote — no extra charge to the client.")

        if not df_our_scope.empty:
            df_show_o = df_our_scope[["formatted_date", "material_name"]].rename(
                columns={"formatted_date": "Date", "material_name": "Description"}
            )
            df_show_o["Status"] = "✅ Included in Quote"
            st.dataframe(df_show_o, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No our-scope materials logged yet. Add them below.")

        st.markdown("#### ➕ Add Our-Scope Material")
        with st.form("designer_add_our_mat"):
            oc1, oc2 = st.columns([1, 2])
            om_date = oc1.date_input("Date", inv_end, format="DD-MM-YYYY", key="des_om_date")
            om_desc = oc2.text_input("Material Description", placeholder="e.g. Wall Paint — Asian Paints Royale")
            oc3, oc4 = st.columns(2)
            om_cat  = oc3.selectbox("Category", ["Civil Material", "Steel Material", "Soil Material", "RMC", "Other"], key="des_om_cat")
            om_qty  = oc4.number_input("Quantity", min_value=0.0, step=1.0, value=1.0, key="des_om_qty")

            if st.form_submit_button("💾 Save", type="primary"):
                if om_desc.strip():
                    load = {
                        "date": str(om_date), "site": inv_site, "category": om_cat,
                        "vendor": "Our Scope", "material_name": om_desc.strip(),
                        "quantity": om_qty, "amount": 0.0, "receipt_url": ""
                    }
                    if has_scope_col:
                        load["invoice_scope"] = OUR_SCOPE
                    try:
                        supabase.table("materials").insert(load).execute()
                        st.success("✅ Saved!")
                        time.sleep(1)
                        st.rerun()
                    except Exception:
                        st.error("⚠️ Failed to save. Check your connection.")
                else:
                    st.error("⚠️ Please enter a description.")

        if not df_our_scope.empty:
            with st.expander("✏️ Edit or Delete an Entry"):
                edit_opts_o = {
                    f"{row['formatted_date']} — {row['material_name']}": row
                    for _, row in df_our_scope.iterrows()
                }
                sel_key_o = st.selectbox("Select entry", list(edit_opts_o.keys()), key="des_sel_o")
                sel_row_o = edit_opts_o[sel_key_o]
                with st.form("designer_edit_our_mat"):
                    oe1, oe2 = st.columns([1, 2])
                    oe_date = oe1.date_input("Date", pd.to_datetime(sel_row_o["date"]).date(), format="DD-MM-YYYY")
                    oe_desc = oe2.text_input("Description", value=str(sel_row_o["material_name"]))
                    oe_qty  = st.number_input("Quantity", value=float(sel_row_o.get("quantity", 1)), step=1.0)
                    ob1, ob2 = st.columns(2)
                    if ob1.form_submit_button("✅ Update"):
                        supabase.table("materials").update({
                            "date": str(oe_date), "material_name": oe_desc, "quantity": oe_qty
                        }).eq("id", int(sel_row_o["id"])).execute()
                        st.success("✅ Updated!")
                        time.sleep(1)
                        st.rerun()
                    if ob2.form_submit_button("🗑️ Delete"):
                        supabase.table("materials").delete().eq("id", int(sel_row_o["id"])).execute()
                        st.success("✅ Deleted.")
                        time.sleep(1)
                        st.rerun()

elif current_tab == "🔍 Site Logs":
    page_header("🔍 Site Logs", "Browse, audit, and manage all recorded entries")
    response = supabase.table("entries").select("*").order("date", desc=True).limit(500).execute()
    df_e = pd.DataFrame(response.data)
    st.caption("Showing last 500 entries across all sites, most recent first.")

    if not df_e.empty:
        df_e["date_obj"] = pd.to_datetime(df_e["date"], errors='coerce')
        df_e = df_e.dropna(subset=["date_obj"])
        df_e["Date"] = df_e["date_obj"].dt.strftime('%d-%m-%Y')

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            fil_site = st.selectbox("Filter by Site", ["All Sites"] + sorted(df_e["site"].unique().tolist()), help="Narrow down entries to a specific site.")
        with filter_col2:
            fil_con = st.selectbox("Filter by Contractor", ["All Contractors"] + sorted(df_e["contractor"].unique().tolist()), help="Narrow down entries to a specific contractor.")

        if fil_site != "All Sites":
            df_e = df_e[df_e["site"] == fil_site]
        if fil_con != "All Contractors":
            df_e = df_e[df_e["contractor"] == fil_con]

        if "photo_url" in df_e.columns:
            df_e["Photo"] = df_e["photo_url"].apply(lambda x: "📸 Yes" if x else "—")
            cols = ["id", "Date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description", "Photo"]
        else:
            cols = ["id", "Date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description"]

        st.dataframe(df_e[cols].rename(columns={
            "id": "ID", "site": "Site", "contractor": "Contractor",
            "count_mason": "Masons", "count_helper": "Helpers", "count_ladies": "Ladies",
            "total_cost": "Cost (₹)", "work_description": "Description"
        }), use_container_width=True, hide_index=True)

        st.divider()
        with st.expander("🗑️ Delete an Entry by ID"):
            st.warning("⚠️ **Danger zone:** Deleting an entry is permanent and cannot be undone. Use the ID from the table above.")
            col_d1, col_d2 = st.columns([1, 2])
            del_id = col_d1.number_input("Entry ID to Delete", step=1, value=0, min_value=0)
            del_code = col_d2.text_input("Security Code", type="password", placeholder="Enter admin security code")
            if st.button("🗑️ Delete Permanently", type="primary"):
                if not del_id:
                    st.error("⚠️ Please enter a valid Entry ID.")
                elif del_code == ADMIN_DELETE_CODE:
                    supabase.table("entries").delete().eq("id", int(del_id)).execute()
                    st.success(f"✅ Entry ID {del_id} has been deleted.")
                    st.rerun()
                else:
                    st.error("❌ Wrong security code. Deletion cancelled.")
    else:
        empty_state("📋", "No entries found", "No records have been logged yet.")

elif current_tab == "📍 Sites":
    page_header("📍 Sites", "Add and manage construction sites")
    sites_df = fetch_data("sites")
    if not sites_df.empty:
        st.dataframe(sites_df, hide_index=True, use_container_width=True)
    else:
        empty_state("🏗️", "No sites added yet", "Add your first site using the form below.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### ➕ Add New Site")
        n = st.text_input("Site Name", placeholder="e.g. Green Valley Block B")
        if st.button("Add Site", type="primary"):
            if n.strip():
                supabase.table("sites").insert({"name": n.strip()}).execute()
                st.success(f"✅ Site '{n}' added!")
                st.rerun()
            else:
                st.error("⚠️ Please enter a site name.")

    with c2:
        st.markdown("#### 🗑️ Delete a Site")
        st.caption("You must download a backup first to unlock deletion.")
        if "site_ul" not in st.session_state:
            st.session_state["site_ul"] = False

        def unlk():
            st.session_state["site_ul"] = True

        st.download_button(
            "🔓 Download Backup to Unlock Delete",
            data=json.dumps({"sites": fetch_data("sites").to_dict("records")}, default=str),
            file_name="site_backup.json",
            on_click=unlk,
            help="Downloads a backup of all sites. Once downloaded, the delete option will unlock."
        )
        if not sites_df.empty:
            d_site = st.selectbox("Select Site to Delete", sites_df["name"].unique())
            if st.button("🗑️ Delete Site", disabled=not st.session_state["site_ul"], type="primary"):
                supabase.table("sites").delete().eq("name", d_site).execute()
                st.success(f"✅ Site '{d_site}' deleted.")
                st.session_state["site_ul"] = False
                st.rerun()
            if not st.session_state["site_ul"]:
                st.caption("⬆️ Download the backup above to enable the delete button.")

elif current_tab == "👷 Contractors":
    page_header("👷 Contractors", "Manage contractor rates and active status")
    df_c = fetch_data("contractors")

    display_cols = ["name", "rate_mason", "rate_helper", "rate_ladies", "effective_date"]
    if "status" in df_c.columns:
        display_cols.append("status")

    if not df_c.empty:
        st.dataframe(
            df_c.sort_values(by=["name", "effective_date"], ascending=[True, False])[display_cols].rename(
                columns={"name": "Contractor", "rate_mason": "Mason Rate (₹)", "rate_helper": "Helper Rate (₹)",
                         "rate_ladies": "Ladies Rate (₹)", "effective_date": "Effective From", "status": "Status"}
            ),
            use_container_width=True, hide_index=True
        )
    else:
        empty_state("👷", "No contractors yet", "Add your first contractor using the form below.")

    st.divider()
    act = st.radio("What would you like to do?", ["Add New Contractor", "Update Existing Rate", "Activate/Deactivate"],
                   horizontal=True, help="Choose an action to manage contractor details.")

    with st.form("c_form"):
        if act == "Activate/Deactivate":
            st.markdown("#### 🔄 Change Contractor Status")
            st.caption("Active contractors appear in the Daily Entry form. Inactive ones are hidden.")
            cn = st.selectbox("Select Contractor", df_c["name"].unique()) if not df_c.empty else None
            curr_status = "Active"
            if cn and "status" in df_c.columns:
                curr_status = df_c[df_c["name"] == cn].iloc[0].get("status", "Active")
            st.write(f"Current Status: **{curr_status}**")
            new_stat = st.selectbox("Set New Status", ["Active", "Inactive"],
                                    index=0 if curr_status == "Active" else 1,
                                    help="Setting to Inactive hides this contractor from the Daily Entry form.")
            if st.form_submit_button("✅ Update Status"):
                if cn:
                    supabase.table("contractors").update({"status": new_stat}).eq("name", cn).execute()
                    st.success(f"✅ {cn} is now **{new_stat}**.")
                    st.rerun()
        else:
            if act == "Add New Contractor":
                st.markdown("#### ➕ Add New Contractor")
                st.caption("Enter the contractor's name and their daily worker rates.")
                cn = st.text_input("Contractor Name", placeholder="e.g. Ram Singh & Co")
            else:
                st.markdown("#### ✏️ Update Contractor Rate")
                st.caption("This adds a new rate entry. The old rate is preserved for historical bills.")
                cn = st.selectbox("Select Contractor", df_c["name"].unique()) if not df_c.empty else st.text_input("Contractor Name")

            c1, c2, c3 = st.columns(3)
            rm = c1.number_input("Mason Rate (₹/shift)", value=0, min_value=0, help="Daily rate per mason worker.")
            rh = c2.number_input("Helper Rate (₹/shift)", value=0, min_value=0, help="Daily rate per helper worker.")
            rl = c3.number_input("Ladies Rate (₹/shift)", value=0, min_value=0, help="Daily rate per ladies worker.")
            ed = st.date_input("Effective From", date.today(), format="DD-MM-YYYY",
                               help="The date from which this rate applies. All bills from this date onward will use this rate.")

            if st.form_submit_button("💾 Save Rate"):
                insert_status = "Active"
                if act == "Update Existing Rate" and "status" in df_c.columns and cn:
                    insert_status = df_c[df_c["name"] == cn].iloc[0].get("status", "Active")

                data_to_insert = {
                    "name": cn, "rate_mason": rm, "rate_helper": rh, "rate_ladies": rl, "effective_date": str(ed)
                }
                if "status" in df_c.columns:
                    data_to_insert["status"] = insert_status

                supabase.table("contractors").insert(data_to_insert).execute()
                st.success(f"✅ Rate saved for **{cn}** effective from {ed.strftime('%d %b %Y')}.")
                st.rerun()

elif current_tab == "👥 Users":
    page_header("👥 Users", "Add, update, or deactivate team members")
    users_df = fetch_data("users")
    if not users_df.empty:
        st.dataframe(users_df, use_container_width=True, hide_index=True)
    else:
        empty_state("👥", "No users yet", "Add your first team member using the form below.")

    st.divider()
    st.markdown("### ➕ Add or Update a User")
    st.caption("If the mobile number already exists, the user's details will be updated. Otherwise, a new account is created.")
    with st.form("u_add"):
        c_u1, c_u2 = st.columns(2)
        ph = c_u1.text_input("📱 Mobile Number (Unique ID)", max_chars=10, placeholder="10-digit number")
        nm = c_u2.text_input("👤 Full Name", placeholder="e.g. Ravi Kumar")
        c_u3, c_u4 = st.columns(2)
        rl = c_u3.selectbox("🎭 Role", ["user", "designer", "admin"],
                            help="'user' = field supervisor (labour entry). 'designer' = interior designer (client materials only). 'admin' = full access.")
        all_sites = fetch_data("sites")["name"].tolist()
        asites = c_u4.multiselect("🏗️ Assigned Sites", all_sites,
                                  help="Select sites this user can access. Leave blank to allow all sites.")
        mpin = st.text_input("🔒 4-Digit PIN", max_chars=4, value="1234",
                             help="The PIN this user will use to log in. Default is 1234.")

        if st.form_submit_button("💾 Save User"):
            if not ph.strip() or not nm.strip():
                st.error("⚠️ Mobile number and name are required.")
            elif len(ph) != 10 or not ph.isdigit():
                st.error("⚠️ Mobile number must be exactly 10 digits.")
            elif len(mpin) != 4 or not mpin.isdigit():
                st.error("⚠️ PIN must be exactly 4 digits.")
            else:
                site_str = ", ".join(asites) if asites else "None/All"
                if supabase.table("users").select("*").eq("phone", ph).execute().data:
                    supabase.table("users").update({"name": nm, "role": rl, "assigned_site": site_str, "mpin": mpin}).eq("phone", ph).execute()
                    st.success(f"✅ User '{nm}' updated successfully.")
                else:
                    supabase.table("users").insert({"phone": ph, "name": nm, "role": rl, "assigned_site": site_str, "status": "Active", "mpin": mpin}).execute()
                    st.success(f"✅ New user '{nm}' created. They can now log in with their mobile number and PIN.")
                st.rerun()

    st.divider()
    st.markdown("### 🚪 Deactivate a User")
    st.caption("Deactivating a user prevents them from logging in. Their data is not deleted.")
    if not users_df.empty:
        active = users_df[(users_df["role"] != "admin")]
        if "status" in active.columns:
            active = active[active["status"] != "Resigned"]
        if not active.empty:
            sel_u = st.selectbox("Select User to Deactivate", [f"{r['name']} ({r['phone']})" for _, r in active.iterrows()])
            deact_pass = st.text_input("🔑 Security Code to Confirm", type="password", key="deact_pass",
                                       placeholder="Enter the admin security code")
            if st.button("⛔ Confirm Deactivation", type="primary"):
                if not deact_pass:
                    st.error("⚠️ Please enter the security code.")
                elif deact_pass == ADMIN_DELETE_CODE:
                    ph_clean = sel_u.split("(")[-1].replace(")", "")
                    supabase.table("users").update({"status": "Resigned"}).eq("phone", ph_clean).execute()
                    st.success(f"✅ User deactivated. They can no longer log in.")
                    st.rerun()
                else:
                    st.error("❌ Wrong security code. No changes were made.")
        else:
            st.info("ℹ️ No active non-admin users to deactivate.")

elif current_tab == "📂 Archive & Recovery":
    page_header("📂 Archive & Recovery", "Backup your data, view old records, or restore from a backup")
    t1, t2, t3 = st.tabs(["🔄 Reset Data", "📜 View Archive", "♻️ Restore Data"])

    with t1:
        st.markdown("### 🔄 Reset Entries")
        st.warning("⚠️ **This permanently deletes all work entries.** Users, sites, contractors, and diary notes are NOT affected. You must download a backup first to unlock this action.")

        if "reset_ul" not in st.session_state:
            st.session_state["reset_ul"] = False

        def ul_res():
            st.session_state["reset_ul"] = True

        bkp = {
            "entries": fetch_data("entries").to_dict("records"),
            "users": fetch_data("users").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records")
        }
        st.download_button("📥 Download Full Backup (JSON)", data=json.dumps(bkp, default=str),
                           file_name="full_backup.json", on_click=ul_res,
                           help="Downloads a complete backup of all your data as a JSON file.")

        if st.session_state["reset_ul"]:
            st.success("✅ Backup downloaded. The reset option is now unlocked below.")
        else:
            st.caption("⬆️ Download the backup above to unlock the reset.")

        st.markdown("---")
        c_del1, c_del2 = st.columns(2)
        conf_txt = c_del1.text_input("Type **DELETE ALL** to confirm", placeholder="DELETE ALL")
        conf_pass = c_del2.text_input("Admin Security Code", type="password", placeholder="Your security code")
        if st.button("🗑️ Clear All Entries", disabled=not st.session_state["reset_ul"], type="primary"):
            if conf_txt == "DELETE ALL" and conf_pass == ADMIN_DELETE_CODE:
                supabase.table("entries").delete().neq("id", 0).execute()
                st.success("✅ All entries have been cleared. Your backup file still contains a copy.")
                st.session_state["reset_ul"] = False
            else:
                st.error("❌ Confirmation text or code is wrong. No data was deleted.")

    with t2:
        st.markdown("### 📜 View Archived Data (Read Only)")
        st.caption("Upload a backup JSON file to browse old data or generate a bill from it. Nothing will be changed in your live database.")
        f_view = st.file_uploader("📁 Upload Backup JSON", type=["json"], key="view_upload")
        if f_view:
            try:
                d = json.load(f_view)
                st.success("✅ File loaded successfully.")
                view_mode = st.radio("What would you like to do?", ["View Raw Data Tables", "Generate Weekly Bill from Archive"])
                if view_mode == "View Raw Data Tables":
                    cat = st.selectbox("Select Category", ["Entries", "Users", "Sites", "Contractors"])
                    k_map = {"Entries": "entries", "Users": "users", "Sites": "sites", "Contractors": "contractors"}
                    if d.get(k_map[cat]):
                        st.dataframe(pd.DataFrame(d[k_map[cat]]), use_container_width=True, hide_index=True)
                    else:
                        st.warning(f"No {cat.lower()} data found in this backup file.")
                elif view_mode == "Generate Weekly Bill from Archive":
                    st.info("ℹ️ Generating a bill from archived data. This does not affect your live data.")
                    if d.get("entries") and d.get("contractors"):
                        ae = pd.DataFrame(d["entries"])
                        ac = pd.DataFrame(d["contractors"])
                        render_weekly_bill(ae, ac)
                    else:
                        st.error("⚠️ This backup file is missing 'entries' or 'contractors' data.")
            except Exception as e:
                st.error(f"⚠️ Error reading file: {e}")

    with t3:
        st.markdown("### ♻️ Restore Data from Backup")
        st.warning("⚠️ Restoring will merge backup data into your live database. Existing records may be overwritten. Use with caution.")
        f = st.file_uploader("📁 Upload Backup JSON to Restore", key="res_up")
        res_pass = st.text_input("🔑 Security Code to Confirm", type="password", placeholder="Enter admin security code")
        if f and st.button("♻️ Start Restore", type="primary"):
            if res_pass == ADMIN_DELETE_CODE:
                d = json.load(f)
                with st.spinner("Restoring your data... please wait"):
                    try:
                        def clean(r):
                            return [{k: v for k, v in x.items() if k != 'id'} for x in r]
                        if d.get("sites"):
                            supabase.table("sites").upsert(clean(d["sites"]), on_conflict="name").execute()
                        if d.get("users"):
                            supabase.table("users").upsert(clean(d["users"]), on_conflict="phone").execute()
                        if d.get("contractors"):
                            supabase.table("contractors").upsert(clean(d["contractors"])).execute()
                        if d.get("entries"):
                            ent = clean(d["entries"])
                            for i in range(0, len(ent), 50):
                                supabase.table("entries").insert(ent[i:i+50]).execute()
                        st.success("✅ Restore complete! All data has been successfully restored.")
                    except Exception as e:
                        st.error(f"⚠️ Error during restore: {e}")
            else:
                st.error("❌ Wrong security code. Restore cancelled. No data was changed.")

# ==============================================================================
# SEARCH RESULTS PAGE (admin only, reached via sidebar search bar)
# ==============================================================================
elif current_tab == "🔎 Search Results":
    query = st.session_state.get("search_query", "").strip()

    page_header("🔎 Search Results", f'Showing results for: "{query}"')

    if not query:
        st.info("ℹ️ Use the search box in the sidebar to search by site name, contractor name, or date (e.g. 15-05-2025 or May 2025).")
        st.stop()

    q_lower = query.lower()

    # ── fetch all entries ──────────────────────────────────────────────────────
    with st.spinner("Searching across all entries..."):
        df_all = fetch_data("entries")

    if df_all.empty:
        empty_state("📋", "No entries in the database yet", "Log some daily entries first.")
        st.stop()

    # ── prepare columns ────────────────────────────────────────────────────────
    df_all["date_dt"] = pd.to_datetime(df_all["date"], errors="coerce")
    df_all = df_all.dropna(subset=["date_dt"])
    df_all["date_fmt"] = df_all["date_dt"].dt.strftime("%d-%m-%Y")           # 15-05-2025
    df_all["month_str"] = df_all["date_dt"].dt.strftime("%B %Y").str.lower() # may 2025
    df_all["site_lower"] = df_all["site"].str.lower()
    df_all["con_lower"]  = df_all["contractor"].str.lower()

    # ── multi-field match ──────────────────────────────────────────────────────
    mask = (
        df_all["site_lower"].str.contains(q_lower, na=False) |
        df_all["con_lower"].str.contains(q_lower, na=False) |
        df_all["date_fmt"].str.contains(q_lower, na=False) |
        df_all["month_str"].str.contains(q_lower, na=False) |
        df_all["date_dt"].dt.year.astype(str).str.contains(q_lower, na=False)
    )
    df_results = df_all[mask].copy().sort_values("date_dt", ascending=False)

    # ── summary bar ───────────────────────────────────────────────────────────
    n = len(df_results)
    if n == 0:
        empty_state(
            "🔍", f'No entries match "{query}"',
            "Try a different spelling, or search by part of a site name, contractor name, or date like '05-2025' or 'May'."
        )
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 Entries found", str(n))
    m2.metric("📍 Sites matched", str(df_results["site"].nunique()))
    m3.metric("👷 Contractors", str(df_results["contractor"].nunique()))
    total_cost = df_results["total_cost"].sum()
    m4.metric("💰 Total Cost", f"₹{total_cost:,.0f}")

    st.divider()

    # ── filter strip ──────────────────────────────────────────────────────────
    st.markdown("#### Refine results")
    fcol1, fcol2, fcol3 = st.columns(3)

    site_opts   = ["All Sites"]   + sorted(df_results["site"].unique().tolist())
    con_opts    = ["All Contractors"] + sorted(df_results["contractor"].unique().tolist())
    sort_opts   = ["Newest first", "Oldest first", "Highest cost first", "Lowest cost first"]

    f_site = fcol1.selectbox("Filter by site",       site_opts,  key="sr_site")
    f_con  = fcol2.selectbox("Filter by contractor", con_opts,   key="sr_con")
    f_sort = fcol3.selectbox("Sort by",              sort_opts,  key="sr_sort")

    df_view = df_results.copy()
    if f_site != "All Sites":
        df_view = df_view[df_view["site"] == f_site]
    if f_con != "All Contractors":
        df_view = df_view[df_view["contractor"] == f_con]

    sort_map = {
        "Newest first":       ("date_dt",    False),
        "Oldest first":       ("date_dt",    True),
        "Highest cost first": ("total_cost", False),
        "Lowest cost first":  ("total_cost", True),
    }
    scol, sasc = sort_map[f_sort]
    df_view = df_view.sort_values(scol, ascending=sasc)

    st.divider()

    # ── results table ──────────────────────────────────────────────────────────
    if df_view.empty:
        st.warning("No entries match the current filters. Try removing a filter above.")
    else:
        display_cols = {
            "date_fmt":          "Date",
            "site":              "Site",
            "contractor":        "Contractor",
            "count_mason":       "Masons",
            "count_helper":      "Helpers",
            "count_ladies":      "Ladies",
            "total_cost":        "Cost (₹)",
            "work_description":  "Description",
        }
        if "photo_url" in df_view.columns:
            df_view["Photo"] = df_view["photo_url"].apply(lambda x: "📸 Yes" if x else "—")
            display_cols["Photo"] = "Photo"

        df_display = df_view[list(display_cols.keys())].rename(columns=display_cols)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # CSV export of the current filtered results
        csv_bytes = df_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Export these results (CSV)",
            data=csv_bytes,
            file_name=f"search_{query.replace(' ', '_')}.csv",
            mime="text/csv",
            help="Download the currently filtered search results as a CSV file."
        )

    st.divider()

    # ── grouped breakdown ─────────────────────────────────────────────────────
    if not df_view.empty:
        st.markdown("#### Breakdown")
        bcol1, bcol2 = st.columns(2)

        with bcol1:
            st.markdown("**By site**")
            by_site = (
                df_view.groupby("site")
                .agg(entries=("id", "count"), cost=("total_cost", "sum"))
                .reset_index()
                .rename(columns={"site": "Site", "entries": "Entries", "cost": "Cost (₹)"})
                .sort_values("Cost (₹)", ascending=False)
            )
            by_site["Cost (₹)"] = by_site["Cost (₹)"].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(by_site, use_container_width=True, hide_index=True)

        with bcol2:
            st.markdown("**By contractor**")
            by_con = (
                df_view.groupby("contractor")
                .agg(entries=("id", "count"), cost=("total_cost", "sum"))
                .reset_index()
                .rename(columns={"contractor": "Contractor", "entries": "Entries", "cost": "Cost (₹)"})
                .sort_values("Cost (₹)", ascending=False)
            )
            by_con["Cost (₹)"] = by_con["Cost (₹)"].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(by_con, use_container_width=True, hide_index=True)

    # ── back / new search nudge ───────────────────────────────────────────────
    st.divider()
    st.caption("💡 Use the search box in the sidebar to run a new search, or click any navigation tab to go back.")