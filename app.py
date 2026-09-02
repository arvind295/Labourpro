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
import warnings

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
# A no-op stand-in so that if the real CookieManager component fails to
# initialize (frontend asset mismatch, blocked iframe in some deployment
# sandboxes, etc.) the WHOLE APP doesn't crash on every load. Without this,
# a single failed component mount here would hang the page on "Connecting..."
# forever since the script errors out before Streamlit can render anything.
class _DummyCookieManager:
    def get_all(self, *a, **kw): return {}
    def get(self, *a, **kw): return None
    def set(self, *a, **kw): pass
    def delete(self, *a, **kw): pass

try:
    cookie_manager = stx.CookieManager(key="cookie_manager_main")
except Exception:
    cookie_manager = _DummyCookieManager()

# The CookieManager component re-renders a hidden iframe every time .get() is
# called, and calling it repeatedly in the same script run (once per field we
# wanted to restore) was causing rendering glitches / reruns. Instead we read
# every cookie ONCE per run into a session_state cache, and only touch the
# real component again when we actually need to write or delete a cookie.
def _load_cookies():
    if st.session_state.get("_cookies_cache") is None:
        try:
            st.session_state["_cookies_cache"] = cookie_manager.get_all() or {}
        except Exception:
            st.session_state["_cookies_cache"] = {}
    return st.session_state["_cookies_cache"]

def _cookie_get(name):
    return _load_cookies().get(name)

def _cookie_set(name, value, **kwargs):
    try:
        cookie_manager.set(name, value, key=f"set_{name}_{uuid.uuid4().hex[:8]}", **kwargs)
    except Exception:
        pass
    st.session_state.setdefault("_cookies_cache", {})[name] = value

def _cookie_delete(name):
    try:
        cookie_manager.delete(name, key=f"del_{name}_{uuid.uuid4().hex[:8]}")
    except Exception:
        pass
    if st.session_state.get("_cookies_cache"):
        st.session_state["_cookies_cache"].pop(name, None)

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
            color: #FFFFFF !important;
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

# --- TDS (Section 194C / 393(1)) HELPERS ---
TDS_ENTITY_OPTIONS = ["Individual / HUF", "Company / Firm / Other"]

def get_financial_year(d):
    """Indian FY runs 1 Apr - 31 Mar. Returns e.g. '2026-27' for any date in that window."""
    if isinstance(d, str):
        d = pd.to_datetime(d).date()
    elif isinstance(d, datetime):
        d = d.date()
    if d.month >= 4:
        return f"{d.year}-{str(d.year + 1)[-2:]}"
    return f"{d.year - 1}-{str(d.year)[-2:]}"

def current_financial_year():
    return get_financial_year(date.today())

def list_financial_years(back=3, fwd=0):
    """A handful of FY labels around today, most recent first, for a selectbox."""
    cy = date.today().year if date.today().month >= 4 else date.today().year - 1
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(cy + fwd, cy - back - 1, -1)]

def tds_rate_for(pan_number, entity_type):
    """Returns (rate, human-readable reason) per Sec 194C / 393(1)."""
    if not pan_number or not str(pan_number).strip():
        return 0.20, "No PAN on file — flat 20%"
    if entity_type == "Individual / HUF":
        return 0.01, "Individual/HUF — 1%"
    return 0.02, "Company/Firm/Other — 2%"

def latest_contractor_profile(df_contractors, contractor_name, df_tds_only=None):
    """Most recent PAN/entity_type on file for a contractor. Checks the labour
    contractors table first (rate-history rows, latest by effective_date), then
    falls back to the TDS-only contractors table for people who don't do daily
    labour but still need TDS tracked."""
    pan, entity = "", "Individual / HUF"
    if df_contractors is not None and not df_contractors.empty and "name" in df_contractors.columns:
        crows = df_contractors[df_contractors["name"] == contractor_name]
        if not crows.empty:
            if "effective_date" in crows.columns:
                crows = crows.copy()
                crows["effective_date"] = pd.to_datetime(crows["effective_date"], errors="coerce")
                crows = crows.sort_values("effective_date", ascending=False)
            latest = crows.iloc[0]
            pan = (latest.get("pan_number") or "").strip() if "pan_number" in crows.columns else ""
            entity = latest.get("entity_type") or "Individual / HUF" if "entity_type" in crows.columns else "Individual / HUF"
            if pan or entity != "Individual / HUF":
                return pan, entity

    if df_tds_only is not None and not df_tds_only.empty and "name" in df_tds_only.columns:
        trows = df_tds_only[df_tds_only["name"] == contractor_name]
        if not trows.empty:
            latest = trows.iloc[0]
            pan = (latest.get("pan_number") or "").strip()
            entity = latest.get("entity_type") or "Individual / HUF"

    return pan, entity

def compute_tds_ledger(df_txn, df_tds_only):
    """Per-transaction TDS ledger. Walks each contractor's payments in date
    order within each financial year and works out the TDS owed on EACH
    transaction individually: the transaction that first crosses the ₹30,000
    single-payment or ₹1,00,000 aggregate threshold pulls the FULL cumulative
    amount into TDS, and every transaction after that is taxed on just its own
    amount — so summing 'TDS Deducted' across any date range gives the correct
    TDS for that period without double-counting.

    IMPORTANT — the amount logged for each payment is the NET amount actually
    paid to the contractor (what left your bank account). TDS is NOT deducted
    on top of it; instead the payment is grossed UP:
        Gross = Net / (1 - rate)      TDS = Gross - Net
    e.g. pay ₹1,00,000 net at 1% → Gross ₹1,01,010.10, TDS ₹1,010.10 —
    the contractor still receives exactly ₹1,00,000. The single-payment
    ₹30,000 threshold is tested against the NET amount you actually paid
    (a payment of exactly ₹30,000 does NOT trigger TDS on its own; ₹30,001
    does). The ₹1,00,000 aggregate threshold is still tested against the
    running GROSS total for the FY, since that is the sum credited/paid
    for 194C purposes."""
    if df_txn is None or df_txn.empty:
        return pd.DataFrame()

    df = df_txn.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"]).dt.date
    df["fy"] = df["txn_date"].apply(get_financial_year)
    df = df.sort_values(["contractor_name", "fy", "txn_date"])

    ledger_rows = []
    for (cname, fy), grp in df.groupby(["contractor_name", "fy"]):
        pan, entity = latest_contractor_profile(None, cname, df_tds_only)
        rate, rate_label = tds_rate_for(pan, entity)
        cumulative_gross = 0.0
        liable = False
        for _, r in grp.iterrows():
            net_amount = float(r["amount"])
            gross_amount = net_amount / (1 - rate) if rate < 1 else net_amount
            liability_before = (cumulative_gross * rate) if liable else 0.0
            cumulative_gross += gross_amount
            if net_amount > 30000 or cumulative_gross > 100000:
                liable = True
            liability_after = (cumulative_gross * rate) if liable else 0.0
            tds_this_txn = round(liability_after - liability_before, 2)
            ledger_rows.append({
                "id": r.get("id"),
                "Contractor": cname,
                "PAN": pan if pan else "— missing —",
                "Category": rate_label,
                "Date": r["txn_date"],
                "FY": fy,
                "Amount Paid (Net)": net_amount,
                "Gross Value": round(gross_amount, 2),
                "Cumulative FY Total (Gross)": round(cumulative_gross, 2),
                "TDS Deducted": tds_this_txn,
            })
    return pd.DataFrame(ledger_rows)

def compute_tds_summary(df_txn, df_deductions, fy_label, df_tds_only=None):
    """Per-contractor TDS position for one financial year, built from the ledger.
    'Payable Now' nets off whatever has already been deposited and logged for
    that contractor+FY so the same rupee is never shown twice."""
    ledger = compute_tds_ledger(df_txn, df_tds_only)
    if ledger.empty:
        return pd.DataFrame()

    df_fy = ledger[ledger["FY"] == fy_label]
    if df_fy.empty:
        return pd.DataFrame()

    rows = []
    for cname, grp in df_fy.groupby("Contractor"):
        total_paid = float(grp["Amount Paid (Net)"].sum())
        total_gross = round(float(grp["Gross Value"].sum()), 2)
        tds_liability = round(float(grp["TDS Deducted"].sum()), 2)
        threshold_crossed = tds_liability > 0

        already_deposited = 0.0
        if df_deductions is not None and not df_deductions.empty:
            dgrp = df_deductions[
                (df_deductions["contractor_name"] == cname) & (df_deductions["financial_year"] == fy_label)
            ]
            already_deposited = float(dgrp["amount"].sum())

        payable_now = round(max(tds_liability - already_deposited, 0.0), 2)

        rows.append({
            "Contractor": cname,
            "PAN": grp["PAN"].iloc[0],
            "Category": grp["Category"].iloc[0],
            "Total Paid Net (FY)": total_paid,
            "Gross Value (FY)": total_gross,
            "Threshold Crossed": "✅ Yes" if threshold_crossed else "No",
            "TDS Liability (FY)": tds_liability,
            "Already Deposited": already_deposited,
            "Payable Now": payable_now,
            "_last_txn_date": grp["Date"].max(),
        })
    return pd.DataFrame(rows)

def compute_tds_period_report(df_txn, df_tds_only, df_deductions, start_date, end_date):
    """Per-contractor TDS totals for an arbitrary custom/monthly/quarterly date
    range, using the same ledger so numbers always tie back to the FY summary."""
    ledger = compute_tds_ledger(df_txn, df_tds_only)
    if ledger.empty:
        return pd.DataFrame()

    mask = (ledger["Date"] >= start_date) & (ledger["Date"] <= end_date)
    df_period = ledger.loc[mask]
    if df_period.empty:
        return pd.DataFrame()

    rows = []
    for cname, grp in df_period.groupby("Contractor"):
        total_paid = float(grp["Amount Paid (Net)"].sum())
        total_gross = round(float(grp["Gross Value"].sum()), 2)
        tds_amount = round(float(grp["TDS Deducted"].sum()), 2)

        deposited_in_period = 0.0
        if df_deductions is not None and not df_deductions.empty and "deposited_date" in df_deductions.columns:
            dep = df_deductions.copy()
            dep["deposited_date"] = pd.to_datetime(dep["deposited_date"], errors="coerce").dt.date
            dgrp = dep[
                (dep["contractor_name"] == cname) & (dep["deposited_date"] >= start_date) & (dep["deposited_date"] <= end_date)
            ]
            deposited_in_period = float(dgrp["amount"].sum())

        rows.append({
            "Contractor": cname,
            "PAN": grp["PAN"].iloc[0],
            "Category": grp["Category"].iloc[0],
            "Payments Count": int(len(grp)),
            "Total Paid (Net)": total_paid,
            "Gross Value": total_gross,
            "TDS for Period": tds_amount,
            "Deposited in Period": deposited_in_period,
        })
    return pd.DataFrame(rows).sort_values("Contractor")


# --- TDS BULK IMPORT (EXCEL/CSV) HELPERS ---
# Lets the user upload a bank/expense sheet that mixes Labour payments in with
# lots of other stuff (materials, rent, salaries...), pick out just the Labour
# rows, and turn them into tds_transactions rows without typing each one in by hand.
#
# The whole import flow is designed to work like importing a bank statement into
# Tally: upload the file, and everything else (header row, which column is the
# contractor/amount/date, which rows are Labour) is auto-detected by looking at
# the actual cell values. Advanced controls are still there for when a guess is
# wrong, but nobody should need them for a normal file.

def _guess_column(columns, keywords):
    """Best-effort guess of which column matches a list of keywords (case-insensitive
    substring match). Used only to pre-select a sensible default in a selectbox —
    the user can always override it, so a wrong guess here is harmless."""
    cols = list(columns)
    for kw in keywords:
        for c in cols:
            if kw in str(c).strip().lower():
                return c
    return cols[0] if cols else None

