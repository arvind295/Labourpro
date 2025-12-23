import streamlit as st
import pandas as pd
import json
from datetime import datetime, date, timedelta
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="LabourPro", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

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

# --- 3. CUSTOM STYLING (THE "NUCLEAR" TEXT FIX) ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* --- GLOBAL TEXT RESET --- */
        html, body, [class*="css"] {
            font-family: sans-serif;
            color: #000000 !important; /* Force ALL text black */
        }
        
        .stApp {
            background-color: #FFFFFF !important;
        }

        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] {
            background-color: #F8F9FA !important;
            border-right: 1px solid #E0E0E0;
        }
        [data-testid="stSidebar"] * {
            color: #000000 !important; /* Force Sidebar text black */
        }

        /* --- INPUTS & LABELS (The Critical Fix) --- */
        
        /* 1. Labels above inputs */
        .stTextInput label, .stNumberInput label, .stSelectbox label, .stDateInput label {
            color: #000000 !important;
            font-weight: 600 !important;
        }
        
        /* 2. The Input Box Container */
        div[data-baseweb="input"], div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border: 1px solid #888 !important; /* Darker border for visibility */
            color: #000000 !important;
        }

        /* 3. The Actual Typing Text */
        input[type="text"], input[type="number"], input[type="password"] {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            caret-color: #000000 !important;
        }

        /* 4. Placeholder Text (e.g. 'Enter mobile...') */
        ::placeholder {
            color: #666666 !important;
            opacity: 1 !important;
        }
        
        /* --- DROPDOWNS --- */
        div[data-baseweb="popover"] {
            background-color: #FFFFFF !important;
        }
        li[role="option"] {
            color: #000000 !important;
        }
        li[role="option"]:hover {
            background-color: #FFE0B2 !important;
        }

        /* --- METRICS & TABLES --- */
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
            color: #000000 !important;
        }
        
        div[data-testid="stTable"] *, div[data-testid="stDataFrame"] * {
            color: #000000 !important;
            background-color: #FFFFFF !important;
        }
        th {
            background-color: #E0E0E0 !important;
            color: #000000 !important;
        }

        /* --- BUTTONS --- */
        div.stButton > button[kind="primary"] {
            background-color: #F39C12 !important;
            color: white !important;
            border: none;
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_styling()

# --- 4. HELPER FUNCTIONS ---
def fetch_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def get_billing_start_date(entry_date):
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

# --- 5. LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: black;'>🏗️ LabourPro</h1>", unsafe_allow_html=True)
        st.divider()
        
        login_type = st.radio("Select Login Type:", ["User Login", "Admin Login"], horizontal=True)

        if login_type == "User Login":
            with st.form("user_login"):
                # Explicit label color not needed due to global CSS, but adding for safety
                st.markdown("<p style='color:black;'>Enter Mobile Number</p>", unsafe_allow_html=True)
                phone = st.text_input("Mobile", label_visibility="collapsed", max_chars=10).strip()
                submitted = st.form_submit_button("Login", type="primary")
                if submitted:
                    if not phone: st.error("Please enter a mobile number.")
                    else:
                        try:
                            data = supabase.table("users").select("*").eq("phone", phone).execute().data
                            if data:
                                user = data[0]
                                if user.get("role") == "admin": st.warning("Admins use Admin Login.")
                                else:
                                    st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                                    st.rerun()
                            else: st.error("❌ Number not found.")
                        except: st.error("Connection Error.")

        elif login_type == "Admin Login":
            with st.form("admin_login"):
                st.markdown("<p style='color:black;'>Admin Mobile Number</p>", unsafe_allow_html=True)
                phone = st.text_input("Admin Mobile", label_visibility="collapsed").strip()
                
                st.markdown("<p style='color:black;'>Password</p>", unsafe_allow_html=True)
                password = st.text_input("Password", type="password", label_visibility="collapsed")
                
                submitted = st.form_submit_button("Login as Admin", type="primary")
                if submitted:
                    real_admin_pass = st.secrets["general"]["admin_password"] if "general" in st.secrets else "admin123"
                    if password != real_admin_pass: st.error("❌ Incorrect Password")
                    else:
                        try:
                            data = supabase.table("users").select("*").eq("phone", phone).execute().data
                            if data and data[0].get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": data[0]["phone"], "role": "admin"})
                                st.rerun()
                            else: st.error("⛔ No Admin privileges.")
                        except: st.error("Connection Error.")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 6. MAIN APP INTERFACE ---
with st.sidebar:
    st.markdown("### 👤 Profile")
    my_role = st.session_state.get("role", "user")
    st.info(f"Role: **{my_role.upper()}**")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏗️ Labour Management Pro")

tabs = ["📝 Daily Entry"]
if my_role == "admin":
    tabs += ["🔍 Site Logs", "📊 Weekly Bill", "📍 Sites", "👷 Contractors", "👥 Users", "💾 Backup"]

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
                user_profile = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
                assigned_site = user_profile.data.get("assigned_site")
                if assigned_site and assigned_site in available_sites: available_sites = [assigned_site]
                else: st.error("⛔ Site not assigned."); st.stop()
            except: st.stop()

        st.subheader("📝 New Work Entry")
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date", date.today(), format="DD/MM/YYYY")
        site = c2.selectbox("Site", available_sites) 
        contractor = c3.selectbox("Contractor", df_con["name"].unique())
        
        # Check existing
        existing_entry = None
        try:
            resp = supabase.table("entries").select("*").eq("date", str(entry_date)).eq("site", site).eq("contractor", contractor).execute()
            if resp.data: existing_entry = resp.data[0]
        except: pass

        val_m, val_h, val_l, val_desc = 0.0, 0.0, 0.0, ""
        mode = "new"
        
        if existing_entry:
            mode = "edit"
            val_m = float(existing_entry.get("count_mason", 0))
            val_h = float(existing_entry.get("count_helper", 0))
            val_l = float(existing_entry.get("count_ladies", 0))
            val_desc = existing_entry.get("work_description", "")
            st.warning(f"✏️ Editing Existing Entry")

        st.divider()
        k1, k2, k3 = st.columns(3)
        n_mason = k1.number_input("🧱 Masons", min_value=0.0, step=0.5, value=val_m)
        n_helper = k2.number_input("👷 Helpers", min_value=0.0, step=0.5, value=val_h)
        n_ladies = k3.number_input("👩 Ladies", min_value=0.0, step=0.5, value=val_l)
        
        work_desc = st.text_area("Work Description", value=val_desc, placeholder="e.g. Plastering 2nd floor...")

        rate_row = None
        try:
            resp = supabase.table("contractors").select("*").eq("name", contractor).lte("effective_date", str(entry_date)).order("effective_date", desc=True).limit(1).execute()
            if resp.data: rate_row = resp.data[0]
        except: pass

        if rate_row:
            total_est = (n_mason * rate_row['rate_mason']) + (n_helper * rate_row['rate_helper']) + (n_ladies * rate_row['rate_ladies'])
            st.info(f"💰 **Estimated Cost: ₹{total_est:,.2f}**")

            if st.button("✅ Save Entry" if mode == "new" else "🔄 Update Entry", type="primary"):
                if total_est > 0 or work_desc.strip() != "":
                    payload = {
                        "date": str(entry_date), "site": site, "contractor": contractor,
                        "count_mason": n_mason, "count_helper": n_helper, "count_ladies": n_ladies,
                        "total_cost": total_est, "work_description": work_desc
                    }
                    if mode == "new": supabase.table("entries").insert(payload).execute()
                    else: supabase.table("entries").update(payload).eq("id", existing_entry["id"]).execute()
                    st.success("Saved Successfully!"); st.rerun()
                else: st.error("Please enter counts or description.")
        else: st.error("⚠️ No rate found for this contractor on this date.")

# ==========================
# 2. SITE LOGS (Fixed Columns)
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
            
            df_display = df_log[[
                "Date", "site", "contractor", 
                "count_mason", "count_helper", "count_ladies", 
                "total_cost", "work_description"
            ]].rename(columns={
                "site": "Site", "contractor": "Contractor",
                "count_mason": "Mason", "count_helper": "Helper", "count_ladies": "Ladies",
                "total_cost": "Cost (₹)", "work_description": "Work Desc"
            })
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else: st.info("No logs found.")

# ==========================
# 3. WEEKLY BILL (The Excel Style)
# ==========================
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill Report")
    
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    
    if not df_e.empty and not df_c.empty:
        df_e["date_dt"] = pd.to_datetime(df_e["date"])
        df_c["effective_date"] = pd.to_datetime(df_c["effective_date"]).dt.date
        
        df_e["start_date"] = df_e["date_dt"].dt.date.apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        df_e["period_label"] = df_e.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
        
        weeks = sorted(df_e["period_label"].unique(), reverse=True)
        selected_week = st.selectbox("Select Week", weeks)
        
        df_week = df_e[df_e["period_label"] == selected_week].copy()
        unique_sites = df_week["site"].unique()
        
        for site_name in unique_sites:
            st.markdown(f"### 📍 Site: {site_name}")
            df_site = df_week[df_week["site"] == site_name]
            unique_cons = df_site["contractor"].unique()
            
            for con_name in unique_cons:
                df_con_entries = df_site[df_site["contractor"] == con_name].sort_values("date")
                
                display_rows = []
                total_m, total_h, total_l, total_amt = 0, 0, 0, 0
                
                for _, row in df_con_entries.iterrows():
                    d_str = row["date_dt"].strftime("%d-%m-%Y")
                    display_rows.append({
                        "Date": d_str,
                        "Mason": row["count_mason"],
                        "Helper": row["count_helper"],
                        "Ladies": row["count_ladies"]
                    })
                    total_m += row["count_mason"]
                    total_h += row["count_helper"]
                    total_l += row["count_ladies"]
                    total_amt += row["total_cost"]

                rates = df_c[(df_c["name"] == con_name)].sort_values("effective_date", ascending=False)
                r_m, r_h, r_l = 0, 0, 0
                if not rates.empty:
                    curr = rates.iloc[0]
                    r_m, r_h, r_l = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]

                bill_df = pd.DataFrame(display_rows).astype(str)
                
                # Totals
                bill_df = pd.concat([bill_df, pd.DataFrame([{
                    "Date": "<b>Total Labour</b>",
                    "Mason": f"<b>{total_m}</b>",
                    "Helper": f"<b>{total_h}</b>",
                    "Ladies": f"<b>{total_l}</b>"
                }])], ignore_index=True)
                
                # Amount
                bill_df = pd.concat([bill_df, pd.DataFrame([{
                    "Date": "<b>Amount (₹)</b>",
                    "Mason": f"₹{total_m * r_m:,.0f}",
                    "Helper": f"₹{total_h * r_h:,.0f}",
                    "Ladies": f"₹{total_l * r_l:,.0f}"
                }])], ignore_index=True)

                # Grand Total
                bill_df = pd.concat([bill_df, pd.DataFrame([{
                    "Date": "<b>Total Amount</b>",
                    "Mason": "",
                    "Helper": f"<b>₹{total_amt:,.0f}</b>", 
                    "Ladies": ""
                }])], ignore_index=True)

                st.markdown(f"#### 👷 Contractor: {con_name}")
                st.write(bill_df.to_html(escape=False, index=False, classes="table table-bordered"), unsafe_allow_html=True)
                st.divider()

