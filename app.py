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
    # ttl=3600 refreshes the connection every hour to prevent "ReadError"
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
# We do NOT cache this because it mounts a component (widget)
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- 4. CUSTOM STYLING ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* Force ALL Text to Black */
        * { color: #000000 !important; }
        .stApp { background-color: #FFFFFF !important; }
        
        /* Sidebar Styling */
        section[data-testid="stSidebar"] { background-color: #F8F9FA !important; border-right: 1px solid #E0E0E0; }
        section[data-testid="stSidebar"] * { color: #000000 !important; }
        
        /* Inputs, Tables, Select Boxes */
        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important; 
            color: #000000 !important; 
            border: 1px solid #ccc !important; 
        }
        /* MultiSelect Tag Styling */
        span[data-baseweb="tag"] {
            background-color: #E0E0E0 !important;
            color: black !important;
        }

        div[data-testid="stDataFrame"], div[data-testid="stTable"] {
            color: #000000 !important; 
            background-color: #FFFFFF !important;
        }
        
        /* Table Headers & Cells */
        th { background-color: #E0E0E0 !important; border-bottom: 2px solid #000 !important; }
        td { border-bottom: 1px solid #ddd !important; }
        
        /* Buttons */
        button[kind="primary"] { 
            background-color: #F39C12 !important; 
            color: #FFFFFF !important; 
            border: none !important; 
        }
        button[disabled] { 
            background-color: #cccccc !important; 
            color: #666666 !important; 
            cursor: not-allowed; 
        }
        
        /* Metrics Styling */
        div[data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
            color: #F39C12 !important;
        }
        div[data-testid="stMetricLabel"] {
             font-size: 1rem !important;
             color: #333333 !important;
        }
        
        /* Mobile Adjustments */
        @media only screen and (max-width: 600px) {
            h1 { font-size: 1.8rem !important; }
            .stButton button { width: 100% !important; }
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_styling()

# --- 5. HELPER FUNCTIONS & PDF ENGINE ---
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

def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty: 
        st.info("No data available.")
        return
    
    # 1. Prepare Data
    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors='coerce')
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"], errors='coerce').dt.date
    df_entries = df_entries.dropna(subset=["date_dt"])
    
    # 2. Calculate Billing Weeks
    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
    
    # 3. Week Selector
    weeks = sorted(df_entries["week_label"].unique(), reverse=True)
    sel_week = st.selectbox("Select Week", weeks) if weeks else None
    
    if not sel_week: 
        return

    # Filter Data
    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    week_start_obj = df_week.iloc[0]["start_date"]
    full_week_dates = [week_start_obj + timedelta(days=i) for i in range(7)] 
    
    # 4. Independent Tabs
    tab_site, tab_con = st.tabs(["🏢 View by Site", "👷 View by Contractor"])
    
    # --- TAB 1: SITE VIEW ---
    with tab_site:
        all_sites = sorted(df_week["site"].unique())
        sel_site = st.selectbox("Select Site", all_sites, key="sb_site")
        
        if sel_site:
            st.divider()
            st.markdown(f"### 📍 Site: {sel_site}")
            
            df_view = df_week[df_week["site"] == sel_site]
            pdf_data = []

            for con_name in df_view["contractor"].unique():
                df_sub = df_view[df_view["contractor"] == con_name]
                entry_map = {d.date(): r for d, r in zip(df_sub["date_dt"], df_sub.to_dict('records'))}
                
                rows = []
                tm, th, tl, tamt = 0, 0, 0, 0
                
                for day_date in full_week_dates:
                    if day_date in entry_map:
                        r = entry_map[day_date]
                        m, h, l, c = r["count_mason"], r["count_helper"], r["count_ladies"], r["total_cost"]
                        
                        if m == 0 and h == 0 and l == 0:
                            dm, dh, dl = "Nil", "Nil", "Nil"
                        else:
                            dm, dh, dl = str(m), str(h), str(l)
                    else:
                        m, h, l, c = 0, 0, 0, 0
                        dm, dh, dl = "0", "0", "0"
                    
                    rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
                    tm += m
                    th += h
                    tl += l
                    tamt += c
                
                rates = df_contractors[df_contractors["name"] == con_name].sort_values("effective_date", ascending=False)
                rm, rh, rl = (0,0,0)
                if not rates.empty:
                    valid_rates = rates[rates["effective_date"] <= week_start_obj]
                    curr = valid_rates.iloc[0] if not valid_rates.empty else rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]

                pdf_data.append({"name": con_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

                st.markdown(f"#### 👷 {con_name}")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("💰 Payable", f"₹{tamt:,.0f}")
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

    # --- TAB 2: CONTRACTOR VIEW ---
    with tab_con:
        all_cons = sorted(df_week["contractor"].unique())
        sel_con = st.selectbox("Select Contractor", all_cons, key="sb_con")
        
        if sel_con:
            st.divider()
            st.markdown(f"### 👷 Contractor: {sel_con}")
            
            df_view = df_week[df_week["contractor"] == sel_con]
            pdf_data = []

            for site_name in df_view["site"].unique():
                df_sub = df_view[df_view["site"] == site_name]
                entry_map = {d.date(): r for d, r in zip(df_sub["date_dt"], df_sub.to_dict('records'))}
                
                rows = []
                tm, th, tl, tamt = 0, 0, 0, 0
                
                for day_date in full_week_dates:
                    if day_date in entry_map:
                        r = entry_map[day_date]
                        m, h, l, c = r["count_mason"], r["count_helper"], r["count_ladies"], r["total_cost"]
                        
                        if m == 0 and h == 0 and l == 0:
                            dm, dh, dl = "Nil", "Nil", "Nil"
                        else:
                            dm, dh, dl = str(m), str(h), str(l)
                    else:
                        m, h, l, c = 0, 0, 0, 0
                        dm, dh, dl = "0", "0", "0"
                    
                    rows.append({"Date": day_date.strftime("%d-%m-%Y"), "Mason": dm, "Helper": dh, "Ladies": dl})
                    tm += m
                    th += h
                    tl += l
                    tamt += c
                
                rates = df_contractors[df_contractors["name"] == sel_con].sort_values("effective_date", ascending=False)
                rm, rh, rl = (0,0,0)
                if not rates.empty:
                    valid_rates = rates[rates["effective_date"] <= week_start_obj]
                    curr = valid_rates.iloc[0] if not valid_rates.empty else rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]

                pdf_data.append({"name": site_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

                st.markdown(f"#### 📍 {site_name}")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("💰 Payable", f"₹{tamt:,.0f}")
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

# --- 6. AUTO-LOGIN CHECK (Run before Login Page) ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

# Check Cookie
time.sleep(0.1) # Give cookie manager a split second
stored_token = cookie_manager.get("auth_token")

if not st.session_state["logged_in"] and stored_token:
    try:
        # Check if this token matches the one in DB
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
            # Token invalid or logged in elsewhere -> Clear cookie
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
        
        # --- TEAM LOGIN ---
        st.subheader("👷 Team Login")
        with st.form("u_log"):
            ph = st.text_input("Enter Mobile Number", max_chars=10, placeholder="9876543210")
            
            if st.form_submit_button("🚀 Login", type="primary", use_container_width=True):
                if ph:
                    try:
                        response = supabase.table("users").select("*").eq("phone", ph).execute()
                        
                        if not response.data:
                            st.error("❌ User not found.")
                        else:
                            user = response.data[0]
                            if user.get("status") == "Resigned":
                                st.error("⛔ Account Deactivated.")
                            elif user.get("role") == "admin":
                                st.error("⚠️ Admins: Please use the 'Admin Login' below.")
                            else:
                                # GENERATE NEW SESSION TOKEN
                                new_token = str(uuid.uuid4())
                                
                                # 1. Update DB (This invalidates any old sessions elsewhere)
                                supabase.table("users").update({"session_token": new_token}).eq("phone", ph).execute()
                                
                                # 2. Set Cookie (Expires in 30 days)
                                cookie_manager.set("auth_token", new_token, expires_at=datetime.now() + timedelta(days=30))
                                
                                # 3. Set Session State
                                st.session_state.update({
                                    "logged_in": True, 
                                    "phone": user["phone"], 
                                    "role": "user",
                                    "user_name": user["name"],
                                    "assigned_site": user.get("assigned_site", "All")
                                })
                                st.success("Logged In!")
                                time.sleep(1) # Wait for cookie to set
                                st.rerun()
                    except Exception as e:
                        st.warning("⚠️ Connection error. Try again.")
                else:
                    st.warning("Please enter a phone number.")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- ADMIN LOGIN ---
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
                                
                                # GENERATE NEW TOKEN
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

# --- 8. LOGOUT LOGIC (FIXED) ---
with st.sidebar:
    st.info(f"Role: **{st.session_state['role'].upper()}**")
    if st.button("Logout"):
        # 1. Clear DB token first (Crucial for Sync)
        if st.session_state.get("phone"):
            try:
                supabase.table("users").update({"session_token": None}).eq("phone", st.session_state["phone"]).execute()
            except: 
                pass
        
        # 2. Delete Cookie (Wrapped in Try/Except to prevent KeyError)
        try:
            cookie_manager.delete("auth_token")
        except KeyError:
            pass # Cookie already gone, safe to proceed
        
        # 3. Clear State
        st.session_state.clear()
        
        # 4. Wait for browser to process deletion
        time.sleep(1)
        
        # 5. Rerun
        st.rerun()

# --- 9. MAIN APP NAVIGATION ---
tabs = ["📝 Daily Entry"]
if st.session_state["role"] == "admin": 
    tabs += ["🔍 Site Logs", "📊 Weekly Bill", "📍 Sites", "👷 Contractors", "👥 Users", "📂 Archive & Recovery"]

current_tab = st.selectbox("Navigate", tabs, label_visibility="collapsed")
st.divider()

# TAB 1: DAILY ENTRY
if current_tab == "📝 Daily Entry":
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")
    
    if df_sites.empty: 
        st.warning("Admin must add sites.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        
        # LOGIC FOR MULTIPLE ASSIGNED SITES
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
            
            # NIL ENTRY LOGIC
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
                load = {
                    "date": str(dt), 
                    "site": st_sel, 
                    "contractor": con_sel, 
                    "count_mason": nm, 
                    "count_helper": nh, 
                    "count_ladies": nl, 
                    "total_cost": cost, 
                    "work_description": wdesc
                }
                try:
                    if mode == "new": 
                        supabase.table("entries").insert(load).execute()
                    else: 
                        supabase.table("entries").update(load).eq("id", exist["id"]).execute()
                    
                    st.success("✅ Saved Successfully!")
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
                st.dataframe(df_recent[["date", "site", "contractor", "total_cost", "work_description"]], use_container_width=True)
        except: 
            pass

# TAB 2: SITE LOGS
elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    response = supabase.table("entries").select("*").order("date", desc=True).limit(500).execute()
    df_e = pd.DataFrame(response.data)
    
    st.caption("Showing last 500 entries only. Use 'Weekly Bill' for full history.")
    
    if not df_e.empty:
        df_e["date_obj"] = pd.to_datetime(df_e["date"], errors='coerce')
        df_e = df_e.dropna(subset=["date_obj"])
        df_e["Date"] = df_e["date_obj"].dt.strftime('%d-%m-%Y')
        
        fil_site = st.selectbox("Filter Site", ["All"] + sorted(df_e["site"].unique().tolist()))
        if fil_site != "All": 
            df_e = df_e[df_e["site"] == fil_site]
            
        st.dataframe(df_e[["id", "Date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description"]], use_container_width=True, hide_index=True)
        
        if st.session_state["role"] == "admin":
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

# TAB 3: BILLING
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill")
    try:
        start_of_year = f"{date.today().year}-01-01"
        response = supabase.table("entries").select("*").gte("date", start_of_year).execute()
        df_entries = pd.DataFrame(response.data)
    except:
        df_entries = fetch_data("entries")
        
    render_weekly_bill(df_entries, fetch_data("contractors"))

# TAB 4: SITE MANAGEMENT
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

# TAB 5: CONTRACTORS
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
                "name": cn, 
                "rate_mason": rm, 
                "rate_helper": rh, 
                "rate_ladies": rl, 
                "effective_date": str(ed)
            }).execute()
            st.success("Saved")
            st.rerun()

# TAB 6: USERS
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
        
        if st.form_submit_button("Save User"):
            site_str = ", ".join(asites) if asites else "None/All"
            
            # Check if user exists
            if supabase.table("users").select("*").eq("phone", ph).execute().data:
                supabase.table("users").update({
                    "name": nm, 
                    "role": rl, 
                    "assigned_site": site_str
                }).eq("phone", ph).execute()
            else:
                supabase.table("users").insert({
                    "phone": ph, 
                    "name": nm, 
                    "role": rl, 
                    "assigned_site": site_str, 
                    "status": "Active"
                }).execute()
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

# TAB 7: ARCHIVE & RECOVERY
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