def parse_amount_value(val):
    """Turns a messy spreadsheet amount cell ('₹1,20,000', 'Rs. 45,000.50', 45000,
    '(5000)') into a float. Returns None if it can't be read as a number."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    s = s.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
    neg = s.startswith("(") and s.endswith(")")  # accounting-style negative, e.g. "(5000)"
    if neg:
        s = s[1:-1]
    try:
        num = float(s)
        return -num if neg else num
    except ValueError:
        return None

def parse_date_value(val):
    """Turns a spreadsheet date cell — an Excel date, or a DD-MM-YYYY / DD/MM/YYYY /
    '01-Apr-2026' style string — into a plain date object. Returns None if unreadable."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(val, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None

def find_duplicate_mask(df_new, df_existing):
    """Flags rows in df_new (columns: Contractor, Amount, Date) that already exist
    in the live tds_transactions table, so re-uploading the same sheet twice (or a
    sheet that overlaps a previous one) doesn't silently double-log payments."""
    if df_existing is None or df_existing.empty or "contractor_name" not in df_existing.columns:
        return pd.Series([False] * len(df_new), index=df_new.index)
    existing = df_existing.copy()
    existing["_amt"] = pd.to_numeric(existing["amount"], errors="coerce").round(2)
    existing["_date"] = pd.to_datetime(existing["txn_date"], errors="coerce").dt.date
    existing["_name"] = existing["contractor_name"].astype(str).str.strip().str.lower()
    existing_keys = set(zip(existing["_name"], existing["_date"], existing["_amt"]))

    def _is_dup(row):
        key = (str(row["Contractor"]).strip().lower(), row["Date"], round(float(row["Amount"]), 2))
        return key in existing_keys

    return df_new.apply(_is_dup, axis=1)

def _looks_like_date_cell(v):
    """True date cells (from Excel) or clearly date-formatted strings only — a bare
    number is NEVER treated as a date here. Without this guard, a plain rupee
    amount like 45000 gets misread as a valid date by pandas (it's a legal
    nanosecond timestamp), which would wrongly flag the Amount column as the
    Date column."""
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return True
    if isinstance(v, (int, float)):
        return False
    s = str(v).strip()
    if not s or s.replace(".", "", 1).replace(",", "").replace("-", "").isdigit():
        return False
    return parse_date_value(s) is not None

def _column_date_score(series):
    """Fraction of a column's cells that look like a genuine date. Used to find the
    date column by what's actually in it, not just by its header text."""
    sample = series.dropna().head(50)
    if sample.empty:
        return 0.0
    ok = sum(1 for v in sample if _looks_like_date_cell(v))
    return ok / len(sample)

def _column_amount_score(series):
    """Fraction of a column's cells that parse as a rupee amount."""
    sample = series.dropna().head(50)
    if sample.empty:
        return 0.0
    ok = sum(1 for v in sample if parse_amount_value(v) is not None)
    return ok / len(sample)

def _column_text_score(series):
    """Fraction of a column's cells that look like a name/description (not blank,
    not a bare number) — used to find the contractor/party column."""
    sample = series.dropna().astype(str).str.strip()
    sample = sample[sample != ""].head(50)
    if sample.empty:
        return 0.0
    def _is_texty(v):
        bare = v.replace(".", "", 1).replace(",", "").replace("-", "").strip()
        return len(v) > 1 and not bare.isdigit()
    ok = sum(1 for v in sample if _is_texty(v))
    return ok / len(sample)

def auto_detect_columns(df):
    """Looks at the ACTUAL cell values (not just header names) to guess which column
    is the date, which is the amount, and which is the contractor/party name — so a
    bank statement, a Tally export, or a random expense sheet all work without the
    user having to tell us which column is which. Header text is only used as a
    tie-breaker. Returns (name_col, amount_col, date_col); any can be None if the
    sheet has no columns at all."""
    cols = list(df.columns)
    if not cols:
        return None, None, None

    date_scores = {c: _column_date_score(df[c]) for c in cols}
    amt_scores = {c: _column_amount_score(df[c]) for c in cols}
    text_scores = {c: _column_text_score(df[c]) for c in cols}

    date_col = max(cols, key=lambda c: date_scores[c])
    if date_scores[date_col] < 0.5:
        kw_guess = _guess_column(cols, ["date"])
        if kw_guess is not None:
            date_col = kw_guess

    remaining = [c for c in cols if c != date_col]

    def _amt_key(c):
        low = str(c).lower()
        header_bonus = 0
        for kw, bonus in [("debit", 3), ("withdrawal", 3), ("paid", 2), ("amount", 2), ("amt", 1)]:
            if kw in low:
                header_bonus = max(header_bonus, bonus)
        return (round(amt_scores.get(c, 0.0), 2), header_bonus)

    amt_col = max(remaining, key=_amt_key) if remaining else None
    if amt_col is not None and amt_scores.get(amt_col, 0.0) < 0.3:
        kw_guess = _guess_column(cols, ["amount", "debit", "withdrawal", "paid", "amt"])
        if kw_guess in cols:
            amt_col = kw_guess

    remaining2 = [c for c in remaining if c != amt_col]

    def _name_key(c):
        low = str(c).lower()
        header_bonus = 0
        for kw, bonus in [("contractor", 3), ("party", 3), ("paid to", 3), ("payee", 3),
                           ("vendor", 2), ("name", 2), ("narration", 1), ("particular", 1),
                           ("description", 1)]:
            if kw in low:
                header_bonus = max(header_bonus, bonus)
        return (round(text_scores.get(c, 0.0), 2), header_bonus)

    if remaining2:
        name_col = max(remaining2, key=_name_key)
    elif remaining:
        name_col = remaining[0]
    else:
        name_col = cols[0]

    return name_col, amt_col, date_col

def auto_detect_category_filter(df, exclude_cols):
    """If the sheet has a column that looks like it separates Labour payments from
    other expense types (materials, rent, salaries...), find it by looking for a
    column with a manageable number of repeated values where at least one value
    contains 'labour'/'labor'. Returns (category_col, labour_values) — or
    (None, []) if no such column is found, in which case every row is treated as
    a payment to import (no filtering step needed)."""
    candidates = [c for c in df.columns if c not in exclude_cols]
    n_rows = max(len(df), 1)
    best_col = None
    for c in candidates:
        vals = df[c].dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        if vals.empty:
            continue
        nunique = vals.nunique()
        if 1 < nunique <= max(15, int(n_rows * 0.5)):
            if any(("labour" in v.lower() or "labor" in v.lower()) for v in vals.unique()):
                best_col = c
                break
    if best_col is None:
        kw_guess = _guess_column(
            candidates, ["category", "type", "particular", "head", "narration", "description", "remark", "purpose"]
        ) if candidates else None
        if kw_guess is not None:
            vals = df[kw_guess].dropna().astype(str).str.strip()
            if any(("labour" in v.lower() or "labor" in v.lower()) for v in vals.unique()):
                best_col = kw_guess
    if best_col is None:
        return None, []
    uniq_vals = sorted([v for v in df[best_col].dropna().astype(str).str.strip().unique() if v], key=str.lower)
    labour_vals = [v for v in uniq_vals if "labour" in v.lower() or "labor" in v.lower()]
    return best_col, labour_vals

def _score_header_candidate(df):
    """Scores how 'clean' a parsed table looks, so we can automatically pick how
    many title/blank rows to skip above the real header — the way Tally exports
    often have a company name and report title sitting above the actual table."""
    if df is None or df.empty:
        return -1
    cols = list(df.columns)
    unnamed = sum(1 for c in cols if str(c).startswith("Unnamed:") or str(c).strip() == "")
    score = -unnamed * 2
    _, amt_col, date_col = auto_detect_columns(df.head(30))
    if date_col is not None:
        score += 3
    if amt_col is not None:
        score += 3
    score += min(len(df), 5)
    return score

def smart_read_table(up_file, sheet_name=None, forced_skip_rows=None):
    """Reads an uploaded Excel/CSV file and automatically figures out how many
    header/title rows to skip by trying a handful of options and keeping whichever
    gives the cleanest-looking table (fewest 'Unnamed' columns, a recognisable
    amount + date column). This is what makes 'just upload the file' work for
    Tally exports and bank statements without asking the user anything first.
    Returns (df, skip_rows_used, sheet_names, chosen_sheet)."""
    is_csv = up_file.name.lower().endswith(".csv")
    sheet_names = []
    xls = None
    if not is_csv:
        up_file.seek(0)
        xls = pd.ExcelFile(up_file)
        sheet_names = xls.sheet_names
        chosen_sheet = sheet_name or sheet_names[0]
    else:
        chosen_sheet = None

    candidates = [int(forced_skip_rows)] if forced_skip_rows is not None else list(range(0, 6))

    best_df, best_skip, best_score = None, candidates[0], None
    for sr in candidates:
        try:
            if is_csv:
                up_file.seek(0)
                df = pd.read_csv(up_file, skiprows=sr)
            else:
                df = pd.read_excel(xls, sheet_name=chosen_sheet, skiprows=sr)
            df = df.dropna(how="all").dropna(axis=1, how="all")
            df.columns = [str(c).strip() for c in df.columns]
        except Exception:
            df = None
        sc = _score_header_candidate(df)
        if best_score is None or sc > best_score:
            best_df, best_skip, best_score = df, sr, sc

    return best_df, best_skip, sheet_names, chosen_sheet

# --- PDF ENGINE FOR TDS REPORTS ---
class TDSReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'TDS Payment Report', 0, 1, 'C')
        self.ln(2)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_tds_report_pdf(period_label, df_report):
    pdf = TDSReportPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, _pdf_safe(f"Period: {period_label}"), 0, 1, 'L')
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 6, _pdf_safe(f"Generated: {date.today().strftime('%d %b %Y')}"), 0, 1, 'L')
    pdf.ln(4)

    pdf.set_font("Arial", 'B', 8)
    pdf.set_fill_color(230, 230, 230)
    col_widths = [34, 26, 28, 26, 26, 26, 24]
    headers = ["Contractor", "PAN", "Category", "Net Paid", "Gross", "TDS Due", "Deposited"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, 1, 0, 'C', fill=True)
    pdf.ln()

    pdf.set_font("Arial", '', 8)
    for _, row in df_report.iterrows():
        pdf.cell(col_widths[0], 8, _pdf_safe(str(row["Contractor"])[:24]), 1)
        pdf.cell(col_widths[1], 8, _pdf_safe(str(row["PAN"])[:14]), 1)
        pdf.cell(col_widths[2], 8, _pdf_safe(str(row["Category"])[:20]), 1)
        pdf.cell(col_widths[3], 8, f"Rs. {row['Total Paid (Net)']:,.0f}", 1, 0, 'R')
        pdf.cell(col_widths[4], 8, f"Rs. {row['Gross Value']:,.0f}", 1, 0, 'R')
        pdf.cell(col_widths[5], 8, f"Rs. {row['TDS for Period']:,.0f}", 1, 0, 'R')
        pdf.cell(col_widths[6], 8, f"Rs. {row['Deposited in Period']:,.0f}", 1, 0, 'R')
        pdf.ln()

    pdf.set_font("Arial", 'B', 9)
    total_paid = df_report["Total Paid (Net)"].sum()
    total_gross = df_report["Gross Value"].sum()
    total_tds = df_report["TDS for Period"].sum()
    total_dep = df_report["Deposited in Period"].sum()
    pdf.cell(sum(col_widths[:3]), 8, "TOTAL", 1, 0, 'R')
    pdf.cell(col_widths[3], 8, f"Rs. {total_paid:,.0f}", 1, 0, 'R')
    pdf.cell(col_widths[4], 8, f"Rs. {total_gross:,.0f}", 1, 0, 'R')
    pdf.cell(col_widths[5], 8, f"Rs. {total_tds:,.0f}", 1, 0, 'R')
    pdf.cell(col_widths[6], 8, f"Rs. {total_dep:,.0f}", 1, 0, 'R')
    return pdf.output(dest='S').encode('latin-1')

