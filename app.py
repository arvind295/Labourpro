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
    initial_sidebar_state="collapsed"
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
        * { color: #000000 !important; }
        .stApp { background-color: #FFFFFF !important; }
        section[data-testid="stSidebar"] { background-color: #F8F9FA !important; border-right: 1px solid #E0E0E0; }
        section[data-testid="stSidebar"] * { color: #000000 !important; }
        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important; 
            color: #000000 !important; 
            border: 1px solid #ccc !important; 
        }
        span[data-baseweb="tag"] { background-color: #E0E0E0 !important; color: black !important; }
        div[data-testid="stDataFrame"], div[data-testid="stTable"] { color: #000000 !important; background-color: #FFFFFF !important; }
        th { background-color: #E0E0E0 !important; border-bottom: 2px solid #000 !important; }
        td { border-bottom: 1px solid #ddd !important; }
        button[kind="primary"] { background-color: #F39C12 !important; color: #FFFFFF !important; border: none !important; }
        button[disabled] { background-color: #cccccc !important; color: #666666 !important; cursor: not-allowed; }
        div[data-testid="stMetricValue"] { font-size: 1.4rem !important; color: #F39C12 !important; }
        div[data-testid="stMetricLabel"] { font-size: 1rem !important; color: #333333 !important; }
        @media only screen and (max-width: 600px) {
            h1 { font-size: 1.8rem !important; }
            .stButton button { width: 100% !important; }
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
            st.error(f"Error fetching data chunk: {e}")
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

            # Table Header
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(25, 8, "Date", 1)
            pdf.cell(50, 8, "Vendor", 1)
            pdf.cell(80, 8, "Material", 1)
            pdf.cell(15, 8, "Qty", 1)
            pdf.cell(20, 8, "Amount", 1)
            pdf.ln()

            # Table Rows
            pdf.set_font("Arial", '', 9)
            cat_total = 0
            for _, row in df_cat.iterrows():
                pdf.cell(25, 8, str(row.get('date', '')), 1)
                
                # Truncate strings to prevent PDF layout breaking
                vendor = str(row.get('vendor', ''))[:22]
                material = str(row.get('material_name', ''))[:40]
                
                pdf.cell(50, 8, vendor, 1)
                pdf.cell(80, 8, material, 1)
                pdf.cell(15, 8, str(row.get('quantity', '')), 1)
                amt = float(row.get('amount', 0))
                cat_total += amt
                pdf.cell(20, 8, f"{amt:,.0f}", 1)
                pdf.ln()

            # Category Total
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(170, 8, f"Total {cat}", 1, 0, 'R')
            pdf.cell(20, 8, f"{cat_total:,.0f}", 1, 1, 'L')
            pdf.ln(8)
            total_grand += cat_total

    # Grand Total
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

def generate_client_invoice_bytes(site_name, date_range_label, labor_cost, df_mats, grand_total):
    pdf = ClientInvoicePDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(100, 8, f"Project Site: {site_name}", 0, 0, 'L')
    pdf.set_font("Arial", '', 11)
    pdf.cell(90, 8, f"Date Generated: {date.today().strftime('%d %b %Y')}", 0, 1, 'R')
    pdf.cell(100, 8, f"Billing Period: {date_range_label}", 0, 1, 'L')
    pdf.ln(10)
    
    # --- Section 1: Labor ---
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " 1. LABOR EXPENSES", 0, 1, 'L', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(140, 10, "Total Labor Cost for the Period (Auto-Calculated):", 1, 0, 'L')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, f"Rs. {labor_cost:,.2f}", 1, 1, 'R')
    pdf.ln(10)
    
    # --- Section 2: Materials ---
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(52, 73, 94)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " 2. MATERIAL EXPENSES", 0, 1, 'L', fill=True)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(236, 240, 241)
    
    # Headers to include Date
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
            pdf.cell(30, 10, f"{m_date[:12]}", 1, 0, 'C')
            pdf.cell(110, 10, f" {desc[:55]}", 1, 0, 'L')
            pdf.cell(50, 10, f"{amt:,.2f}", 1, 1, 'R')
    else:
        pdf.cell(190, 10, "No materials entered for this period.", 1, 1, 'C')
        
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(140, 10, "Total Material Cost:", 1, 0, 'R', fill=True)
    pdf.cell(50, 10, f"Rs. {mat_total:,.2f}", 1, 1, 'R', fill=True)
    pdf.ln(15)
    
    # --- Grand Total ---
    pdf.set_font("Arial", 'B', 16)
    pdf.set_fill_color(46, 204, 113)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(140, 15, " GRAND TOTAL DUE:", 1, 0, 'R', fill=True)
    pdf.cell(50, 15, f"Rs. {grand_total:,.2f}", 1, 1, 'R', fill=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- WEEKLY BILL RENDERER ---
def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty: 
        st.info("No data available.")
        return
    
    is_admin = (st.session_state["role"] == "admin")
    if not is_admin:
        assigned_raw = st.session_state.get("assigned_site", "")
        if "All" not in assigned_raw and "None/All" not in assigned_raw:
            user_sites = [s.strip() for s in assigned_raw.split(",")]
            df_entries = df_entries[df_entries["site"].isin(user_sites)]
            if df_entries.empty: 
                st.warning("No data found for your assigned sites.")
                return

    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors='coerce')
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"], errors='coerce').dt.date
    df_entries = df_entries.dropna(subset=["date_dt"])
    if df_entries.empty:
        st.info("No valid date entries found.")
        return

    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
    
    unique_weeks = df_entries[["start_date", "week_label"]].drop_duplicates().sort_values("start_date", ascending=False)
    weeks = unique_weeks["week_label"].tolist()
    sel_week = st.selectbox("Select Week", weeks) if weeks else None
    
    if not sel_week: 
        return

    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    week_start_obj = df_week.iloc[0]["start_date"]
    full_week_dates = [week_start_obj + timedelta(days=i) for i in range(7)] 
    
    if is_admin:
        csv_data = df_week.to_csv(index=False).encode('utf-8')
        st.download_button(f"📊 Download {sel_week} (Excel/CSV)", csv_data, f"Data_{sel_week}.csv", "text/csv")
        st.divider()

    tab_site, tab_con = st.tabs(["🏢 View by Site", "👷 View by Contractor"])
    
    with tab_site:
        all_sites = sorted(df_week["site"].unique())
        sel_site = st.pills("Select Site", all_sites, key="sb_site", default=all_sites[0] if all_sites else None)
        if sel_site:
            st.divider()
            st.markdown(f"### 📍 Site: {sel_site}")
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
                        if m == 0 and h == 0 and l == 0:
                            dm, dh, dl = "Nil", "Nil", "Nil"
                        else:
                            dm, dh, dl = str(m), str(h), str(l)
                    else:
                        m, h, l, current_daily_cost = 0, 0, 0, 0
                        dm, dh, dl = "0", "0", "0"
                    
                    rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
                    tm += m
                    th += h
                    tl += l
                    tamt += current_daily_cost  

                pdf_data.append({"name": con_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

                st.markdown(f"#### 👷 {con_name}")
                if is_admin:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 Payable", f"₹{tamt:,.0f}")
                else:
                    k2, k3, k4 = st.columns(3)
                
                k2.metric("🧱 Masons", f"{tm}")
                k3.metric("🛠️ Helpers", f"{th}")
                k4.metric("👩 Ladies", f"{tl}")
                
                with st.expander(f"📄 Details: {con_name}"):
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if pdf_data:
                try:
                    pdf_bytes = generate_pdf_bytes(sel_site, sel_week, pdf_data)
                    st.download_button(f"⬇️ PDF ({sel_site})", pdf_bytes, f"Bill_{sel_site}.pdf", "application/pdf")
                except: 
                    pass

    with tab_con:
        all_cons = sorted(df_week["contractor"].unique())
        sel_con = st.pills("Select Contractor", all_cons, key="sb_con", default=all_cons[0] if all_cons else None)
        if sel_con:
            st.divider()
            st.markdown(f"### 👷 Contractor: {sel_con}")
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
                        if m == 0 and h == 0 and l == 0:
                            dm, dh, dl = "Nil", "Nil", "Nil"
                        else:
                            dm, dh, dl = str(m), str(h), str(l)
                    else:
                        m, h, l, current_daily_cost = 0, 0, 0, 0
                        dm, dh, dl = "0", "0", "0"
                    
                    rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
                    tm += m
                    th += h
                    tl += l
                    tamt += current_daily_cost

                pdf_data.append({"name": site_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

                st.markdown(f"#### 📍 {site_name}")
                if is_admin:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 Payable", f"₹{tamt:,.0f}")
                else:
                    k2, k3, k4 = st.columns(3)

                k2.metric("🧱 Masons", f"{tm}")
                k3.metric("🛠️ Helpers", f"{th}")
                k4.metric("👩 Ladies", f"{tl}")
                
                with st.expander(f"📄 Details: {site_name}"):
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if pdf_data:
                try:
                    pdf_bytes = generate_pdf_bytes(sel_con, sel_week, pdf_data)
                    st.download_button(f"⬇️ PDF ({sel_con})", pdf_bytes, f"Bill_{sel_con}.pdf", "application/pdf")
                except: 
                    pass

# --- 6. AUTO-LOGIN CHECK ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

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
            st.toast(f"Welcome back, {user['name']}!")
        else:
            try:
                cookie_manager.delete("auth_token")
            except KeyError:
                pass
    except Exception as e:
        pass

# --- 7. LOGIN PROCESS ---
def login_process():
    col1, col2, col3 = st.columns([1, 10, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center; color: black;'>🏗️ LabourPro</h1><p style='text-align: center; color: grey;'>Site Entry Portal</p><hr>", unsafe_allow_html=True)
        st.subheader("👷 Team Login")
        with st.form("u_log"):
            ph = st.text_input("Enter Mobile Number", max_chars=10, placeholder="9876543210")
            pin = st.text_input("Enter 4-Digit PIN", type="password", max_chars=4, placeholder="****")
            if st.form_submit_button("🚀 Login", type="primary", use_container_width=True):
                if ph and pin:
                    try:
                        response = supabase.table("users").select("*").eq("phone", ph).execute()
                        if not response.data:
                            st.error("❌ User not found.")
                        else:
                            user = response.data[0]
                            user_mpin = user.get("mpin", "1234")
                            if user_mpin is None: user_mpin = "1234"
                            if str(pin) != str(user_mpin):
                                st.error("❌ Incorrect PIN")
                            elif user.get("status") == "Resigned":
                                st.error("⛔ Account Deactivated.")
                            elif user.get("role") == "admin":
                                st.error("⚠️ Admins: Please use the 'Admin Login' below.")
                            else:
                                new_token = str(uuid.uuid4())
                                supabase.table("users").update({"session_token": new_token}).eq("phone", ph).execute()
                                cookie_manager.set("auth_token", new_token, expires_at=datetime.now() + timedelta(days=30))
                                st.session_state.update({
                                    "logged_in": True, 
                                    "phone": user["phone"], 
                                    "role": "user",
                                    "user_name": user["name"],
                                    "assigned_site": user.get("assigned_site", "All")
                                })
                                st.success("Logged In!")
                                time.sleep(1)
                                st.rerun()
                    except Exception as e:
                        st.warning("⚠️ Connection error. Try again.")
                else:
                    st.warning("Please enter Phone and PIN.")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔐 Admin Login"):
            with st.form("a_log"):
                ph_a = st.text_input("Admin Mobile")
                pw_a = st.text_input("Password", type="password")
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
                                st.error("❌ Not an Admin Account")
                        except Exception as e:
                             st.warning("⚠️ Connection error.")
                    else:
                        st.error("❌ Wrong Password")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 8. SIDEBAR LOGOUT & SETTINGS ---
with st.sidebar:
    st.info(f"Role: **{st.session_state['role'].upper()}**")
    if st.session_state["role"] == "user":
        with st.expander("🔐 Change My PIN"):
            new_pin = st.text_input("New 4-Digit PIN", max_chars=4, type="password", key="new_u_pin")
            if st.button("Update PIN"):
                if len(new_pin) == 4 and new_pin.isdigit():
                    try:
                        supabase.table("users").update({"mpin": new_pin}).eq("phone", st.session_state["phone"]).execute()
                        st.success("PIN Updated!")
                    except:
                        st.error("Error updating PIN.")
                else:
                    st.error("PIN must be 4 digits.")
    st.divider()
    if st.button("Logout"):
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

# --- 9. MAIN APP NAVIGATION ---
tabs = ["📝 Daily Entry", "📊 Weekly Bill", "🧱 Materials", "📓 My Diary"]
if st.session_state["role"] == "admin": 
    tabs += ["📈 Dashboard", "🧾 Client Invoice", "🔍 Site Logs", "📍 Sites", "👷 Contractors", "👥 Users", "📂 Archive & Recovery"]

current_tab = st.selectbox("Navigate", tabs, label_visibility="collapsed")
st.divider()

# ==============================================================================
# TAB 1: DAILY ENTRY
# ==============================================================================
if current_tab == "📝 Daily Entry":
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")
    
    if df_sites.empty: 
        st.warning("Admin must add sites.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        if st.session_state["role"] != "admin":
            u = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
            if u.data and u.data.get("assigned_site"):
                raw_assignments = u.data.get("assigned_site", "")
                assigned_list = [s.strip() for s in raw_assignments.split(",")]
                if "None/All" in assigned_list or "All" in assigned_list:
                    pass 
                else:
                    av_sites = [s for s in av_sites if s in assigned_list]
            else:
                st.error("No site assigned.")
                st.stop()

        if not av_sites:
            st.error("You are assigned to sites that no longer exist.")
            st.stop()

        st.subheader("New Work Entry")
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("Date", date.today(), format="DD-MM-YYYY")
        st_sel = c2.selectbox("Site", av_sites, index=None, placeholder="Select Site...")
        con_sel_options = df_con["name"].unique() if not df_con.empty else []
        con_sel = c3.selectbox("Contractor", con_sel_options, index=None, placeholder="Select Contractor...")
        
        if st_sel and con_sel:
            st.write(f"**Entry for:** {st_sel} | {con_sel}")
            exist = None
            try:
                r = supabase.table("entries").select("*").eq("date", str(dt)).eq("site", st_sel).eq("contractor", con_sel).execute()
                if r.data: 
                    exist = r.data[0]
            except: 
                pass

            mode = "new"
            if exist: 
                mode = "edit"
                st.warning("✏️ Editing Entry")
            
            is_nil_default = False
            if exist and exist.get("count_mason") == 0 and exist.get("count_helper") == 0 and exist.get("count_ladies") == 0:
                is_nil_default = True
                
            is_nil = st.checkbox("⛔ No Work / Holiday (Nil Entry)", value=is_nil_default)
            
            if is_nil:
                nm, nh, nl, cost = 0, 0, 0, 0
                default_desc = "No Work / Holiday"
                if exist:
                    default_desc = exist.get("work_description", "No Work / Holiday")
                wdesc = st.text_input("Reason (Optional)", value=default_desc)
                st.info("⚠️ This will be saved as a 'Nil' entry.")
                uploaded_photo = None
            else:
                vm, vh, vl, vd = 0.0, 0.0, 0.0, ""
                if exist: 
                    vm = float(exist.get("count_mason", 0))
                    vh = float(exist.get("count_helper", 0))
                    vl = float(exist.get("count_ladies", 0))
                    vd = exist.get("work_description", "")
                
                c4, c5, c6 = st.columns(3)
                nm = c4.number_input("Mason", value=vm, step=0.5)
                nh = c5.number_input("Helper", value=vh, step=0.5)
                nl = c6.number_input("Ladies", value=vl, step=0.5)
                wdesc = st.text_area("Description", value=vd)

                # PHOTO UPLOAD
                uploaded_photo = st.file_uploader("📸 Upload Site Photo (Optional)", type=["jpg", "jpeg", "png", "webp"])

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
                        st.info(f"💰 Est Cost: ₹{cost:,.2f}")
                else:
                    st.error("No rate found. Cost will be 0.")
                    cost = 0

            if st.button("Save Entry", type="primary", use_container_width=True): 
                photo_link = ""
                if uploaded_photo:
                    with st.spinner("Uploading photo..."):
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
                    else: 
                        supabase.table("entries").update(load).eq("id", exist["id"]).execute()
                    st.success("✅ Saved Successfully!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.warning("⚠️ Network timeout. Please click 'Save' again.")

    if st.session_state["role"] == "admin": 
        st.divider()
        st.subheader("📋 Recent Entries (Last 50)")
        try:
            response = supabase.table("entries").select("*").order("date", desc=True).limit(50).execute()
            if response.data: 
                df_recent = pd.DataFrame(response.data)
                if "photo_url" in df_recent.columns:
                    df_recent["has_photo"] = df_recent["photo_url"].apply(lambda x: "📸 Yes" if x else "No")
                    cols_to_show = ["date", "site", "contractor", "total_cost", "work_description", "has_photo"]
                else:
                    cols_to_show = ["date", "site", "contractor", "total_cost", "work_description"]
                st.dataframe(df_recent[cols_to_show], use_container_width=True)
        except: 
            pass

# ==============================================================================
# TAB 2: WEEKLY BILL
# ==============================================================================
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill")
    try:
        df_entries = fetch_data("entries")
    except:
        df_entries = pd.DataFrame()
    render_weekly_bill(df_entries, fetch_data("contractors"))

# ==============================================================================
# TAB 3: MATERIALS
# ==============================================================================
elif current_tab == "🧱 Materials":
    st.subheader("🧱 Material Tracking")
    df_sites = fetch_data("sites")
    if df_sites.empty:
        st.warning("Please add sites first.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        if st.session_state["role"] != "admin":
            assigned_raw = st.session_state.get("assigned_site", "")
            if "All" not in assigned_raw and "None/All" not in assigned_raw:
                assigned_list = [s.strip() for s in assigned_raw.split(",")]
                av_sites = [s for s in av_sites if s in assigned_list]
            if not av_sites:
                st.error("⚠️ You are not assigned to any active sites.")
                st.stop()

        sel_site = st.selectbox("📍 Select Site for Materials", av_sites)
        st.divider()

        if sel_site:
            try:
                raw_materials = supabase.table("materials").select("*").eq("site", sel_site).execute()
                df_mat = pd.DataFrame(raw_materials.data) if raw_materials.data else pd.DataFrame()
            except Exception as e:
                df_mat = pd.DataFrame()
                st.error("Error fetching materials data.")

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

            # Week Filter Selection
            st.markdown("### 📅 Filter & Download Report")
            sel_week = st.selectbox("Select Time Period to View & Download", ["All Time"] + weeks)
            
            # Filter the dataframe based on the selection for displaying & PDF
            if sel_week != "All Time" and not df_mat.empty:
                df_mat_filtered = df_mat[df_mat["week_label"] == sel_week].copy()
            else:
                df_mat_filtered = df_mat.copy()

            # PDF Download Button (Visible to everyone)
            if not df_mat_filtered.empty:
                try:
                    pdf_bytes = generate_material_pdf_bytes(sel_site, sel_week, df_mat_filtered)
                    st.download_button(
                        label=f"⬇️ Download Material Report (PDF)", 
                        data=pdf_bytes, 
                        file_name=f"Materials_{sel_site}_{sel_week.replace(' ', '_')}.pdf", 
                        mime="application/pdf",
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {e}")
            else:
                st.info("No records found to generate a report.")
                
            st.divider()

            # Tabs for Entry & Viewing
            categories = ["Civil Material", "Steel Material", "Soil Material", "RMC"]
            mat_tabs = st.tabs(categories)

            for i, cat in enumerate(categories):
                with mat_tabs[i]:
                    st.markdown(f"### ➕ Log New {cat}")
                    with st.form(f"form_{cat}"):
                        c1, c2, c3 = st.columns(3)
                        m_date = c1.date_input("Date", date.today(), format="DD-MM-YYYY", key=f"d_{cat}")
                        m_vendor = c2.text_input("Vendor Name", key=f"v_{cat}", placeholder="e.g., ABC Suppliers")
                        m_material = c3.text_input("Material Description", key=f"m_{cat}", placeholder="e.g., Cement (50kg bags)")
                        c4, c5 = st.columns(2)
                        m_qty = c4.number_input("Quantity", min_value=0.0, step=1.0, key=f"q_{cat}")
                        m_amt = c5.number_input("Total Amount (₹)", min_value=0.0, step=100.0, key=f"a_{cat}")
                        
                        m_receipt = st.file_uploader("🧾 Upload Bill/Receipt Image (Optional)", type=["jpg", "jpeg", "png"], key=f"rec_{cat}")

                        if st.form_submit_button("Save Material Entry", type="primary", use_container_width=True):
                            if not m_vendor or not m_material:
                                st.error("Vendor and Material fields cannot be empty.")
                            else:
                                receipt_link = ""
                                if m_receipt:
                                    with st.spinner("Uploading receipt..."):
                                        receipt_link = upload_evidence(m_receipt)

                                load = {
                                    "date": str(m_date), "site": sel_site, "category": cat,
                                    "vendor": m_vendor, "material_name": m_material,
                                    "quantity": m_qty, "amount": m_amt, "receipt_url": receipt_link
                                }
                                try:
                                    supabase.table("materials").insert(load).execute()
                                    st.success(f"✅ {cat} saved successfully!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error("⚠️ Failed to save entry. Check database connection.")
                    
                    st.markdown("---")
                    st.markdown(f"### 📋 {cat} Entries ({sel_week})")
                    if not df_mat_filtered.empty:
                        df_cat = df_mat_filtered[df_mat_filtered["category"] == cat].copy()
                        
                        if not df_cat.empty:
                            df_cat = df_cat.sort_values("date_dt", ascending=False)
                            # Show total cost for both Admin and User in this view for clarity
                            total_spent = df_cat["amount"].sum()
                            st.metric(f"Total Spent on {cat}", f"₹{total_spent:,.2f}")
                            
                            display_df = df_cat[["date", "vendor", "material_name", "quantity", "amount"]].rename(
                                columns={"date": "Date", "vendor": "Vendor", "material_name": "Material", "quantity": "Quantity", "amount": "Amount (₹)"}
                            )
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                        else:
                            st.info(f"No {cat} logged for {sel_site} during {sel_week}.")
                    else:
                        st.info("No materials logged yet.")

# ==============================================================================
# TAB 4: MY DIARY
# ==============================================================================
elif current_tab == "📓 My Diary":
    st.subheader("📓 My Personal Diary")
    st.write("Use this space to jot down private notes, reminders, or site observations.")

    user_phone = st.session_state.get("phone")
    if not user_phone:
        st.error("Session error. Please log in again.")
        st.stop()

    with st.form("diary_form"):
        d_date = st.date_input("Date", date.today(), format="DD-MM-YYYY")
        d_content = st.text_area("Write your note here...", height=150, placeholder="What happened today?")
        
        if st.form_submit_button("💾 Save Note", type="primary"):
            if not d_content.strip():
                st.error("Note cannot be empty.")
            else:
                load = {"date": str(d_date), "phone": user_phone, "content": d_content.strip()}
                try:
                    supabase.table("diary_entries").insert(load).execute()
                    st.success("✅ Note saved successfully!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error("⚠️ Failed to save note. Check database connection.")

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
                    if st.button("🗑️ Delete", key=f"del_diary_{row['id']}"):
                        supabase.table("diary_entries").delete().eq("id", row['id']).execute()
                        st.rerun()
        else:
            st.info("You haven't written any notes yet.")
            
    except Exception as e:
        st.error("Error loading past entries.")

# ==============================================================================
# ADMIN ONLY TABS BELOW
# ==============================================================================

elif current_tab == "📈 Dashboard":
    st.subheader("📈 Cost Analytics & Dashboard")
    df_entries = fetch_data("entries")
    if not df_entries.empty:
        df_entries["date_dt"] = pd.to_datetime(df_entries["date"])
        total_spent = df_entries["total_cost"].sum()
        total_masons = df_entries["count_mason"].sum()
        total_helpers = df_entries["count_helper"].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total Labor Spent (All Time)", f"₹{total_spent:,.0f}")
        c2.metric("🧱 Total Masons Logged", f"{total_masons}")
        c3.metric("🛠️ Total Helpers Logged", f"{total_helpers}")
        
        st.divider()
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("### 📍 Total Cost by Site")
            site_cost = df_entries.groupby("site")["total_cost"].sum().reset_index()
            st.bar_chart(site_cost.set_index("site"), color="#F39C12")
        with col_chart2:
            st.markdown("### 📅 Daily Cost (Last 30 Days)")
            recent = df_entries[df_entries["date_dt"] >= (pd.Timestamp.now() - pd.Timedelta(days=30))]
            if not recent.empty:
                date_cost = recent.groupby(recent["date_dt"].dt.date)["total_cost"].sum().reset_index()
                st.line_chart(date_cost.set_index("date_dt"))
            else:
                st.info("No entries in the last 30 days.")
    else:
        st.info("Not enough data to generate dashboard.")

elif current_tab == "🧾 Client Invoice":
    st.subheader("🧾 Client Invoice Generator")
    df_sites = fetch_data("sites")
    if df_sites.empty: st.warning("No sites available.")
    else:
        if "is_client_site" in df_sites.columns: client_sites = df_sites[df_sites["is_client_site"] == True]["name"].tolist()
        else:
            client_sites = []
            st.error("⚠️ Database Error: Please add the 'is_client_site' boolean column to the 'sites' table in Supabase.")
            
        if not client_sites: st.info("💡 You have no sites marked for Client Billing. Go to Supabase -> Table Editor -> `sites` and check the 'is_client_site' box for the sites you want to invoice.")
        else:
            st.markdown("### Step 1: Select Site & Date Range")
            c1, c2, c3 = st.columns(3)
            inv_site = c1.selectbox("Select Project Site", client_sites)
            inv_start = c2.date_input("Start Date", date.today() - timedelta(days=6), format="DD-MM-YYYY")
            inv_end = c3.date_input("End Date", date.today(), format="DD-MM-YYYY")
            
            st.divider()
            
            # --- AUTO FETCH LABOR ---
            st.markdown("### Step 2: Auto-Calculated Labor")
            df_entries = fetch_data("entries")
            if not df_entries.empty:
                df_entries["date_dt"] = pd.to_datetime(df_entries["date"]).dt.date
                mask = (df_entries["site"] == inv_site) & (df_entries["date_dt"] >= inv_start) & (df_entries["date_dt"] <= inv_end)
                df_e_filtered = df_entries[mask]
                total_labor = df_e_filtered["total_cost"].sum() if not df_e_filtered.empty else 0
            else: total_labor = 0
            
            st.metric(f"Total Labor Cost for {inv_site}", f"₹{total_labor:,.2f}")
            st.divider()
            
            # --- AUTO FETCH MATERIALS ---
            st.markdown("### Step 3: Auto-Fetched Materials")
            st.caption(f"Showing materials saved to the database for **{inv_site}** between **{inv_start.strftime('%d-%m-%Y')}** and **{inv_end.strftime('%d-%m-%Y')}**.")
            
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
                    pdf_mats = df_m_filtered[["formatted_date", "Description_PDF", "amount"]].rename(columns={"formatted_date": "Date", "Description_PDF": "Description", "amount": "Amount (Rs)"})
                    total_mat = pdf_mats["Amount (Rs)"].sum()
            
            if not pdf_mats.empty:
                st.dataframe(pdf_mats, use_container_width=True, hide_index=True)
            else:
                st.info("No materials found in the database for this date range. Use the box below to add some!")
                
            st.metric("Total Material Cost", f"₹{total_mat:,.2f}")
            
            # --- ⚙️ MANAGE MATERIALS PANEL ---
            st.markdown("#### ⚙️ Manage Materials")
            tab_add, tab_edit, tab_del = st.tabs(["➕ Add Material", "✏️ Edit Material", "🗑️ Delete Material"])
            
            # 1. ADD TAB
            with tab_add:
                with st.form("quick_add_mat"):
                    c_qm1, c_qm2 = st.columns([1, 2])
                    qm_date = c_qm1.date_input("Date of Purchase", inv_end, format="DD-MM-YYYY")
                    qm_desc = c_qm2.text_input("Material Description", placeholder="e.g., Cement (50 Bags)")
                    qm_amt = st.number_input("Amount (₹)", min_value=0.0, step=100.0)
                    
                    if st.form_submit_button("Save to Database", type="primary"):
                        if qm_desc:
                            load = {
                                "date": str(qm_date), "site": inv_site, "category": "Client Billed",
                                "vendor": "Client Invoice", "material_name": qm_desc,
                                "quantity": 1, "amount": qm_amt, "receipt_url": ""
                            }
                            supabase.table("materials").insert(load).execute()
                            st.success("✅ Saved! The invoice will automatically update.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Please enter a description.")
                            
            # 2. EDIT TAB
            with tab_edit:
                if not df_m_filtered.empty:
                    edit_options = {f"{row['formatted_date']} - {row['material_name']} - ₹{row['amount']}": row for _, row in df_m_filtered.iterrows()}
                    sel_edit_key = st.selectbox("Select Material to Edit", list(edit_options.keys()))
                    sel_edit_row = edit_options[sel_edit_key]
                    
                    with st.form("edit_mat_form"):
                        c_e1, c_e2 = st.columns([1, 2])
                        edit_date_obj = pd.to_datetime(sel_edit_row["date"]).date()
                        e_date = c_e1.date_input("Update Date", edit_date_obj, format="DD-MM-YYYY")
                        e_desc = c_e2.text_input("Update Description", value=sel_edit_row["material_name"])
                        e_amt = st.number_input("Update Amount (₹)", value=float(sel_edit_row["amount"]), step=100.0)
                        
                        if st.form_submit_button("Update Material", type="primary"):
                            update_load = {
                                "date": str(e_date),
                                "material_name": e_desc,
                                "amount": e_amt
                            }
                            supabase.table("materials").update(update_load).eq("id", int(sel_edit_row["id"])).execute()
                            st.success("✅ Material Updated!")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.info("No materials available to edit in this date range.")
                    
            # 3. DELETE TAB
            with tab_del:
                if not df_m_filtered.empty:
                    del_options = {f"{row['formatted_date']} - {row['material_name']} - ₹{row['amount']}": row['id'] for _, row in df_m_filtered.iterrows()}
                    sel_del = st.selectbox("Select Material to Delete", list(del_options.keys()))
                    
                    if st.button("🗑️ Delete Selected Material", type="primary"):
                        del_id = del_options[sel_del]
                        supabase.table("materials").delete().eq("id", int(del_id)).execute()
                        st.success("✅ Material Deleted!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.info("No materials available to delete in this date range.")

            st.divider()
            
            # --- GENERATE PDF ---
            grand_total = total_labor + total_mat
            st.markdown(f"## 💰 Grand Total: ₹{grand_total:,.2f}")
            
            if st.button("📄 Generate Professional Invoice", type="primary", use_container_width=True):
                date_label = f"{inv_start.strftime('%d-%m-%Y')} to {inv_end.strftime('%d-%m-%Y')}"
                with st.spinner("Generating beautiful PDF..."):
                    pdf_bytes = generate_client_invoice_bytes(inv_site, date_label, total_labor, pdf_mats, grand_total)
                st.success("✅ Invoice Generated!")
                st.download_button(
                    label="⬇️ Download Client Invoice (PDF)", data=pdf_bytes, 
                    file_name=f"Client_Invoice_{inv_site}_{inv_start.strftime('%d%b')}.pdf", mime="application/pdf"
                )

elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    response = supabase.table("entries").select("*").order("date", desc=True).limit(500).execute()
    df_e = pd.DataFrame(response.data)
    st.caption("Showing last 500 entries.")
    if not df_e.empty:
        df_e["date_obj"] = pd.to_datetime(df_e["date"], errors='coerce')
        df_e = df_e.dropna(subset=["date_obj"])
        df_e["Date"] = df_e["date_obj"].dt.strftime('%d-%m-%Y')
        fil_site = st.selectbox("Filter Site", ["All"] + sorted(df_e["site"].unique().tolist()))
        if fil_site != "All": 
            df_e = df_e[df_e["site"] == fil_site]
            
        if "photo_url" in df_e.columns:
            df_e["Photo"] = df_e["photo_url"].apply(lambda x: "📸 Yes" if x else "No")
            cols = ["id", "Date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description", "Photo"]
        else: cols = ["id", "Date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description"]
            
        st.dataframe(df_e[cols], use_container_width=True, hide_index=True)
        st.divider()
        with st.expander("🗑️ Delete Entry"):
            col_d1, col_d2 = st.columns([1, 2])
            del_id = col_d1.number_input("ID to Delete", step=1, value=0)
            del_code = col_d2.text_input("Security Code", type="password")
            if st.button("Delete Permanently", type="primary"):
                if del_code == ADMIN_DELETE_CODE:
                    supabase.table("entries").delete().eq("id", int(del_id)).execute()
                    st.success("Deleted")
                    st.rerun()
                else: 
                    st.error("Wrong Code")
    else: 
        st.info("No logs.")

elif current_tab == "📍 Sites":
    st.subheader("📍 Sites")
    st.dataframe(fetch_data("sites"), hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        n = st.text_input("New Site Name")
        if st.button("Add Site"): 
            supabase.table("sites").insert({"name": n}).execute()
            st.rerun()
    with c2:
        if "site_ul" not in st.session_state: 
            st.session_state["site_ul"] = False
        def unlk(): 
            st.session_state["site_ul"] = True
        st.download_button("Unlock Delete (Download Backup)", data=json.dumps({"sites": fetch_data("sites").to_dict("records")}, default=str), file_name="site_bkp.json", on_click=unlk)
        d_site = st.selectbox("Delete Site", fetch_data("sites")["name"].unique()) if not fetch_data("sites").empty else None
        if st.button("Delete Site", disabled=not st.session_state["site_ul"]):
             supabase.table("sites").delete().eq("name", d_site).execute()
             st.success("Deleted")
             st.rerun()

elif current_tab == "👷 Contractors":
    st.subheader("Contractor Rates")
    df_c = fetch_data("contractors")
    st.dataframe(df_c.sort_values(by=["name", "effective_date"], ascending=[True, False]), use_container_width=True, hide_index=True)
    st.divider()
    act = st.radio("Action", ["Add New", "Update Existing"], horizontal=True)
    with st.form("c_form"):
        cn = st.selectbox("Select", df_c["name"].unique()) if act == "Update Existing" and not df_c.empty else st.text_input("Name")
        c1, c2, c3 = st.columns(3)
        rm = c1.number_input("Mason Rate", value=0)
        rh = c2.number_input("Helper Rate", value=0)
        rl = c3.number_input("Ladies Rate", value=0)
        ed = st.date_input("Effective Date", date.today())
        if st.form_submit_button("Save"):
            supabase.table("contractors").insert({
                "name": cn, "rate_mason": rm, "rate_helper": rh, "rate_ladies": rl, "effective_date": str(ed)
            }).execute()
            st.success("Saved")
            st.rerun()

elif current_tab == "👥 Users":
    st.subheader("Users")
    st.dataframe(fetch_data("users"), use_container_width=True)
    st.markdown("### ➕ Add / Update User")
    with st.form("u_add"):
        c_u1, c_u2 = st.columns(2)
        ph = c_u1.text_input("Phone (Unique ID)", max_chars=10)
        nm = c_u2.text_input("Name")
        c_u3, c_u4 = st.columns(2)
        rl = c_u3.selectbox("Role", ["user", "admin"])
        all_sites = fetch_data("sites")["name"].tolist()
        asites = c_u4.multiselect("Assigned Sites", all_sites)
        c_u5 = st.columns(1)[0]
        mpin = c_u5.text_input("Assign 4-Digit PIN", max_chars=4, value="1234")
        if st.form_submit_button("Save User"):
            site_str = ", ".join(asites) if asites else "None/All"
            if supabase.table("users").select("*").eq("phone", ph).execute().data:
                supabase.table("users").update({"name": nm, "role": rl, "assigned_site": site_str, "mpin": mpin}).eq("phone", ph).execute()
            else:
                supabase.table("users").insert({"phone": ph, "name": nm, "role": rl, "assigned_site": site_str, "status": "Active", "mpin": mpin}).execute()
            st.success("User Saved!")
            st.rerun()
            
    st.divider()
    st.markdown("### 🚪 Deactivate User")
    users = fetch_data("users")
    if not users.empty:
        active = users[(users["role"] != "admin")]
        if "status" in active.columns: 
            active = active[active["status"] != "Resigned"]
        if not active.empty:
            sel_u = st.selectbox("Select User to Resign", [f"{r['name']} ({r['phone']})" for _, r in active.iterrows()])
            deact_pass = st.text_input("Enter Security Code to Confirm", type="password", key="deact_pass")
            if st.button("Confirm Deactivation", type="primary"):
                if deact_pass == ADMIN_DELETE_CODE:
                    ph_clean = sel_u.split("(")[-1].replace(")", "")
                    supabase.table("users").update({"status": "Resigned"}).eq("phone", ph_clean).execute()
                    st.success("User deactivated")
                    st.rerun()
                else: 
                    st.error("⚠️ Wrong Security Code.")

elif current_tab == "📂 Archive & Recovery":
    st.subheader("Recovery Zone")
    t1, t2, t3 = st.tabs(["Reset Data", "View Archives (Offline)", "Restore Data"])
    
    with t1:
        st.info("Download backup to unlock reset.")
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
        st.download_button("Download Backup", data=json.dumps(bkp, default=str), file_name="full_backup.json", on_click=ul_res)
        
        c_del1, c_del2 = st.columns(2)
        conf_txt = c_del1.text_input("Type 'DELETE ALL'")
        conf_pass = c_del2.text_input("Admin Password", type="password")
        if st.button("Clear Entries", disabled=not st.session_state["reset_ul"], type="primary"):
            if conf_txt == "DELETE ALL" and conf_pass == ADMIN_DELETE_CODE:
                supabase.table("entries").delete().neq("id", 0).execute()
                st.success("Reset Complete")
                st.session_state["reset_ul"] = False
            else: 
                st.error("Wrong Code or Text")

    with t2:
        st.markdown("### 📜 View Old Data (No Restore)")
        f_view = st.file_uploader("Upload JSON to View", type=["json"], key="view_upload")
        if f_view:
            try:
                d = json.load(f_view)
                st.success("File Loaded Successfully")
                view_mode = st.radio("View Mode", ["Raw Data Tables", "Generate Weekly Bill"])
                if view_mode == "Raw Data Tables":
                    cat = st.selectbox("Category", ["Entries", "Users", "Sites", "Contractors"])
                    k_map = {"Entries": "entries", "Users": "users", "Sites": "sites", "Contractors": "contractors"}
                    if d.get(k_map[cat]): 
                        st.dataframe(pd.DataFrame(d[k_map[cat]]), use_container_width=True)
                    else: 
                        st.warning("No data found for this category.")
                elif view_mode == "Generate Weekly Bill":
                    st.info("Generating bill from uploaded backup file...")
                    if d.get("entries") and d.get("contractors"):
                        ae = pd.DataFrame(d["entries"])
                        ac = pd.DataFrame(d["contractors"])
                        render_weekly_bill(ae, ac)
                    else: 
                        st.error("Backup file missing entries or contractors data.")
            except Exception as e: 
                st.error(f"Error reading file: {e}")

    with t3:
        f = st.file_uploader("Upload Backup JSON to Restore", key="res_up")
        res_pass = st.text_input("Restore Password", type="password")
        if f and st.button("Restore Now", type="primary"):
            if res_pass == ADMIN_DELETE_CODE:
                d = json.load(f)
                st.write("Restoring...")
                try:
                    def clean(r): return [{k:v for k,v in x.items() if k!='id'} for x in r]
                    if d.get("sites"): supabase.table("sites").upsert(clean(d["sites"]), on_conflict="name").execute()
                    if d.get("users"): supabase.table("users").upsert(clean(d["users"]), on_conflict="phone").execute()
                    if d.get("contractors"): supabase.table("contractors").upsert(clean(d["contractors"])).execute()
                    if d.get("entries"): 
                        ent = clean(d["entries"])
                        for i in range(0, len(ent), 50): 
                            supabase.table("entries").insert(ent[i:i+50]).execute()
                    st.success("Restored Successfully!")
                except Exception as e: 
                    st.error(f"Error: {e}")
            else: 
                st.error("Wrong Password")