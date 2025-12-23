import streamlit as st
import pandas as pd
import json
from datetime import datetime, date, timedelta
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="LabourPro", page_icon="🏗️", layout="wide")

# Try to get password from secrets, otherwise default to admin123 (Only for testing!)
try:
    ADMIN_PASSWORD = st.secrets["general"]["admin_password"]
except:
    ADMIN_PASSWORD = "admin123"

# --- 2. CONNECT TO SUPABASE ---
try:
    @st.cache_resource
    def init_connection():
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    supabase = init_connection()
except Exception:
    st.error("⚠️ Supabase connection failed. Check secrets.toml.")
    st.stop()

# --- 3. CUSTOM STYLING (THEME & DESIGN) ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* IMPORT FONT */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

        /* MAIN BACKGROUND & TEXT */
        .stApp {
            background-color: #F4F6F9; /* Light Grey Background */
            font-family: 'Inter', sans-serif;
        }
        
        /* HEADINGS */
        h1, h2, h3 {
            color: #2C3E50; /* Dark Blue */
            font-weight: 600;
        }

        /* CARDS (CONTAINERS) */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            background-color: #FFFFFF;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border: 1px solid #E0E0E0;
        }

        /* PRIMARY BUTTONS (ORANGE) */
        div.stButton > button[kind="primary"] {
            background-color: #F39C12;
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #D68910;
            box-shadow: 0 4px 8px rgba(243, 156, 18, 0.3);
        }

        /* SECONDARY BUTTONS (Standard) */
        div.stButton > button[kind="secondary"] {
            background-color: #ECF0F1;
            color: #2C3E50;
            border: 1px solid #BDC3C7;
            border-radius: 8px;
        }
        
        /* INPUT FIELDS */
        .stTextInput input, .stNumberInput input, .stSelectbox div[data-testid="stMarkdownContainer"] {
            color: #2C3E50;
        }
        div[data-baseweb="input"] {
            border-radius: 8px;
            border: 1px solid #D0D3D4;
            background-color: #FFFFFF;
        }
        
        /* METRICS */
        [data-testid="stMetricValue"] {
            color: #2980B9; /* Blue numbers */
        }
        
        /* HIDE DEFAULT MENU */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        </style>
    """, unsafe_allow_html=True)

apply_custom_styling()

# --- 4. HELPER FUNCTIONS ---
def fetch_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def get_billing_start_date(entry_date):
    """Calculates the Saturday that started the billing week."""
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

def calculate_split_costs(df_e, df_c):
    if df_e.empty or df_c.empty: return df_e
    df_c = df_c.copy()
    df_c["effective_date"] = pd.to_datetime(df_c["effective_date"]).dt.date
    
    m_costs, h_costs, l_costs = [], [], []
    for index, row in df_e.iterrows():
        rates = df_c[(df_c["name"] == row["contractor"]) & (df_c["effective_date"] <= row["date"])].sort_values("effective_date", ascending=False)
        if not rates.empty:
            rate = rates.iloc[0]
            m_costs.append(row["count_mason"] * rate["rate_mason"])
            h_costs.append(row["count_helper"] * rate["rate_helper"])
            l_costs.append(row["count_ladies"] * rate["rate_ladies"])
        else:
            m_costs.append(0); h_costs.append(0); l_costs.append(0)
    df_e["amt_mason"] = m_costs; df_e["amt_helper"] = h_costs; df_e["amt_ladies"] = l_costs
    return df_e

# --- 5. LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏗️ LabourPro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: grey;'>Secure Construction Management System</p>", unsafe_allow_html=True)
        
        st.divider()
        
        login_type = st.radio("Select Login Type:", ["User Login", "Admin Login"], horizontal=True)

        if login_type == "User Login":
            with st.form("user_login"):
                phone = st.text_input("Enter Mobile Number", max_chars=10).strip()
                submitted = st.form_submit_button("Login", type="primary")
                if submitted:
                    if not phone: st.error("Please enter a mobile number.")
                    else:
                        try:
                            data = supabase.table("users").select("*").eq("phone", phone).execute().data
                            if data:
                                user = data[0]
                                if user.get("role") == "admin": st.warning("Admins should use the 'Admin Login' tab.")
                                else:
                                    st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                                    st.rerun()
                            else: st.error("❌ Number not found.")
                        except Exception as e: st.error(f"Connection Error: {e}")

        elif login_type == "Admin Login":
            with st.form("admin_login"):
                phone = st.text_input("Admin Mobile Number", max_chars=10).strip()
                password = st.text_input("Admin Password", type="password")
                submitted = st.form_submit_button("Login as Admin", type="primary")
                if submitted:
                    if password != ADMIN_PASSWORD: st.error("❌ Incorrect Password")
                    else:
                        try:
                            data = supabase.table("users").select("*").eq("phone", phone).execute().data
                            if data and data[0].get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": data[0]["phone"], "role": "admin"})
                                st.rerun()
                            else: st.error("⛔ No Admin privileges.")
                        except Exception as e: st.error(f"Connection Error: {e}")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 6. MAIN APP INTERFACE ---
with st.sidebar:
    st.markdown("### 👤 Profile")
    my_role = st.session_state.get("role", "user")
    my_phone = st.session_state.get("phone")
    st.info(f"Role: **{my_role.upper()}**")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏗️ Labour Management Pro")

tabs = ["📝 Daily Entry"]
if my_role == "admin":
    tabs += ["🔍 Site Logs", "📊 Weekly Bill", "💰 Payment Summary", "📍 Sites", "👷 Contractors", "👥 Users", "💾 Backup & Restore"]

current_tab = st.selectbox("Navigate", tabs, label_visibility="collapsed")
st.divider()

# ==========================
# 1. DAILY ENTRY
# ==========================
if current_tab == "📝 Daily Entry":
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")

    if df_sites.empty or df_con.empty:
        st.warning("⚠️ Admin must add Sites and Contractors first.")
    else:
        available_sites = df_sites["name"].unique().tolist()
        if my_role != "admin":
            try:
                user_profile = supabase.table("users").select("assigned_site").eq("phone", my_phone).single().execute()
                assigned_site = user_profile.data.get("assigned_site")
                if assigned_site and assigned_site in available_sites: available_sites = [assigned_site]
                else: st.error("⛔ Site not assigned."); st.stop()
            except: st.stop()

        with st.container():
            st.subheader("📝 New Work Entry")
            c1, c2, c3 = st.columns(3)
            entry_date = c1.date_input("Date", date.today(), format="DD/MM/YYYY")
            site = c2.selectbox("Site", available_sites) 
            contractor = c3.selectbox("Contractor", df_con["name"].unique())
            
            st.divider()
            
            # Check existing
            existing_entry = None
            try:
                resp = supabase.table("entries").select("*").eq("date", str(entry_date)).eq("site", site).eq("contractor", contractor).execute()
                if resp.data: existing_entry = resp.data[0]
            except: pass

            mode = "new"
            current_edits, val_m, val_h, val_l, val_desc = 0, 0.0, 0.0, 0.0, ""

            if existing_entry:
                mode = "edit"
                current_edits = existing_entry.get("edit_count", 0)
                val_m = float(existing_entry.get("count_mason", 0))
                val_h = float(existing_entry.get("count_helper", 0))
                val_l = float(existing_entry.get("count_ladies", 0))
                val_desc = existing_entry.get("work_description", "")
                
                if current_edits >= 2: st.error("⛔ Entry Locked (Max edits reached)."); st.stop()
                else: st.warning(f"✏️ Edit Mode (Used: {current_edits}/2)")

            k1, k2, k3 = st.columns(3)
            n_mason = k1.number_input("🧱 Masons", min_value=0.0, step=0.5, value=val_m, format="%.1f")
            n_helper = k2.number_input("👷 Helpers", min_value=0.0, step=0.5, value=val_h, format="%.1f")
            n_ladies = k3.number_input("👩 Ladies", min_value=0.0, step=0.5, value=val_l, format="%.1f")
            
            work_desc = st.text_area("Work Description", value=val_desc, placeholder="e.g. Plastering 2nd floor...")

            rate_row = None
            try:
                resp = supabase.table("contractors").select("*").eq("name", contractor).lte("effective_date", str(entry_date)).order("effective_date", desc=True).limit(1).execute()
                if resp.data: rate_row = resp.data[0]
            except: pass

            if rate_row:
                total_est = (n_mason * rate_row['rate_mason']) + (n_helper * rate_row['rate_helper']) + (n_ladies * rate_row['rate_ladies'])
                if my_role == "admin": st.info(f"💰 **Estimated Cost: ₹{total_est:,.2f}**")

                btn_text = "✅ Save Entry" if mode == "new" else "🔄 Update Entry"
                if st.button(btn_text, type="primary"):
                    if total_est > 0 or work_desc.strip() != "":
                        payload = {
                            "date": str(entry_date), "site": site, "contractor": contractor,
                            "count_mason": n_mason, "count_helper": n_helper, "count_ladies": n_ladies,
                            "total_cost": total_est, "work_description": work_desc
                        }
                        if mode == "new":
                            payload["edit_count"] = 0
                            supabase.table("entries").insert(payload).execute()
                            st.success("Saved!")
                        else:
                            if not existing_entry.get("original_values"):
                                snapshot = f"M:{existing_entry['count_mason']} H:{existing_entry['count_helper']} L:{existing_entry['count_ladies']} (₹{existing_entry['total_cost']})"
                                payload["original_values"] = snapshot
                            payload["edit_count"] = current_edits + 1
                            supabase.table("entries").update(payload).eq("id", existing_entry["id"]).execute()
                            st.success("Updated!")
                        st.rerun()
                    else: st.error("Enter counts or description.")
            else: st.error("⚠️ No active rates found.")

# ==========================
# 2. SITE LOGS
# ==========================
elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    df_sites = fetch_data("sites")
    if not df_sites.empty:
        sel_site = st.selectbox("Select Site", ["All Sites"] + df_sites["name"].unique().tolist())
        raw = supabase.table("entries").select("*").order("date", desc=True).execute().data
        df_log = pd.DataFrame(raw)
        
        if not df_log.empty:
            if sel_site != "All Sites": df_log = df_log[df_log["site"] == sel_site]
            
            df_log["date"] = pd.to_datetime(df_log["date"])
            df_log["Date"] = df_log["date"].dt.strftime('%d-%m-%Y')
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Spend", f"₹{df_log['total_cost'].sum():,.0f}")
            m2.metric("Entries", len(df_log))
            m3.metric("Contractors", df_log["contractor"].nunique())

            st.dataframe(
                df_log[["Date", "site", "contractor", "work_description", "total_cost"]], 
                use_container_width=True, hide_index=True
            )
        else: st.info("No logs found.")

# ==========================
# 3. WEEKLY BILL
# ==========================
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill Report")
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    
    if not df_e.empty:
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        if not df_c.empty: df_e = calculate_split_costs(df_e, df_c)
        
        df_e["start_date"] = df_e["date"].apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        df_e["Period"] = df_e.apply(lambda x: f"{x['start_date'].strftime('%d-%m')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
        
        report = df_e.groupby(["Period", "contractor", "site"])[["total_cost", "amt_mason", "amt_helper", "amt_ladies"]].sum().reset_index()
        
        st.dataframe(report, use_container_width=True, hide_index=True)
        
        csv = report.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "weekly_bill.csv", "text/csv", type="primary")

# ==========================
# 4. PAYMENT SUMMARY
# ==========================
elif current_tab == "💰 Payment Summary":
    st.subheader("💰 Weekly Payment Dashboard")
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    
    if not df_e.empty:
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        if not df_c.empty: df_e = calculate_split_costs(df_e, df_c)
        df_e["start"] = df_e["date"].apply(get_billing_start_date)
        df_e["Period"] = df_e.apply(lambda x: f"{x['start'].strftime('%d-%m-%Y')} Week", axis=1)
        
        weeks = df_e["Period"].unique()
        for wk in weeks:
            with st.expander(f"🗓️ {wk}", expanded=True):
                wk_data = df_e[df_e["Period"] == wk]
                summ = wk_data.groupby("contractor")["total_cost"].sum().reset_index()
                st.dataframe(summ, use_container_width=True, hide_index=True)

# ==========================
# 5. SITES & CONTRACTORS & USERS
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Manage Sites")
    df = fetch_data("sites")
    st.dataframe(df, hide_index=True, use_container_width=True)
    new = st.text_input("New Site Name")
    if st.button("Add Site", type="primary"):
        if new: supabase.table("sites").insert({"name": new}).execute(); st.success("Added"); st.rerun()

elif current_tab == "👷 Contractors":
    st.subheader("👷 Manage Contractors")
    df = fetch_data("contractors")
    st.dataframe(df, use_container_width=True)
    with st.form("add_con"):
        n = st.text_input("Name")
        c1, c2, c3 = st.columns(3)
        r1 = c1.number_input("Mason Rate", value=800)
        r2 = c2.number_input("Helper Rate", value=500)
        r3 = c3.number_input("Ladies Rate", value=400)
        d = st.date_input("Effective Date", date.today())
        if st.form_submit_button("Save Contractor", type="primary"):
            supabase.table("contractors").insert({"name": n, "rate_mason": r1, "rate_helper": r2, "rate_ladies": r3, "effective_date": str(d)}).execute()
            st.success("Saved"); st.rerun()

elif current_tab == "👥 Users":
    st.subheader("👥 User Access")
    df = fetch_data("users")
    st.dataframe(df, use_container_width=True)
    with st.form("add_user"):
        ph = st.text_input("Phone")
        nm = st.text_input("Name")
        rl = st.selectbox("Role", ["user", "admin"])
        site_opts = fetch_data("sites")["name"].tolist() if not fetch_data("sites").empty else []
        st_as = st.selectbox("Assign Site", ["None/All"] + site_opts)
        if st.form_submit_button("Save User", type="primary"):
            sv = None if st_as == "None/All" else st_as
            # Check exist
            ext = supabase.table("users").select("*").eq("phone", ph).execute().data
            if ext: supabase.table("users").update({"name": nm, "role": rl, "assigned_site": sv}).eq("phone", ph).execute()
            else: supabase.table("users").insert({"phone": ph, "name": nm, "role": rl, "assigned_site": sv}).execute()
            st.success("Saved"); st.rerun()

# ==========================
# 8. BACKUP & RESTORE (SAFE MODE)
# ==========================
elif current_tab == "💾 Backup & Restore":
    st.subheader("💾 Data Management")
    if "backup_downloaded" not in st.session_state: st.session_state["backup_downloaded"] = False

    t1, t2, t3 = st.tabs(["📤 Backup", "📅 Start New Year", "📂 Archive Viewer"])
    
    with t1:
        st.info("Download a full backup of your system.")
        if st.button("Generate Backup"):
            data = {
                "entries": fetch_data("entries").to_dict("records"),
                "contractors": fetch_data("contractors").to_dict("records"),
                "sites": fetch_data("sites").to_dict("records"),
                "users": fetch_data("users").to_dict("records"),
                "date": str(datetime.now())
            }
            st.download_button("📥 Download JSON", json.dumps(data, indent=4, default=str), f"backup_{date.today()}.json", "application/json", type="primary")

    with t2:
        st.write("### 📅 Fiscal Year Reset")
        st.markdown("**1. Download Backup first to unlock the delete button.**")
        
        # Auto-prepare data for the lock check
        full_data = {
            "entries": fetch_data("entries").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "users": fetch_data("users").to_dict("records"),
            "type": "YearEndBackup"
        }
        
        def unlock(): st.session_state["backup_downloaded"] = True
        
        st.download_button(
            "1️⃣ Download Backup to Unlock", 
            json.dumps(full_data, indent=4, default=str), 
            f"YearEnd_Backup_{date.today()}.json", 
            "application/json", 
            type="primary", 
            on_click=unlock
        )
        
        st.divider()
        
        if st.session_state["backup_downloaded"]:
            st.warning("⚠️ **Warning:** This will delete all daily work entries. Contractors & Sites will remain.")
            confirm = st.checkbox("I confirm I want to start fresh.")
            if st.button("2️⃣ 🔴 Clear Data & Start New Year", type="primary", disabled=not confirm):
                supabase.table("entries").delete().neq("id", 0).execute()
                st.balloons()
                st.success("New Year Started!")
                st.session_state["backup_downloaded"] = False
        else:
            st.info("🚫 'Start Fresh' button is locked.")

    with t3:
        st.write("### 📂 Archive Viewer")
        f = st.file_uploader("Upload Old Backup JSON", type=["json"])
        if f:
            d = json.load(f)
            if "entries" in d:
                adf = pd.DataFrame(d["entries"])
                if not adf.empty:
                    adf["date"] = pd.to_datetime(adf["date"])
                    st.success(f"Loaded {len(adf)} entries.")
                    st.dataframe(adf[["date", "site", "contractor", "total_cost", "work_description"]])