def generate_tds_report_excel(period_label, df_report):
    buf = io.BytesIO()
    export_df = df_report.rename(columns={
        "TDS for Period": "TDS Due", "Deposited in Period": "Deposited"
    })
    total_row = pd.DataFrame([{
        "Contractor": "TOTAL", "PAN": "", "Category": "", "Payments Count": export_df["Payments Count"].sum(),
        "Total Paid (Net)": export_df["Total Paid (Net)"].sum(), "Gross Value": export_df["Gross Value"].sum(),
        "TDS Due": export_df["TDS Due"].sum(), "Deposited": export_df["Deposited"].sum(),
    }])
    export_df = pd.concat([export_df, total_row], ignore_index=True)

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="TDS Report", startrow=2)
        ws = writer.sheets["TDS Report"]
        ws["A1"] = "TDS Payment Report"
        ws["A2"] = f"Period: {period_label}"
    buf.seek(0)
    return buf.getvalue()

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

def _pdf_safe(text):
    """Make any string safe for FPDF's Latin-1-only core fonts.
    Swaps common 'smart' characters (curly quotes, em/en-dashes, the ₹ sign,
    ellipsis) for plain ASCII equivalents, then drops anything else that still
    can't be encoded — so a stray emoji or symbol in a site/contractor name
    can never crash PDF generation again."""
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u20b9": "Rs. ",
        "\u00a0": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="replace").decode("latin-1")

def generate_pdf_bytes(header_name, week_label, billing_data):
    pdf = PDFBill()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, _pdf_safe(f"Bill For: {header_name}"), 0, 1, 'L')
    pdf.cell(0, 10, _pdf_safe(f"Week: {week_label}"), 0, 1, 'L')
    pdf.ln(5)
    for item in billing_data:
        pdf.set_fill_color(220, 220, 220)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, _pdf_safe(item['name']), 0, 1, 'L', fill=True)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Date", 1)
        pdf.cell(20, 8, "Mason", 1)
        pdf.cell(20, 8, "Helper", 1)
        pdf.cell(20, 8, "Ladies", 1)
        pdf.ln()
        pdf.set_font("Arial", '', 10)
        for row in item['rows']:
            pdf.cell(30, 8, _pdf_safe(row['Date']), 1)
            pdf.cell(20, 8, _pdf_safe(row['Mason']), 1)
            pdf.cell(20, 8, _pdf_safe(row['Helper']), 1)
            pdf.cell(20, 8, _pdf_safe(row['Ladies']), 1)
            pdf.ln()
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Totals", 1)
        pdf.cell(20, 8, _pdf_safe(item['totals']['m']), 1)
        pdf.cell(20, 8, _pdf_safe(item['totals']['h']), 1)
        pdf.cell(20, 8, _pdf_safe(item['totals']['l']), 1)
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
    pdf.cell(0, 10, _pdf_safe(f"Site: {site_name}"), 0, 1, 'L')
    pdf.cell(0, 10, _pdf_safe(f"Period: {period_label}"), 0, 1, 'L')
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
                pdf.cell(25, 8, _pdf_safe(row.get('date', '')), 1)
                vendor = _pdf_safe(str(row.get('vendor', ''))[:22])
                material = _pdf_safe(str(row.get('material_name', ''))[:40])
                pdf.cell(50, 8, vendor, 1)
                pdf.cell(80, 8, material, 1)
                pdf.cell(15, 8, _pdf_safe(row.get('quantity', '')), 1)
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
        self.cell(0, 15, 'WEEKLY EXPENSE REPORT', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_client_invoice_bytes(site_name, date_range_label, labor_details, df_mats, grand_total):
    pdf = ClientInvoicePDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(100, 8, _pdf_safe(f"Project Site: {site_name}"), 0, 0, 'L')
    pdf.set_font("Arial", '', 11)
    pdf.cell(90, 8, f"Date Generated: {date.today().strftime('%d %b %Y')}", 0, 1, 'R')
    pdf.cell(100, 8, f"Billing Period: {date_range_label}", 0, 1, 'L')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " 1. LABOR EXPENSES", 0, 1, 'L', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_fill_color(236, 240, 241)
    pdf.cell(50, 10, "Labor Type", 1, 0, 'C', fill=True)
    pdf.cell(45, 10, "Total Shifts", 1, 0, 'C', fill=True)
    pdf.cell(45, 10, "Rate (Rs)", 1, 0, 'C', fill=True)
    pdf.cell(50, 10, "Amount (Rs)", 1, 1, 'C', fill=True)
    pdf.set_font("Arial", '', 11)
    if labor_details['m_count'] > 0:
        pdf.cell(50, 10, " Masons", 1, 0, 'L')
        pdf.cell(45, 10, f"{labor_details['m_count']}", 1, 0, 'C')
        pdf.cell(45, 10, f"{labor_details['m_rate']:,.2f}", 1, 0, 'C')
        pdf.cell(50, 10, f"{(labor_details['m_count'] * labor_details['m_rate']):,.2f}", 1, 1, 'R')
    if labor_details['h_count'] > 0:
        pdf.cell(50, 10, " Helpers", 1, 0, 'L')
        pdf.cell(45, 10, f"{labor_details['h_count']}", 1, 0, 'C')
        pdf.cell(45, 10, f"{labor_details['h_rate']:,.2f}", 1, 0, 'C')
        pdf.cell(50, 10, f"{(labor_details['h_count'] * labor_details['h_rate']):,.2f}", 1, 1, 'R')
    if labor_details['l_count'] > 0:
        pdf.cell(50, 10, " Ladies", 1, 0, 'L')
        pdf.cell(45, 10, f"{labor_details['l_count']}", 1, 0, 'C')
        pdf.cell(45, 10, f"{labor_details['l_rate']:,.2f}", 1, 0, 'C')
        pdf.cell(50, 10, f"{(labor_details['l_count'] * labor_details['l_rate']):,.2f}", 1, 1, 'R')
    if labor_details['m_count'] == 0 and labor_details['h_count'] == 0 and labor_details['l_count'] == 0:
        pdf.cell(190, 10, "No labor entered for this period.", 1, 1, 'C')
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(140, 10, "Total Labor Cost:", 1, 0, 'R', fill=True)
    pdf.cell(50, 10, f"Rs. {labor_details['total']:,.2f}", 1, 1, 'R', fill=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " 2. MATERIAL EXPENSES", 0, 1, 'L', fill=True)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(236, 240, 241)
    pdf.cell(30, 10, "Date", 1, 0, 'C', fill=True)
    pdf.cell(110, 10, "Material Description", 1, 0, 'C', fill=True)
    pdf.cell(50, 10, "Amount", 1, 1, 'C', fill=True)
    pdf.set_font("Arial", '', 11)
    mat_total = 0
    if not df_mats.empty:
        for _, r in df_mats.iterrows():
            desc = str(r.get("Description", "")).strip()
            if not desc: continue
            m_date = str(r.get("Date", "")).strip()
            try: amt = float(r.get("Amount (Rs)", 0))
            except: amt = 0.0
            mat_total += amt
            pdf.cell(30, 10, _pdf_safe(m_date[:12]), 1, 0, 'C')
            pdf.cell(110, 10, _pdf_safe(f" {desc[:55]}"), 1, 0, 'L')
            pdf.cell(50, 10, f"{amt:,.2f}", 1, 1, 'R')
    else:
        pdf.cell(190, 10, "No materials entered for this period.", 1, 1, 'C')
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(140, 10, "Total Material Cost:", 1, 0, 'R', fill=True)
    pdf.cell(50, 10, f"Rs. {mat_total:,.2f}", 1, 1, 'R', fill=True)
    pdf.ln(15)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_fill_color(46, 204, 113)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 15, " GRAND TOTAL DUE:", 1, 0, 'R', fill=True)
    pdf.cell(50, 15, f"Rs. {grand_total:,.2f}", 1, 1, 'R', fill=True)
    return pdf.output(dest='S').encode('latin-1')

# --- WEEKLY BILL RENDERER ---
def _safe_get_rates(df_contractors, contractor_name, week_start_obj):
    """Safely fetch mason/helper/ladies rates for a contractor on a given week.
    Returns (rm, rh, rl) as floats, defaulting to 0 on any error."""
    try:
        rates = df_contractors[df_contractors["name"] == contractor_name].copy()
        if rates.empty:
            return 0.0, 0.0, 0.0
        # Drop rows where effective_date is NaT / None
        rates = rates.dropna(subset=["effective_date"])
        if rates.empty:
            return 0.0, 0.0, 0.0
        rates = rates.sort_values("effective_date", ascending=False)
        # Only compare dates to dates (both must be datetime.date)
        valid = rates[rates["effective_date"].apply(
            lambda d: d <= week_start_obj if isinstance(d, type(week_start_obj)) else False
        )]
        row = valid.iloc[0] if not valid.empty else rates.iloc[0]
        return float(row["rate_mason"]), float(row["rate_helper"]), float(row["rate_ladies"])
    except Exception:
        return 0.0, 0.0, 0.0


def _build_week_rows(df_sub, full_week_dates, rm, rh, rl):
    """Build the 7-day row list and totals for one contractor+site block."""
    # Build entry_map: date → record. Guard against NaT in date_dt.
    entry_map = {}
    for _, row in df_sub.iterrows():
        dt_val = row.get("date_dt")
        if pd.notna(dt_val):
            try:
                entry_map[dt_val.date()] = row
            except Exception:
                pass

    rows = []
    tm, th, tl, tamt = 0.0, 0.0, 0.0, 0.0
    for day_date in full_week_dates:
        if day_date in entry_map:
            r = entry_map[day_date]
            m = float(r.get("count_mason", 0) or 0)
            h = float(r.get("count_helper", 0) or 0)
            l = float(r.get("count_ladies", 0) or 0)
            daily_cost = (m * rm) + (h * rh) + (l * rl)
            if m == 0 and h == 0 and l == 0:
                dm, dh, dl = "Nil", "Nil", "Nil"
            else:
                dm = str(int(m) if m == int(m) else m)
                dh = str(int(h) if h == int(h) else h)
                dl = str(int(l) if l == int(l) else l)
        else:
            m, h, l, daily_cost = 0.0, 0.0, 0.0, 0.0
            dm, dh, dl = "-", "-", "-"
        rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
        tm += m; th += h; tl += l; tamt += daily_cost

    return rows, tm, th, tl, tamt