# ==========================
# 4. ADMIN SETUP (Sites/Contractors/Users/Backup)
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Manage Sites")
    st.dataframe(fetch_data("sites"), hide_index=True, use_container_width=True)
    new = st.text_input("New Site Name")
    if st.button("Add Site", type="primary"):
        if new: supabase.table("sites").insert({"name": new}).execute(); st.rerun()

elif current_tab == "👷 Contractors":
    st.subheader("👷 Manage Contractors")
    st.dataframe(fetch_data("contractors"), use_container_width=True)
    with st.form("add_con"):
        n = st.text_input("Name")
        c1, c2, c3 = st.columns(3)
        r1 = c1.number_input("Mason Rate", value=800)
        r2 = c2.number_input("Helper Rate", value=500)
        r3 = c3.number_input("Ladies Rate", value=400)
        d = st.date_input("Effective Date", date.today())
        if st.form_submit_button("Save Contractor", type="primary"):
            supabase.table("contractors").insert({"name": n, "rate_mason": r1, "rate_helper": r2, "rate_ladies": r3, "effective_date": str(d)}).execute()
            st.rerun()

elif current_tab == "👥 Users":
    st.subheader("👥 User Access")
    st.dataframe(fetch_data("users"), use_container_width=True)
    with st.form("add_user"):
        ph = st.text_input("Phone")
        nm = st.text_input("Name")
        rl = st.selectbox("Role", ["user", "admin"])
        site_opts = fetch_data("sites")["name"].tolist() if not fetch_data("sites").empty else []
        st_as = st.selectbox("Assign Site", ["None/All"] + site_opts)
        if st.form_submit_button("Save User", type="primary"):
            sv = None if st_as == "None/All" else st_as
            ext = supabase.table("users").select("*").eq("phone", ph).execute().data
            if ext: supabase.table("users").update({"name": nm, "role": rl, "assigned_site": sv}).eq("phone", ph).execute()
            else: supabase.table("users").insert({"phone": ph, "name": nm, "role": rl, "assigned_site": sv}).execute()
            st.success("Saved"); st.rerun()

elif current_tab == "💾 Backup":
    st.subheader("💾 Backup Data")
    if st.button("Download Full JSON Backup"):
        data = {
            "entries": fetch_data("entries").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "users": fetch_data("users").to_dict("records"),
            "backup_date": str(datetime.now())
        }
        st.download_button("📥 Click to Download", json.dumps(data, indent=4, default=str), f"backup_{date.today()}.json", "application/json", type="primary")