def render_weekly_bill(df_entries, df_contractors):
    # ── guard: no data ─────────────────────────────────────────────────────────
    if df_entries.empty:
        empty_state("📊", "No entries yet", "Start by logging daily attendance in the Daily Entry tab.")
        return

    is_admin = (st.session_state["role"] == "admin")

    # ── filter by assigned sites for non-admin users ───────────────────────────
    if not is_admin:
        assigned_raw = st.session_state.get("assigned_site", "")
        if "All" not in assigned_raw and "None/All" not in assigned_raw:
            user_sites = [s.strip() for s in assigned_raw.split(",")]
            df_entries = df_entries[df_entries["site"].isin(user_sites)]
            if df_entries.empty:
                empty_state("🏗️", "No data for your sites", "Your assigned sites have no entries in this period.")
                return

    # ── parse dates ────────────────────────────────────────────────────────────
    df_entries = df_entries.copy()
    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors="coerce")
    df_entries = df_entries.dropna(subset=["date_dt"])
    if df_entries.empty:
        empty_state("📅", "No valid dates found", "Check that your entries have proper dates.")
        return

    # Ensure effective_date in contractors is always datetime.date (not Timestamp/NaT)
    df_contractors = df_contractors.copy()
    df_contractors["effective_date"] = pd.to_datetime(
        df_contractors["effective_date"], errors="coerce"
    ).dt.date

    # ── build week labels ──────────────────────────────────────────────────────
    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["week_label"] = df_entries["start_date"].apply(
        lambda s: f"{s.strftime('%d-%m-%Y')} to {(s + timedelta(days=6)).strftime('%d-%m-%Y')}"
    )

    unique_weeks = (
        df_entries[["start_date", "week_label"]]
        .drop_duplicates()
        .sort_values("start_date", ascending=False)
    )
    weeks = unique_weeks["week_label"].tolist()

    # ── week selector ──────────────────────────────────────────────────────────
    st.markdown("#### 📅 Select a Week to View")
    sel_week = st.selectbox(
        "Billing Week", weeks,
        help="Each week runs Saturday → Friday. Select any week to see the full bill."
    )
    if not sel_week:
        return

    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    week_start_obj = df_week.iloc[0]["start_date"]   # datetime.date
    full_week_dates = [week_start_obj + timedelta(days=i) for i in range(7)]

    if is_admin:
        csv_data = df_week.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📊 Download Week Data (CSV)", csv_data,
            f"Data_{sel_week}.csv", "text/csv",
            help="Download all raw entries for this week as a CSV/Excel file."
        )
        st.divider()

    # ── two view tabs (NO st.stop() inside tabs — use early return guards) ─────
    tab_site, tab_con = st.tabs(["🏢 View by Site", "👷 View by Contractor"])

    # ════════════════════════════════
    # TAB A — View by Site
    # ════════════════════════════════
    with tab_site:
        all_sites = sorted(df_week["site"].dropna().unique().tolist())
        if not all_sites:
            empty_state("🏗️", "No sites found for this week")
        else:
            sel_site = st.pills(
                "Select a Site", all_sites,
                key=f"sb_site_{sel_week}",          # week-scoped key — avoids stale key clash
                default=all_sites[0]
            )
            if sel_site:
                st.divider()
                st.markdown(f"### 📍 {sel_site}")
                df_view = df_week[df_week["site"] == sel_site]
                pdf_data = []

                for con_name in df_view["contractor"].dropna().unique():
                    df_sub = df_view[df_view["contractor"] == con_name]
                    rm, rh, rl = _safe_get_rates(df_contractors, con_name, week_start_obj)
                    rows, tm, th, tl, tamt = _build_week_rows(df_sub, full_week_dates, rm, rh, rl)
                    pdf_data.append({
                        "name": con_name, "rows": rows,
                        "totals": {"m": tm, "h": th, "l": tl, "amt": tamt},
                        "rates": {"rm": rm, "rh": rh, "rl": rl}
                    })

                    st.markdown(f"#### 👷 {con_name}")
                    if rm == 0 and rh == 0 and rl == 0:
                        st.caption("⚠️ No rates found for this contractor — amounts show as ₹0. Add rates in the Contractors tab.")
                    if is_admin:
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("💰 Amount Payable", f"₹{tamt:,.0f}")
                        k2.metric("🧱 Mason Shifts", f"{tm:g}")
                        k3.metric("🛠️ Helper Shifts", f"{th:g}")
                        k4.metric("👩 Ladies Shifts", f"{tl:g}")
                    else:
                        k2, k3, k4 = st.columns(3)
                        k2.metric("🧱 Mason Shifts", f"{tm:g}")
                        k3.metric("🛠️ Helper Shifts", f"{th:g}")
                        k4.metric("👩 Ladies Shifts", f"{tl:g}")

                    with st.expander(f"📄 Day-by-Day: {con_name}"):
                        st.caption("— = no entry submitted. Nil = holiday/no-work entry submitted.")
                        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

                if pdf_data:
                    try:
                        pdf_bytes = generate_pdf_bytes(sel_site, sel_week, pdf_data)
                        st.download_button(
                            f"⬇️ Download PDF Bill — {sel_site}", pdf_bytes,
                            f"Bill_{sel_site}.pdf", "application/pdf",
                            help="Formatted PDF bill for all contractors at this site."
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Could not generate PDF: {e}")

    # ════════════════════════════════
    # TAB B — View by Contractor
    # ════════════════════════════════
    with tab_con:
        all_cons = sorted(df_week["contractor"].dropna().unique().tolist())
        if not all_cons:
            empty_state("👷", "No contractors found for this week")
        else:
            sel_con = st.pills(
                "Select a Contractor", all_cons,
                key=f"sb_con_{sel_week}",           # week-scoped key
                default=all_cons[0]
            )
            if sel_con:
                st.divider()
                st.markdown(f"### 👷 {sel_con}")
                df_view = df_week[df_week["contractor"] == sel_con]
                pdf_data = []

                for site_name in df_view["site"].dropna().unique():
                    df_sub = df_view[df_view["site"] == site_name]
                    rm, rh, rl = _safe_get_rates(df_contractors, sel_con, week_start_obj)
                    rows, tm, th, tl, tamt = _build_week_rows(df_sub, full_week_dates, rm, rh, rl)
                    pdf_data.append({
                        "name": site_name, "rows": rows,
                        "totals": {"m": tm, "h": th, "l": tl, "amt": tamt},
                        "rates": {"rm": rm, "rh": rh, "rl": rl}
                    })

                    st.markdown(f"#### 📍 {site_name}")
                    if rm == 0 and rh == 0 and rl == 0:
                        st.caption("⚠️ No rates found — amounts show as ₹0. Add rates in the Contractors tab.")
                    if is_admin:
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("💰 Amount Payable", f"₹{tamt:,.0f}")
                        k2.metric("🧱 Mason Shifts", f"{tm:g}")
                        k3.metric("🛠️ Helper Shifts", f"{th:g}")
                        k4.metric("👩 Ladies Shifts", f"{tl:g}")
                    else:
                        k2, k3, k4 = st.columns(3)
                        k2.metric("🧱 Mason Shifts", f"{tm:g}")
                        k3.metric("🛠️ Helper Shifts", f"{th:g}")
                        k4.metric("👩 Ladies Shifts", f"{tl:g}")

                    with st.expander(f"📄 Day-by-Day: {site_name}"):
                        st.caption("— = no entry submitted. Nil = holiday/no-work entry submitted.")
                        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

                if pdf_data:
                    try:
                        pdf_bytes = generate_pdf_bytes(sel_con, sel_week, pdf_data)
                        st.download_button(
                            f"⬇️ Download PDF Bill — {sel_con}", pdf_bytes,
                            f"Bill_{sel_con}.pdf", "application/pdf",
                            help="Formatted PDF bill for this contractor across all sites."
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Could not generate PDF: {e}")

# --- 6. AUTO-LOGIN CHECK ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

if "search_query" not in st.session_state:
    st.session_state["search_query"] = ""
if "search_active" not in st.session_state:
    st.session_state["search_active"] = False

stored_token = _cookie_get("auth_token")

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
            # Restore last active tab from cookie (so background-switch reloads land
            # back on the same page the user was on, not always Daily Entry)
            saved_tab = _cookie_get("active_tab")
            if saved_tab:
                st.session_state["_restored_tab"] = saved_tab
        else:
            _cookie_delete("auth_token")
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
                if st.form_submit_button("Login  →", type="primary", width='stretch'):
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
                                    _cookie_set("auth_token", new_token, expires_at=datetime.now() + timedelta(days=30))
                                    st.session_state.update({
                                        "logged_in": True,
                                        "phone": user["phone"],
                                        "role": "user",
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
                if st.form_submit_button("Admin Login", width='stretch'):
                    if pw_a == ADMIN_LOGIN_PASS:
                        try:
                            response = supabase.table("users").select("*").eq("phone", ph_a).execute()
                            if response.data and response.data[0].get("role") == "admin":
                                user = response.data[0]
                                new_token = str(uuid.uuid4())
                                supabase.table("users").update({"session_token": new_token}).eq("phone", ph_a).execute()
                                _cookie_set("auth_token", new_token, expires_at=datetime.now() + timedelta(days=30))
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
tabs = ["📝 Daily Entry", "📊 Weekly Bill", "🧱 Materials", "📓 My Diary"]
if st.session_state["role"] == "admin":
    tabs += ["📈 Dashboard", "🧾 Client Invoice", "💰 TDS Calculator", "📑 Custom Labour Report", "🔍 Site Logs", "📍 Sites", "👷 Contractors", "👥 Users", "📂 Archive & Recovery", "🔎 Search Results"]

if "current_tab" not in st.session_state or st.session_state["current_tab"] not in tabs:
    # If we have a restored tab from cookie (post background-switch reload), use it
    restored = st.session_state.pop("_restored_tab", None)
    if restored and restored in tabs:
        st.session_state["current_tab"] = restored
    else:
        st.session_state["current_tab"] = tabs[0]

with st.sidebar:
    st.markdown("""
        <div style='text-align:center; padding: 1rem 0 0.5rem 0;'>
            <div style='font-size:2rem;'>🏗️</div>
            <div style='font-size:1.2rem; font-weight:700; color:#FFFFFF; letter-spacing:0.05em;'>LabourPro</div>
        </div>
    """, unsafe_allow_html=True)

    role_badge = "🛡️ Admin" if st.session_state["role"] == "admin" else "👷 Field User"
    user_name = st.session_state.get("user_name", "User")
    st.markdown(f"""
        <div style='background:rgba(243,156,18,0.15); border:1px solid rgba(243,156,18,0.3);
                    border-radius:10px; padding:0.75rem 1rem; margin:0.5rem 0 1rem 0;'>
            <div style='font-size:0.75rem; color:#F39C12; font-weight:600; text-transform:uppercase; letter-spacing:0.05em;'>{role_badge}</div>
            <div style='font-size:1rem; font-weight:700; color:#FFFFFF; margin-top:0.1rem;'>{user_name}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- GLOBAL SEARCH (admin only) ---
    if st.session_state["role"] == "admin":
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
            if st.button("Search", width='stretch', key="do_search"):
                if search_input.strip():
                    st.session_state["search_query"] = search_input.strip()
                    st.session_state["search_active"] = True
                    st.session_state["current_tab"] = "🔎 Search Results"
                    st.rerun()
        with col_s2:
            if st.button("✕", width='stretch', key="clear_search", help="Clear search"):
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
        if st.button(tab, key=f"nav_{tab}", width='stretch'):
            st.session_state["current_tab"] = tab
            _cookie_set("active_tab", tab, expires_at=datetime.now() + timedelta(days=30))
            st.rerun()

    # Keep active_tab cookie in sync, but only when it has changed
    # (writing on every render causes a re-render loop on heavy pages like Weekly Bill)
    _cur = st.session_state.get("current_tab", tabs[0])
    if st.session_state.get("_last_saved_tab") != _cur:
        _cookie_set("active_tab", _cur, expires_at=datetime.now() + timedelta(days=30))
        st.session_state["_last_saved_tab"] = _cur

    st.divider()

    # PIN change for regular users
    if st.session_state["role"] == "user":
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

    if st.button("🚪 Logout", width='stretch'):
        if st.session_state.get("phone"):
            try:
                supabase.table("users").update({"session_token": None}).eq("phone", st.session_state["phone"]).execute()
            except:
                pass
        for _ck in ["auth_token", "active_tab", "last_site", "last_contractor"]:
            try:
                _cookie_delete(_ck)
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
        # Restore last-used selections from cookies so a background-switch reload
        # doesn't wipe what the user had selected
        _saved_site = _cookie_get("last_site")
        _saved_con  = _cookie_get("last_contractor")

        st.markdown("""<div class='step-card'><div class='step-label'>Step 1 — Choose Entry Details</div></div>""", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("📅 Date", date.today(), format="DD-MM-YYYY", help="Select the date for this work entry.")

        _site_idx = av_sites.index(_saved_site) if _saved_site and _saved_site in av_sites else None
        st_sel = c2.selectbox("🏗️ Site", av_sites, index=_site_idx, placeholder="Select a site...", help="Choose the construction site.")

        con_sel_options = []
        if not df_con.empty:
            if "status" in df_con.columns:
                active_df = df_con[df_con["status"] != "Inactive"]
                con_sel_options = active_df["name"].unique().tolist()
            else:
                con_sel_options = df_con["name"].unique().tolist()

        _con_idx = con_sel_options.index(_saved_con) if _saved_con and _saved_con in con_sel_options else None
        con_sel = c3.selectbox("👷 Contractor", con_sel_options, index=_con_idx, placeholder="Select a contractor...", help="Choose the contractor whose workers you are logging.")

        # Persist selections to cookies only when value actually changes
        if st_sel and st_sel != _saved_site:
            _cookie_set("last_site", st_sel, expires_at=datetime.now() + timedelta(days=7))
        if con_sel and con_sel != _saved_con:
            _cookie_set("last_contractor", con_sel, expires_at=datetime.now() + timedelta(days=7))

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

            # Declare defaults so Save button never hits NameError regardless of branch
            nm, nh, nl, cost, wdesc, uploaded_photo = 0, 0, 0, 0, "", None

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
            if st.button(btn_label, type="primary", width='stretch'):
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
                }), width='stretch', hide_index=True)
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
        else:
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

                            if st.form_submit_button("💾 Save Material Entry", type="primary", width='stretch'):
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
                                st.dataframe(display_df, width='stretch', hide_index=True)
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
    page_header("🧾 Client Invoice", "Generate a professional expense report to send to your client")
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
            st.info("💡 No sites are marked for client billing. To fix this, go to **Supabase → Table Editor → sites** and tick the **is_client_site** checkbox for the sites you want to invoice.")
        else:
            st.markdown("### Step 1 — Select Site & Date Range")
            c1, c2, c3 = st.columns(3)
            inv_site = c1.selectbox("🏗️ Project Site", client_sites, help="Only sites marked for client billing appear here.")
            inv_start = c2.date_input("📅 From", date.today() - timedelta(days=6), format="DD-MM-YYYY")
            inv_end = c3.date_input("📅 To", date.today(), format="DD-MM-YYYY")

            st.divider()

            st.markdown("### Step 2 — Labour Billing")
            st.caption("Your actual (internal) labour cost is shown below. Enter the rates you want to charge your client to apply a margin.")
            df_entries = fetch_data("entries")
            tot_mason, tot_helper, tot_ladies = 0, 0, 0
            internal_total_labor = 0

            if not df_entries.empty:
                df_entries["date_dt"] = pd.to_datetime(df_entries["date"]).dt.date
                mask = (df_entries["site"] == inv_site) & (df_entries["date_dt"] >= inv_start) & (df_entries["date_dt"] <= inv_end)
                df_e_filtered = df_entries[mask]
                if not df_e_filtered.empty:
                    tot_mason = df_e_filtered["count_mason"].sum()
                    tot_helper = df_e_filtered["count_helper"].sum()
                    tot_ladies = df_e_filtered["count_ladies"].sum()
                    internal_total_labor = df_e_filtered["total_cost"].sum()

            st.info(f"💡 **Your internal labour payout** for this period: **₹{internal_total_labor:,.0f}**  |  Enter your client billing rates below to set what you'll charge the client.")

            c_l1, c_l2, c_l3 = st.columns(3)
            client_rate_mason = c_l1.number_input(f"Client Rate — Mason ({int(tot_mason)} shifts)", value=0.0, step=50.0, help="Rate per shift you're billing the client.")
            client_rate_helper = c_l2.number_input(f"Client Rate — Helper ({int(tot_helper)} shifts)", value=0.0, step=50.0)
            client_rate_ladies = c_l3.number_input(f"Client Rate — Ladies ({int(tot_ladies)} shifts)", value=0.0, step=50.0)

            total_labor = (tot_mason * client_rate_mason) + (tot_helper * client_rate_helper) + (tot_ladies * client_rate_ladies)
            margin = total_labor - internal_total_labor
            st.metric(f"Total Billed Labour — {inv_site}", f"₹{total_labor:,.2f}",
                      delta=f"₹{margin:,.0f} margin" if total_labor > 0 else None,
                      help="This is what you will bill the client for labour.")

            labor_details = {
                'm_count': tot_mason, 'm_rate': client_rate_mason,
                'h_count': tot_helper, 'h_rate': client_rate_helper,
                'l_count': tot_ladies, 'l_rate': client_rate_ladies,
                'total': total_labor
            }

            st.divider()
            st.markdown("### Step 3 — Materials")
            st.caption(f"Showing materials from the database for **{inv_site}** between **{inv_start.strftime('%d %b %Y')}** and **{inv_end.strftime('%d %b %Y')}**.")

            df_materials = fetch_data("materials")
            pdf_mats = pd.DataFrame(columns=["Date", "Description", "Amount (Rs)"])
            total_mat = 0
            df_m_filtered = pd.DataFrame()

            if not df_materials.empty:
                df_materials["date_dt"] = pd.to_datetime(df_materials["date"]).dt.date
                mask_m = (df_materials["site"] == inv_site) & (df_materials["date_dt"] >= inv_start) & (df_materials["date_dt"] <= inv_end)
                df_m_filtered = df_materials[mask_m].copy()
                if not df_m_filtered.empty:
                    df_m_filtered["formatted_date"] = pd.to_datetime(df_m_filtered["date"]).dt.strftime('%d-%m-%Y')
                    df_m_filtered["Description_PDF"] = df_m_filtered["material_name"] + " (" + df_m_filtered["category"] + ")"
                    pdf_mats = df_m_filtered[["formatted_date", "Description_PDF", "amount"]].rename(
                        columns={"formatted_date": "Date", "Description_PDF": "Description", "amount": "Amount (Rs)"})
                    total_mat = pdf_mats["Amount (Rs)"].sum()

            if not pdf_mats.empty:
                # Using st.table instead of st.dataframe here on purpose: st.dataframe
                # serializes through pyarrow (a C++ library) which has been segfaulting
                # on this environment's Python 3.13 build. st.table renders as plain
                # HTML instead, avoiding that native code path entirely.
                st.table(pdf_mats.reset_index(drop=True))
            else:
                st.info("ℹ️ No materials found in the database for this date range. You can add them below.")

            st.metric("Total Material Cost", f"₹{total_mat:,.2f}")

            st.markdown("#### ⚙️ Manage Materials for This Invoice")
            st.caption("Use these tabs to add, edit, or remove materials before generating the PDF.")
            tab_add, tab_edit, tab_del = st.tabs(["➕ Add Material", "✏️ Edit Material", "🗑️ Delete Material"])

            with tab_add:
                with st.form("quick_add_mat_v2"):
                    c_qm1, c_qm2 = st.columns([1, 2])
                    qm_date = c_qm1.date_input("Date of Purchase", inv_end, format="DD-MM-YYYY")
                    qm_desc = c_qm2.text_input("Material Description", placeholder="e.g. Cement (50 Bags)")
                    c_qm3, c_qm4 = st.columns(2)
                    qm_cat = c_qm3.selectbox("Category", ["Civil", "Bill", "Transportation"])
                    qm_amt = c_qm4.number_input("Amount (₹)", min_value=0.0, step=100.0)
                    if st.form_submit_button("💾 Save to Database", type="primary"):
                        if qm_desc.strip():
                            load = {
                                "date": str(qm_date), "site": inv_site, "category": qm_cat,
                                "vendor": "Client Invoice", "material_name": qm_desc.strip(),
                                "quantity": 1, "amount": qm_amt, "receipt_url": ""
                            }
                            supabase.table("materials").insert(load).execute()
                            st.success("✅ Saved! The invoice totals will update automatically.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("⚠️ Please enter a material description.")

            with tab_edit:
                if not df_m_filtered.empty:
                    edit_options = {f"{row['formatted_date']} — {row['material_name']} — ₹{row['amount']}": row for _, row in df_m_filtered.iterrows()}
                    sel_edit_key = st.selectbox("Select entry to edit", list(edit_options.keys()))
                    sel_edit_row = edit_options[sel_edit_key]
                    with st.form("edit_mat_form"):
                        c_e1, c_e2 = st.columns([1, 2])
                        edit_date_obj = pd.to_datetime(sel_edit_row["date"]).date()
                        e_date = c_e1.date_input("Date", edit_date_obj, format="DD-MM-YYYY")
                        e_desc = c_e2.text_input("Description", value=sel_edit_row["material_name"])
                        c_e3, c_e4 = st.columns(2)
                        cat_options = ["Civil", "Bill", "Transportation"]
                        existing_cat = sel_edit_row.get("category", "Civil")
                        cat_idx = cat_options.index(existing_cat) if existing_cat in cat_options else 0
                        e_cat = c_e3.selectbox("Category", cat_options, index=cat_idx)
                        e_amt = c_e4.number_input("Amount (₹)", value=float(sel_edit_row["amount"]), step=100.0)
                        if st.form_submit_button("✅ Update Material", type="primary"):
                            supabase.table("materials").update({
                                "date": str(e_date), "material_name": e_desc, "category": e_cat, "amount": e_amt
                            }).eq("id", int(sel_edit_row["id"])).execute()
                            st.success("✅ Material updated!")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.info("ℹ️ No materials to edit in this date range. Add some using the ➕ tab.")

            with tab_del:
                if not df_m_filtered.empty:
                    del_options = {f"{row['formatted_date']} — {row['material_name']} — ₹{row['amount']}": row['id'] for _, row in df_m_filtered.iterrows()}
                    sel_del = st.selectbox("Select entry to delete", list(del_options.keys()))
                    st.caption("⚠️ Deletion is immediate and cannot be undone.")
                    if st.button("🗑️ Delete Selected Entry", type="primary"):
                        del_id = del_options[sel_del]
                        supabase.table("materials").delete().eq("id", int(del_id)).execute()
                        st.success("✅ Entry deleted.")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.info("ℹ️ No materials to delete in this date range.")

            st.divider()
            grand_total = total_labor + total_mat
            st.markdown(f"## 💰 Grand Total to Bill Client: ₹{grand_total:,.2f}")
            st.caption("This is the sum of billed labour + all materials in the selected period.")

            if st.button("📄 Generate Professional Invoice PDF", type="primary", width='stretch'):
                date_label = f"{inv_start.strftime('%d-%m-%Y')} to {inv_end.strftime('%d-%m-%Y')}"
                with st.spinner("Generating your invoice PDF..."):
                    pdf_bytes = generate_client_invoice_bytes(inv_site, date_label, labor_details, pdf_mats, grand_total)
                # Persist to session_state instead of a local variable: clicking the
                # download button below triggers its own rerun, which would reset
                # st.button("Generate...") back to False and make this whole block
                # (and the download button with it) disappear before the click could
                # register. Session state survives that rerun.
                st.session_state["_client_invoice_pdf_bytes"] = pdf_bytes
                st.session_state["_client_invoice_pdf_name"] = f"Client_Invoice_{inv_site}_{inv_start.strftime('%d%b')}.pdf"

            if st.session_state.get("_client_invoice_pdf_bytes"):
                st.success("✅ Invoice ready to download!")
                st.download_button(
                    label="⬇️ Download Client Invoice (PDF)",
                    data=st.session_state["_client_invoice_pdf_bytes"],
                    file_name=st.session_state["_client_invoice_pdf_name"],
                    mime="application/pdf"
                )

elif current_tab == "💰 TDS Calculator":
    page_header("💰 TDS Calculator", "Log contractor payments made from your bank account and see what TDS is due each month")

    df_txn = fetch_data("tds_transactions")
    df_deductions = fetch_data("tds_deductions")
    df_tds_only = fetch_data("tds_only_contractors")

    tds_only_names = sorted(df_tds_only["name"].unique().tolist()) if not df_tds_only.empty else []

    tab_log, tab_import, tab_payable, tab_only, tab_report, tab_history = st.tabs(
        ["📥 Log Bank Payment", "📤 Bulk Import (Excel)", "📊 TDS Payable", "👤 TDS-Only Contractors", "📄 Download Report", "📜 Payment Log"]
    )

    # ── LOG A BANK PAYMENT ──────────────────────────────────────────────────
    with tab_log:
        st.caption("This is completely separate from your Daily Entry contractors. Only contractors added under 'TDS-Only Contractors' show up here — add them there first, then log payments.")
        if not tds_only_names:
            empty_state("👤", "No TDS contractors yet", "Add one in the 'TDS-Only Contractors' sub-tab first.")
        else:
            with st.form("tds_txn_form"):
                t1, t2 = st.columns(2)
                txn_contractor = t1.selectbox("Contractor", tds_only_names)
                txn_amount = t2.number_input("Amount Paid to Contractor (₹)", min_value=0.0, step=1000.0, format="%.2f",
                                help="The NET amount actually paid to the contractor. TDS is grossed up on top of this: Gross = Paid ÷ (1 − rate), TDS = Gross − Paid.")
                txn_date = st.date_input("Date of Payment", date.today(), format="DD-MM-YYYY")
                if st.form_submit_button("💾 Log Payment", type="primary"):
                    if txn_amount <= 0:
                        st.error("⚠️ Enter an amount greater than zero.")
                    else:
                        try:
                            supabase.table("tds_transactions").insert({
                                "contractor_name": txn_contractor,
                                "amount": txn_amount,
                                "txn_date": str(txn_date),
                            }).execute()
                            st.success(f"✅ Logged ₹{txn_amount:,.2f} paid to **{txn_contractor}** on {txn_date.strftime('%d %b %Y')}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Could not save this payment: {e}")

    # ── BULK IMPORT FROM EXCEL / CSV ─────────────────────────────────────────
    with tab_import:
        st.caption(
            "Upload your bank statement or expense sheet — like importing a bank statement into Tally. "
            "We auto-detect the contractor, amount and date columns and pick out the Labour payments "
            "for you to review before importing. It's fine if materials, rent, salaries etc. are mixed in."
        )

        up_file = st.file_uploader("📁 Upload Excel or CSV", type=["xlsx", "xls", "csv"], key="tds_bulk_upload")

        if up_file is None:
            st.info("ℹ️ Upload a file to get started. Bank statements and Tally exports (Day Book / Bank Book) both work.")
        else:
            with st.spinner("Reading file..."):
                raw_df, auto_skip, sheet_names, chosen_sheet = smart_read_table(up_file)
            sel_sheet = chosen_sheet

            if len(sheet_names) > 1:
                sel_sheet = st.selectbox(
                    "This file has multiple sheets — which one has the payments?",
                    sheet_names, index=sheet_names.index(chosen_sheet), key="tds_bulk_sheet"
                )
                if sel_sheet != chosen_sheet:
                    with st.spinner("Reading file..."):
                        raw_df, auto_skip, sheet_names, chosen_sheet = smart_read_table(up_file, sheet_name=sel_sheet)

            if raw_df is None or raw_df.empty:
                st.warning("⚠️ Couldn't find any rows in this file. Open 'Advanced options' below to set the header row manually.")
                raw_df = pd.DataFrame() if raw_df is None else raw_df

            cols_list = list(raw_df.columns)

            if not cols_list:
                st.info("ℹ️ No columns found in this file. Double check it's a valid Excel/CSV export.")
            else:
                auto_name_col, auto_amt_col, auto_date_col = auto_detect_columns(raw_df)
                auto_cat_col, auto_labour_vals = auto_detect_category_filter(
                    raw_df, exclude_cols={c for c in [auto_name_col, auto_amt_col, auto_date_col] if c}
                )

                name_col, amt_col, date_col = auto_name_col, auto_amt_col, auto_date_col
                cat_col, sel_labour_vals = None, []
                use_category_filter = auto_cat_col is not None
                if use_category_filter:
                    cat_col, sel_labour_vals = auto_cat_col, auto_labour_vals
                use_date_filter = False
                date_from, date_to = None, None

                with st.expander("⚙️ Advanced options — fix column detection or filters", expanded=False):
                    st.caption("Only open this if the auto-detected columns below look wrong.")
                    manual_skip = st.number_input(
                        "Rows to skip before the header row", min_value=0, max_value=20,
                        value=int(auto_skip), step=1, key="tds_bulk_skip_rows",
                        help="We auto-detected this. Change it if the preview below shows 'Unnamed' columns or a title row."
                    )
                    if manual_skip != auto_skip:
                        with st.spinner("Re-reading file..."):
                            raw_df, _, _, _ = smart_read_table(up_file, sheet_name=sel_sheet, forced_skip_rows=manual_skip)
                        raw_df = pd.DataFrame() if raw_df is None else raw_df
                        cols_list = list(raw_df.columns)
                        auto_name_col, auto_amt_col, auto_date_col = auto_detect_columns(raw_df)
                        auto_cat_col, auto_labour_vals = auto_detect_category_filter(
                            raw_df, exclude_cols={c for c in [auto_name_col, auto_amt_col, auto_date_col] if c}
                        )
                        name_col, amt_col, date_col = auto_name_col, auto_amt_col, auto_date_col

                    st.dataframe(raw_df.head(5), width='stretch', hide_index=True)

                    c1, c2, c3 = st.columns(3)
                    name_col = c1.selectbox("Contractor Name column", cols_list,
                                             index=cols_list.index(auto_name_col) if auto_name_col in cols_list else 0,
                                             key="tds_bulk_name_col")
                    amt_col = c2.selectbox("Amount column", cols_list,
                                            index=cols_list.index(auto_amt_col) if auto_amt_col in cols_list else 0,
                                            key="tds_bulk_amt_col")
                    date_col = c3.selectbox("Date column", cols_list,
                                             index=cols_list.index(auto_date_col) if auto_date_col in cols_list else 0,
                                             key="tds_bulk_date_col")

                    use_category_filter = st.checkbox(
                        "This sheet mixes Labour with other kinds of payments — filter by a column",
                        value=auto_cat_col is not None, key="tds_bulk_use_cat"
                    )
                    if use_category_filter:
                        cat_options = [c for c in cols_list if c not in (name_col, amt_col, date_col)] or cols_list
                        cat_col = st.selectbox(
                            "Which column marks what a payment is for?",
                            cat_options, index=cat_options.index(auto_cat_col) if auto_cat_col in cat_options else 0,
                            key="tds_bulk_cat_col"
                        )
                        uniq_vals = sorted(
                            [v for v in raw_df[cat_col].dropna().astype(str).str.strip().unique() if v], key=str.lower
                        )
                        default_labour_vals = auto_labour_vals if cat_col == auto_cat_col else [
                            v for v in uniq_vals if "labour" in v.lower() or "labor" in v.lower()
                        ]
                        sel_labour_vals = st.multiselect(
                            "Select every value in that column that means 'Labour' — pick all that apply",
                            uniq_vals, default=default_labour_vals, key="tds_bulk_labour_vals"
                        )
                    else:
                        cat_col, sel_labour_vals = None, []

                    use_date_filter = st.checkbox("Limit to a date range", value=False, key="tds_bulk_use_date_filter")
                    if use_date_filter:
                        fy_start_year = int(current_financial_year().split("-")[0])
                        dcol1, dcol2 = st.columns(2)
                        date_from = dcol1.date_input("From", date(fy_start_year, 4, 1), format="DD-MM-YYYY", key="tds_bulk_date_from")
                        date_to = dcol2.date_input("To", date.today(), format="DD-MM-YYYY", key="tds_bulk_date_to")

                filtered_df = raw_df.copy()
                if use_category_filter and cat_col:
                    filtered_df = raw_df[raw_df[cat_col].astype(str).str.strip().isin(sel_labour_vals)].copy()

                st.markdown("#### Review payments to import")
                st.caption(
                    f"Detected **{name_col}** as contractor, **{amt_col}** as amount, **{date_col}** as date"
                    + (f", filtered to Labour rows using **{cat_col}**" if use_category_filter and cat_col else "")
                    + f". Matched **{len(filtered_df)}** of {len(raw_df)} rows."
                )

                if filtered_df.empty:
                    st.info("ℹ️ No rows matched. Open 'Advanced options' above to adjust the column mapping or Labour filter.")
                else:
                    # ── build a clean working dataframe ──
                    work_df = pd.DataFrame({
                        "Contractor": filtered_df[name_col].astype(str).str.strip(),
                        "Amount": filtered_df[amt_col].apply(parse_amount_value),
                        "Date": filtered_df[date_col].apply(parse_date_value),
                    })

                    n_total = len(work_df)
                    bad_amount = work_df["Amount"].isna() | (work_df["Amount"] <= 0)
                    bad_date = work_df["Date"].isna()
                    bad_name = work_df["Contractor"].isin(["", "nan", "None"])
                    if use_date_filter:
                        out_of_range = work_df["Date"].apply(lambda d: d is not None and not (date_from <= d <= date_to))
                    else:
                        out_of_range = pd.Series([False] * n_total, index=work_df.index)

                    skip_mask = bad_amount | bad_date | bad_name | out_of_range
                    n_skipped = int(skip_mask.sum())
                    clean_df = work_df[~skip_mask].copy()

                    # flag rows that look like they're already logged, so a re-upload doesn't double-count
                    dup_mask = find_duplicate_mask(clean_df, df_txn) if not clean_df.empty else pd.Series(dtype=bool)
                    if not clean_df.empty:
                        clean_df["Include"] = ~dup_mask.values

                    unknown_contractors = sorted(set(clean_df["Contractor"]) - set(tds_only_names)) if not clean_df.empty else []

                    if n_skipped:
                        st.warning(
                            f"⚠️ {n_skipped} row(s) skipped — missing/zero amount, an unreadable date, a blank "
                            "contractor name, or outside the date range above."
                        )
                    if not clean_df.empty and int(dup_mask.sum()) > 0:
                        st.info(
                            f"ℹ️ {int(dup_mask.sum())} row(s) look like duplicates of payments already in your "
                            "Payment Log (same contractor, amount and date) — unticked by default below. "
                            "Tick 'Include' if you really do want them added again."
                        )

                    if clean_df.empty:
                        st.info("ℹ️ Nothing left to import after cleaning. Check 'Advanced options' above.")
                    else:
                        auto_add_contractors = True
                        if unknown_contractors:
                            st.warning(
                                f"⚠️ {len(unknown_contractors)} contractor name(s) aren't in your TDS-Only "
                                f"Contractors list yet: **{', '.join(unknown_contractors)}**. They'll be added "
                                "automatically with no PAN on file, so TDS defaults to the flat 20% rate until "
                                "you add their PAN in the 'TDS-Only Contractors' tab."
                            )
                            auto_add_contractors = st.checkbox(
                                f"Auto-add these {len(unknown_contractors)} new contractor(s) so their payments can be imported",
                                value=True, key="tds_bulk_autoadd"
                            )

                        edited_df = st.data_editor(
                            clean_df.sort_values("Date").reset_index(drop=True),
                            width='stretch',
                            hide_index=True,
                            key="tds_bulk_editor",
                            column_config={
                                "Include": st.column_config.CheckboxColumn("Include?"),
                                "Contractor": st.column_config.TextColumn("Contractor"),
                                "Amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f", min_value=0.0),
                                "Date": st.column_config.DateColumn("Date", format="DD-MM-YYYY"),
                            }
                        )

                        to_import = edited_df[edited_df["Include"]].copy()

                        # guard against edits made directly in the table above (e.g. amount cleared to 0)
                        still_invalid = (to_import["Amount"] <= 0) | (to_import["Contractor"].astype(str).str.strip() == "")
                        if still_invalid.any():
                            st.caption(f"↳ Skipping {int(still_invalid.sum())} row(s) edited to have no amount or contractor name.")
                            to_import = to_import[~still_invalid]

                        if not auto_add_contractors:
                            new_names_to_import = sorted(set(to_import["Contractor"]) - set(tds_only_names))
                            if new_names_to_import:
                                to_import = to_import[~to_import["Contractor"].isin(new_names_to_import)]
                                st.caption(f"↳ Skipping {len(new_names_to_import)} unregistered contractor(s) since auto-add is off.")

                        n_import = len(to_import)
                        total_amt = float(to_import["Amount"].sum()) if n_import else 0.0

                        k1, k2 = st.columns(2)
                        k1.metric("✅ Ready to import", str(n_import))
                        k2.metric("💰 Total amount", f"₹{total_amt:,.2f}")

                        if n_import == 0:
                            st.info("ℹ️ Tick at least one row above to import.")
                        elif st.button(f"📥 Import {n_import} Payment(s)", type="primary", key="tds_bulk_confirm"):
                            try:
                                with st.spinner("Importing payments..."):
                                    if auto_add_contractors:
                                        new_names = sorted(set(to_import["Contractor"]) - set(tds_only_names))
                                        for nm in new_names:
                                            supabase.table("tds_only_contractors").upsert(
                                                {"name": nm, "pan_number": "", "entity_type": "Individual / HUF"},
                                                on_conflict="name"
                                            ).execute()

                                    records = [
                                        {
                                            "contractor_name": r["Contractor"],
                                            "amount": float(r["Amount"]),
                                            "txn_date": pd.to_datetime(r["Date"]).strftime("%Y-%m-%d"),
                                        }
                                        for _, r in to_import.iterrows()
                                    ]
                                    for i in range(0, len(records), 50):
                                        supabase.table("tds_transactions").insert(records[i:i + 50]).execute()

                                st.success(
                                    f"✅ Imported {n_import} payment(s) totalling ₹{total_amt:,.2f}. "
                                    "Check the 'Payment Log' tab to review them."
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Import failed partway through: {e}")

    # ── MONTHLY TDS PAYABLE ──────────────────────────────────────────────────
    with tab_payable:
        st.caption("TDS applies to a contractor's ENTIRE financial-year total (not just the excess) once either a single payment (net amount you paid) exceeds ₹30,000 or the FY running gross total exceeds ₹1,00,000. Amounts you log are what you actually paid the contractor — TDS is grossed up on top (Gross = Paid ÷ (1 − rate)).")
        fy_options = list_financial_years()
        default_fy_index = fy_options.index(current_financial_year()) if current_financial_year() in fy_options else 0
        sel_fy = st.selectbox("Financial Year", fy_options, index=default_fy_index)

        summary_df = compute_tds_summary(df_txn, df_deductions, sel_fy, df_tds_only)

        if summary_df.empty:
            empty_state("💰", "No payments logged for this FY", "Log a bank payment in the previous sub-tab to see the TDS position here.")
        else:
            display_df = summary_df.drop(columns=["_last_txn_date"]).copy()
            for col in ["Total Paid Net (FY)", "Gross Value (FY)", "TDS Liability (FY)", "Already Deposited", "Payable Now"]:
                display_df[col] = display_df[col].apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(display_df, width='stretch', hide_index=True)

            total_payable = summary_df["Payable Now"].sum()
            k1, k2 = st.columns(2)
            k1.metric("👷 Contractors with dues", str((summary_df["Payable Now"] > 0).sum()))
            k2.metric("💰 Total TDS Payable Now", f"₹{total_payable:,.2f}")

            st.divider()
            st.markdown("#### ✅ Mark TDS as Deposited")
            st.caption("Once you've paid a contractor's TDS to the government for this FY, log it here so it's not shown as due again next month.")
            payable_names = summary_df[summary_df["Payable Now"] > 0]["Contractor"].tolist()
            if not payable_names:
                st.info("ℹ️ Nothing currently payable for this financial year.")
            else:
                with st.form("tds_deposit_form"):
                    d1, d2 = st.columns(2)
                    dep_contractor = d1.selectbox("Contractor", payable_names)
                    dep_row = summary_df[summary_df["Contractor"] == dep_contractor].iloc[0]
                    dep_amount = d2.number_input("Amount Deposited (₹)", min_value=0.0,
                                                 value=float(dep_row["Payable Now"]), step=100.0, format="%.2f")
                    dep_date = st.date_input("Date Deposited", date.today(), format="DD-MM-YYYY")
                    if st.form_submit_button("💾 Record Deposit", type="primary"):
                        try:
                            supabase.table("tds_deductions").insert({
                                "contractor_name": dep_contractor,
                                "financial_year": sel_fy,
                                "amount": dep_amount,
                                "deposited_date": str(dep_date),
                            }).execute()
                            st.success(f"✅ Recorded ₹{dep_amount:,.2f} TDS deposited for **{dep_contractor}**.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Could not save this deposit: {e}")

    # ── TDS-ONLY CONTRACTORS (never appear in Daily Entry) ──────────────────
    with tab_only:
        st.caption("Contractors added here are used ONLY for TDS tracking — they will never show up in the Daily Entry, Weekly Bill, or any labour-tracking screens.")

        if df_tds_only.empty:
            empty_state("👤", "No TDS-only contractors yet", "Add one below.")
        else:
            show_only = df_tds_only[["name", "pan_number", "entity_type"]].rename(
                columns={"name": "Contractor", "pan_number": "PAN", "entity_type": "Entity Type"}
            )
            st.dataframe(show_only, width='stretch', hide_index=True)

        st.divider()
        only_act = st.radio("What would you like to do?", ["Add New", "Edit Existing"], horizontal=True, key="tds_only_act")

        with st.form("tds_only_form"):
            if only_act == "Add New":
                st.markdown("#### ➕ Add TDS-Only Contractor")
                oc_name = st.text_input("Contractor Name", placeholder="e.g. Sharma Electricals")
                default_pan_o, default_entity_o = "", "Individual / HUF"
            else:
                st.markdown("#### ✏️ Edit TDS-Only Contractor")
                if tds_only_names:
                    oc_name = st.selectbox("Select Contractor", tds_only_names)
                    existing_row = df_tds_only[df_tds_only["name"] == oc_name].iloc[0]
                    default_pan_o = existing_row.get("pan_number", "") or ""
                    default_entity_o = existing_row.get("entity_type", "Individual / HUF") or "Individual / HUF"
                else:
                    st.info("ℹ️ No TDS-only contractors to edit yet.")
                    oc_name = None
                    default_pan_o, default_entity_o = "", "Individual / HUF"

            oc_pan = st.text_input("PAN Number", value=default_pan_o, placeholder="e.g. ABCDE1234F",
                                   help="Leave blank if not available — TDS will default to the flat 20% no-PAN rate.")
            oc_entity = st.selectbox("Entity Type", TDS_ENTITY_OPTIONS,
                                     index=TDS_ENTITY_OPTIONS.index(default_entity_o) if default_entity_o in TDS_ENTITY_OPTIONS else 0)

            if st.form_submit_button("💾 Save Contractor", type="primary"):
                if not oc_name or not str(oc_name).strip():
                    st.error("⚠️ Enter a contractor name.")
                else:
                    try:
                        payload = {
                            "name": oc_name.strip(),
                            "pan_number": oc_pan.strip().upper() if oc_pan else "",
                            "entity_type": oc_entity,
                        }
                        supabase.table("tds_only_contractors").upsert(payload, on_conflict="name").execute()
                        st.success(f"✅ Saved **{oc_name}** as a TDS-only contractor.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Could not save this contractor: {e}")

        if tds_only_names:
            st.divider()
            st.markdown("##### 🗑️ Delete a TDS-Only Contractor")
            st.caption("This removes them from the dropdown when logging new payments. Any payments already logged under their name stay in the Payment Log and reports.")
            del_contractor = st.selectbox("Select contractor to delete", tds_only_names, key="tds_only_del_select")
            if st.button("🗑️ Delete This Contractor"):
                try:
                    supabase.table("tds_only_contractors").delete().eq("name", del_contractor).execute()
                    st.success(f"✅ Deleted **{del_contractor}**.")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Could not delete this contractor: {e}")

    # ── DOWNLOAD REPORT ──────────────────────────────────────────────────────
    with tab_report:
        st.caption("Generate a TDS payment report for a month, quarter, or any custom date range — with PDF and Excel downloads.")

        if df_txn.empty:
            empty_state("📄", "No payments logged yet", "Log a bank payment first to generate a report.")
        else:
            period_type = st.radio("Report For", ["Monthly", "Quarterly", "Custom Range"], horizontal=True, key="tds_report_period_type")

            report_start, report_end, period_label = None, None, ""

            if period_type == "Monthly":
                rm1, rm2 = st.columns(2)
                month_names = ["January", "February", "March", "April", "May", "June",
                               "July", "August", "September", "October", "November", "December"]
                sel_month_name = rm1.selectbox("Month", month_names, index=date.today().month - 1)
                sel_year = rm2.number_input("Year", min_value=2020, max_value=2100, value=date.today().year, step=1)
                sel_month_num = month_names.index(sel_month_name) + 1
                report_start = date(sel_year, sel_month_num, 1)
                next_month = date(sel_year + (1 if sel_month_num == 12 else 0), (sel_month_num % 12) + 1, 1)
                report_end = next_month - timedelta(days=1)
                period_label = f"{sel_month_name} {sel_year}"

            elif period_type == "Quarterly":
                rq1, rq2 = st.columns(2)
                fy_options_rep = list_financial_years()
                default_fy_idx = fy_options_rep.index(current_financial_year()) if current_financial_year() in fy_options_rep else 0
                sel_fy_q = rq1.selectbox("Financial Year", fy_options_rep, index=default_fy_idx, key="tds_report_fy_q")
                quarter_map = {
                    "Q1 (Apr - Jun)": (4, 6), "Q2 (Jul - Sep)": (7, 9),
                    "Q3 (Oct - Dec)": (10, 12), "Q4 (Jan - Mar)": (1, 3),
                }
                sel_q_label = rq2.selectbox("Quarter", list(quarter_map.keys()))
                fy_start_year = int(sel_fy_q.split("-")[0])
                start_month, end_month = quarter_map[sel_q_label]
                q_year_start = fy_start_year if start_month >= 4 else fy_start_year + 1
                q_year_end = fy_start_year if end_month >= 4 else fy_start_year + 1
                report_start = date(q_year_start, start_month, 1)
                last_day_end_month = date(q_year_end + (1 if end_month == 12 else 0), (end_month % 12) + 1, 1) - timedelta(days=1)
                report_end = last_day_end_month
                period_label = f"{sel_q_label} — FY {sel_fy_q}"

            else:
                rc1, rc2 = st.columns(2)
                report_start = rc1.date_input("From", date.today().replace(day=1), format="DD-MM-YYYY", key="tds_report_from")
                report_end = rc2.date_input("To", date.today(), format="DD-MM-YYYY", key="tds_report_to")
                period_label = f"{report_start.strftime('%d %b %Y')} to {report_end.strftime('%d %b %Y')}"

            if report_start and report_end and report_start > report_end:
                st.error("⚠️ 'From' date must be before 'To' date.")
            else:
                report_df = compute_tds_period_report(df_txn, df_tds_only, df_deductions, report_start, report_end)

                if report_df.empty:
                    empty_state("📄", "No payments found for this period", "Try a different date range.")
                else:
                    display_report = report_df.copy()
                    for col in ["Total Paid (Net)", "Gross Value", "TDS for Period", "Deposited in Period"]:
                        display_report[col] = display_report[col].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(display_report, width='stretch', hide_index=True)

                    rk1, rk2 = st.columns(2)
                    rk1.metric("💰 Total Paid Net (Period)", f"₹{report_df['Total Paid (Net)'].sum():,.2f}")
                    rk2.metric("🧾 Total TDS (Period)", f"₹{report_df['TDS for Period'].sum():,.2f}")

                    st.divider()
                    dl1, dl2 = st.columns(2)
                    with dl1:
                        pdf_bytes = generate_tds_report_pdf(period_label, report_df)
                        st.download_button(
                            "⬇️ Download PDF", data=pdf_bytes,
                            file_name=f"TDS_Report_{period_label.replace(' ', '_').replace('/', '-')}.pdf",
                            mime="application/pdf", width='stretch'
                        )
                    with dl2:
                        excel_bytes = generate_tds_report_excel(period_label, report_df)
                        st.download_button(
                            "⬇️ Download Excel", data=excel_bytes,
                            file_name=f"TDS_Report_{period_label.replace(' ', '_').replace('/', '-')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch'
                        )

    # ── PAYMENT LOG ──────────────────────────────────────────────────────────
    with tab_history:
        st.caption("All bank payments logged for the TDS calculator.")
        if df_txn.empty:
            empty_state("📜", "No payments logged yet")
        else:
            hist = df_txn.copy()
            hist["txn_date"] = pd.to_datetime(hist["txn_date"]).dt.date
            hist = hist.sort_values("txn_date", ascending=False)
            hist_display = hist[["contractor_name", "amount", "txn_date"]].rename(
                columns={"contractor_name": "Contractor", "amount": "Amount Paid Net (₹)", "txn_date": "Date"}
            )
            hist_display["Amount Paid Net (₹)"] = hist_display["Amount Paid Net (₹)"].apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(hist_display, width='stretch', hide_index=True)

            st.divider()
            st.markdown("##### 🗑️ Delete a Logged Payment")
            del_options = {f"{r['contractor_name']} — ₹{r['amount']:,.2f} on {r['txn_date'].strftime('%d %b %Y')}": r["id"]
                           for _, r in hist.iterrows()} if "id" in hist.columns else {}
            if del_options:
                sel_del = st.selectbox("Select entry to delete", list(del_options.keys()))
                if st.button("🗑️ Delete This Payment"):
                    try:
                        supabase.table("tds_transactions").delete().eq("id", del_options[sel_del]).execute()
                        st.success("✅ Payment deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Could not delete this entry: {e}")

elif current_tab == "📑 Custom Labour Report":
    page_header("📑 Custom Labour Report", "Download a day-by-day labour report for any site or contractor, for any date range you choose")

    df_entries = fetch_data("entries")
    df_contractors = fetch_data("contractors")

    if df_entries.empty:
        empty_state("📊", "No entries yet", "Start by logging daily attendance in the Daily Entry tab.")
    else:
        df_entries = df_entries.copy()
        df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors="coerce")
        df_entries = df_entries.dropna(subset=["date_dt"])

        df_contractors = df_contractors.copy()
        if not df_contractors.empty:
            df_contractors["effective_date"] = pd.to_datetime(
                df_contractors["effective_date"], errors="coerce"
            ).dt.date

        st.markdown("### Step 1 — Choose Report Type & Dates")
        c1, c2, c3 = st.columns(3)
        report_mode = c1.radio("Report For", ["🏢 Site", "👷 Contractor"], horizontal=False)
        rep_start = c2.date_input("📅 From", date.today() - timedelta(days=29), format="DD-MM-YYYY", key="clr_from")
        rep_end = c3.date_input("📅 To", date.today(), format="DD-MM-YYYY", key="clr_to")

        if rep_start > rep_end:
            st.error("⚠️ 'From' date must be on or before 'To' date.")
        else:
            if report_mode == "🏢 Site":
                options = sorted(df_entries["site"].dropna().unique().tolist())
                label = "🏗️ Select Site"
            else:
                options = sorted(df_entries["contractor"].dropna().unique().tolist())
                label = "👷 Select Contractor"

            if not options:
                st.info("ℹ️ No data available to build this report yet.")
            else:
                sel_name = st.selectbox(label, options, key="clr_sel_name")

                mask = (df_entries["date_dt"].dt.date >= rep_start) & (df_entries["date_dt"].dt.date <= rep_end)
                if report_mode == "🏢 Site":
                    mask &= (df_entries["site"] == sel_name)
                else:
                    mask &= (df_entries["contractor"] == sel_name)
                df_range = df_entries[mask].copy()

                st.divider()
                st.markdown(f"### Step 2 — Preview: {sel_name}")
                st.caption(f"Showing **{rep_start.strftime('%d %b %Y')}** to **{rep_end.strftime('%d %b %Y')}** ({(rep_end - rep_start).days + 1} days).")

                if df_range.empty:
                    st.info("ℹ️ No entries found for this selection in the chosen date range.")
                else:
                    full_range_dates = [rep_start + timedelta(days=i) for i in range((rep_end - rep_start).days + 1)]
                    billing_data = []
                    grand_amt = 0.0

                    # When reporting on a Site, break out each contractor who worked there.
                    # When reporting on a Contractor, break out each site they worked at.
                    if report_mode == "🏢 Site":
                        sub_groups = sorted(df_range["contractor"].dropna().unique().tolist())
                        group_col = "contractor"
                    else:
                        sub_groups = sorted(df_range["site"].dropna().unique().tolist())
                        group_col = "site"

                    for grp in sub_groups:
                        df_sub = df_range[df_range[group_col] == grp]
                        con_for_rate = grp if report_mode == "🏢 Site" else sel_name
                        rm, rh, rl = _safe_get_rates(df_contractors, con_for_rate, rep_start) if not df_contractors.empty else (0.0, 0.0, 0.0)
                        rows, tm, th, tl, tamt = _build_week_rows(df_sub, full_range_dates, rm, rh, rl)
                        billing_data.append({
                            "name": grp, "rows": rows,
                            "totals": {"m": tm, "h": th, "l": tl, "amt": tamt},
                            "rates": {"rm": rm, "rh": rh, "rl": rl}
                        })
                        grand_amt += tamt

                        st.markdown(f"#### {'👷' if report_mode == '🏢 Site' else '📍'} {grp}")
                        if rm == 0 and rh == 0 and rl == 0:
                            st.caption("⚠️ No rates found — amounts show as ₹0. Add rates in the Contractors tab.")
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("💰 Amount", f"₹{tamt:,.0f}")
                        k2.metric("🧱 Mason Shifts", f"{tm:g}")
                        k3.metric("🛠️ Helper Shifts", f"{th:g}")
                        k4.metric("👩 Ladies Shifts", f"{tl:g}")
                        with st.expander(f"📄 Day-by-Day: {grp}"):
                            st.caption("— = no entry submitted. Nil = holiday/no-work entry submitted.")
                            # st.table (not st.dataframe) on purpose — avoids the pyarrow
                            # native-crash issue seen on this environment's Python build.
                            st.table(pd.DataFrame(rows))

                    st.divider()
                    st.markdown(f"## 💰 Grand Total: ₹{grand_amt:,.2f}")

                    period_label = f"{rep_start.strftime('%d-%m-%Y')} to {rep_end.strftime('%d-%m-%Y')}"

                    cA, cB = st.columns(2)
                    with cA:
                        if st.button("📄 Generate PDF Report", type="primary", width='stretch', key="clr_gen_pdf"):
                            with st.spinner("Generating your PDF report..."):
                                pdf_bytes = generate_pdf_bytes(sel_name, period_label, billing_data)
                            st.session_state["_clr_pdf_bytes"] = pdf_bytes
                            st.session_state["_clr_pdf_name"] = f"Labour_Report_{sel_name}_{rep_start.strftime('%d%b')}_{rep_end.strftime('%d%b')}.pdf"
                    with cB:
                        csv_bytes = df_range.drop(columns=["date_dt"], errors="ignore").to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "📊 Download Raw Data (CSV)", csv_bytes,
                            f"Labour_Data_{sel_name}_{rep_start.strftime('%d%b')}_{rep_end.strftime('%d%b')}.csv",
                            "text/csv", width='stretch'
                        )

                    # Rendered outside the generate-button block on purpose: clicking
                    # download_button triggers its own rerun, which would otherwise
                    # reset st.button("Generate...") to False and make this vanish
                    # before the click could register. session_state survives that.
                    if st.session_state.get("_clr_pdf_bytes"):
                        st.success("✅ Report ready to download!")
                        st.download_button(
                            label="⬇️ Download PDF Report",
                            data=st.session_state["_clr_pdf_bytes"],
                            file_name=st.session_state["_clr_pdf_name"],
                            mime="application/pdf"
                        )

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
        }), width='stretch', hide_index=True)

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
        st.dataframe(sites_df, hide_index=True, width='stretch')
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
            width='stretch', hide_index=True
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
                default_pan, default_entity = "", "Individual / HUF"
            else:
                st.markdown("#### ✏️ Update Contractor Rate")
                st.caption("This adds a new rate entry. The old rate is preserved for historical bills.")
                cn = st.selectbox("Select Contractor", df_c["name"].unique()) if not df_c.empty else st.text_input("Contractor Name")
                default_pan, default_entity = latest_contractor_profile(df_c, cn) if cn else ("", "Individual / HUF")

            c1, c2, c3 = st.columns(3)
            rm = c1.number_input("Mason Rate (₹/shift)", value=0, min_value=0, help="Daily rate per mason worker.")
            rh = c2.number_input("Helper Rate (₹/shift)", value=0, min_value=0, help="Daily rate per helper worker.")
            rl = c3.number_input("Ladies Rate (₹/shift)", value=0, min_value=0, help="Daily rate per ladies worker.")
            ed = st.date_input("Effective From", date.today(), format="DD-MM-YYYY",
                               help="The date from which this rate applies. All bills from this date onward will use this rate.")

            st.markdown("###### 🧾 TDS Details")
            st.caption("Used by the TDS Calculator to work out the deduction rate for this contractor.")
            c4, c5 = st.columns(2)
            pan_in = c4.text_input("PAN Number", value=default_pan, placeholder="e.g. ABCDE1234F",
                                   help="Leave blank if not available — TDS will default to the flat 20% no-PAN rate.")
            entity_in = c5.selectbox("Entity Type", TDS_ENTITY_OPTIONS,
                                     index=TDS_ENTITY_OPTIONS.index(default_entity) if default_entity in TDS_ENTITY_OPTIONS else 0,
                                     help="Individual/HUF is taxed at 1%, everything else (company, firm, partnership) at 2%.")

            if st.form_submit_button("💾 Save Rate"):
                insert_status = "Active"
                if act == "Update Existing Rate" and "status" in df_c.columns and cn:
                    insert_status = df_c[df_c["name"] == cn].iloc[0].get("status", "Active")

                data_to_insert = {
                    "name": cn, "rate_mason": rm, "rate_helper": rh, "rate_ladies": rl, "effective_date": str(ed),
                    "pan_number": pan_in.strip().upper() if pan_in else "", "entity_type": entity_in,
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
        st.dataframe(users_df, width='stretch', hide_index=True)
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
        rl = c_u3.selectbox("🎭 Role", ["user", "admin"], help="'user' = field worker. 'admin' = full access.")
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
                        st.dataframe(pd.DataFrame(d[k_map[cat]]), width='stretch', hide_index=True)
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
        st.dataframe(df_display, width='stretch', hide_index=True)

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
            st.dataframe(by_site, width='stretch', hide_index=True)

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
            st.dataframe(by_con, width='stretch', hide_index=True)

    # ── back / new search nudge ───────────────────────────────────────────────
    st.divider()
    st.caption("💡 Use the search box in the sidebar to run a new search, or click any navigation tab to go back.")