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

# --- 3. CUSTOM STYLING (Aggressive Visibility Fix) ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* Force ALL Text to Black */
        * {
            color: #000000 !important;
        }
        
        /* Main Background */
        .stApp {
            background-color: #FFFFFF !important;
        }

        /* Sidebar Background & Text */
        section[data-testid="stSidebar"] {
            background-color: #F8F9FA !important;
            border-right: 1px solid #E0E0E0;
        }
        section[data-testid="stSidebar"] * {
            color: #000000 !important;
        }

        /* --- INPUTS FIX (Text & Background) --- */
        input, textarea, select {
            color: #000000 !important;
            background-color: #FFFFFF !important;
            border: 1px solid #ccc !important; 
        }
        
        /* Streamlit Input Wrappers */
        div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
            background-color: #FFFFFF !important;
            color: #000000 !important;
            border: 1px solid #ccc !important;
        }

        /* Input Labels */
        label, .stTextInput label, .stNumberInput label, .stDateInput label, .stSelectbox label {
            color: #000000 !important;
            font-weight: bold !important;
        }

        /* --- DATAFRAMES & TABLES FIX --- */
        div[data-testid="stDataFrame"], div[data-testid="stTable"] {
            color: #000000 !important;
            background-color: #FFFFFF !important;
        }
        
        /* Table Headers */
        th {
            background-color: #E0E0E0 !important;
            color: #000000 !important;
            font-weight: bold !important;
            border-bottom: 2px solid #000 !important;
        }
        
        /* Table Cells */
        td {
            color: #000000 !important;
            background-color: #FFFFFF !important;
            border-bottom: 1px solid #ddd !important;
        }

        /* --- BUTTONS --- */
        button[kind="primary"] {
            background-color: #F39C12 !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        button[kind="secondary"] {
            background-color: #E0E0E0 !important;
            color: #000000 !important;
            border: 1px solid #999 !important;
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_styling()

# --- 4. HELPER FUNCTIONS ---
def fetch_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def get_billing_start_date(entry_date):
    """Start week on Saturday"""
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
                st.markdown("**Enter Mobile Number**")
                phone = st.text_input("Mobile", label_visibility="collapsed", max_chars=10).strip()
                if st.form_submit_button("Login", type="primary"):
                    if not phone: st.error("Enter number.")
                    else:
                        try:
                            data = supabase.table("users").select("*").eq("phone", phone).execute().data
                            if data:
                                user = data[0]
                                if user.get("role") == "admin": st.warning("Use Admin Login tab.")
                                else:
                                    st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                                    st.rerun()
                            else: st.error("❌ User not found.")
                        except: st.error("Connection Error.")

        elif login_type == "Admin Login":
            with st.form("admin_login"):
                st.markdown("**Admin Mobile**")
                phone = st.text_input("Admin Mobile", label_visibility="collapsed").strip()
                st.markdown("**Password**")
                password = st.text_input("Password", type="password", label_visibility="collapsed")
                
                if st.form_submit_button("Login", type="primary"):
                    real_pass = st.secrets["general"]["admin_password"] if "general" in st.secrets else "admin123"
                    if password != real_pass: st.error("❌ Wrong Password")
                    else:
                        try:
                            data = supabase.table("users").select("*").eq("phone", phone).execute().data
                            if data and data[0].get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": data[0]["phone"], "role": "admin"})
                                st.rerun()
                            else: st.error("⛔ No Admin Access.")
                        except: st.error("Connection Error.")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 6. MAIN APP INTERFACE ---
with st.sidebar:
    st.markdown("### 👤 Profile")
    st.info(f"Role: **{st.session_state['role'].upper()}**")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏗️ Labour Management Pro")

tabs = ["📝 Daily Entry"]
if st.session_state["role"] == "admin":
    tabs += ["🔍 Site Logs", "📊 Weekly Bill", "📍 Sites", "👷 Contractors", "👥 Users", "📂 Archive & New Year"]

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
        if st.session_state["role"] != "admin":
            try:
                user_data = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
                assigned = user_data.data.get("assigned_site")
                if assigned and assigned in available_sites: available_sites = [assigned]
                else: st.error("⛔ No site assigned."); st.stop()
            except: st.stop()

        st.subheader("📝 New Work Entry")
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date", date.today(), format="DD/MM/YYYY")
        site = c2.selectbox("Site", available_sites) 
        contractor = c3.selectbox("Contractor", df_con["name"].unique())
        
        # Check Existing
        existing = None
        try:
            resp = supabase.table("entries").select("*").eq("date", str(entry_date)).eq("site", site).eq("contractor", contractor).execute()
            if resp.data: existing = resp.data[0]
        except: pass

        val_m, val_h, val_l, val_desc = 0.0, 0.0, 0.0, ""
        mode = "new"
        
        if existing:
            mode = "edit"
            val_m = float(existing.get("count_mason", 0))
            val_h = float(existing.get("count_helper", 0))
            val_l = float(existing.get("count_ladies", 0))
            val_desc = existing.get("work_description", "")
            st.warning(f"✏️ Editing entry for {site} - {contractor}")

        k1, k2, k3 = st.columns(3)
        n_mason = k1.number_input("🧱 Masons", min_value=0.0, step=0.5, value=val_m)
        n_helper = k2.number_input("👷 Helpers", min_value=0.0, step=0.5, value=val_h)
        n_ladies = k3.number_input("👩 Ladies", min_value=0.0, step=0.5, value=val_l)
        
        work_desc = st.text_area("Work Description", value=val_desc)

        # Rate Calculation
        rate_row = None
        try:
            resp = supabase.table("contractors").select("*").eq("name", contractor).lte("effective_date", str(entry_date)).order("effective_date", desc=True).limit(1).execute()
            if resp.data: rate_row = resp.data[0]
        except: pass

        if rate_row:
            est_cost = (n_mason * rate_row['rate_mason']) + (n_helper * rate_row['rate_helper']) + (n_ladies * rate_row['rate_ladies'])
            st.info(f"💰 **Estimated Cost: ₹{est_cost:,.2f}**")

            if st.button("✅ Save Entry" if mode == "new" else "🔄 Update Entry", type="primary"):
                if est_cost > 0 or work_desc.strip():
                    payload = {
                        "date": str(entry_date), "site": site, "contractor": contractor,
                        "count_mason": n_mason, "count_helper": n_helper, "count_ladies": n_ladies,
                        "total_cost": est_cost, "work_description": work_desc
                    }
                    if mode == "new": supabase.table("entries").insert(payload).execute()
                    else: supabase.table("entries").update(payload).eq("id", existing["id"]).execute()
                    st.success("Saved!"); st.rerun()
                else: st.error("Enter counts or description.")
        else: st.error("⚠️ No active rate found for this contractor.")

# ==========================
# 2. SITE LOGS (Fixed Visibility)
# ==========================
elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    df_sites = fetch_data("sites")
    if not df_sites.empty:
        sel_site = st.selectbox("Filter by Site", ["All Sites"] + df_sites["name"].unique().tolist())
        
        # Fetch Data
        raw = supabase.table("entries").select("*").order("date", desc=True).execute().data
        df_log = pd.DataFrame(raw)
        
        if not df_log.empty:
            if sel_site != "All Sites": df_log = df_log[df_log["site"] == sel_site]
            
            df_log["date"] = pd.to_datetime(df_log["date"])
            df_log["Date"] = df_log["date"].dt.strftime('%d-%m-%Y')
            
            df_show = df_log[[
                "Date", "site", "contractor", 
                "count_mason", "count_helper", "count_ladies", 
                "total_cost", "work_description"
            ]].rename(columns={
                "site": "Site", "contractor": "Contractor",
                "count_mason": "Mason", "count_helper": "Helper", "count_ladies": "Ladies",
                "total_cost": "Cost (₹)", "work_description": "Work Desc"
            })
            
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else: st.info("No logs found.")

# ==========================
# 3. WEEKLY BILL (The Tally View)
# ==========================
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill Report")
    
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    
    if not df_e.empty and not df_c.empty:
        df_e["date_dt"] = pd.to_datetime(df_e["date"])
        df_c["effective_date"] = pd.to_datetime(df_c["effective_date"]).dt.date
        
        # Determine Billing Weeks
        df_e["start_date"] = df_e["date_dt"].dt.date.apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        df_e["week_label"] = df_e.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
        
        weeks = sorted(df_e["week_label"].unique(), reverse=True)
        sel_week = st.selectbox("Select Week", weeks)
        
        df_week = df_e[df_e["week_label"] == sel_week].copy()
        
        # Render Tables
        for site_name in df_week["site"].unique():
            st.markdown(f"### 📍 Site: {site_name}")
            df_site = df_week[df_week["site"] == site_name]
            
            for con_name in df_site["contractor"].unique():
                st.markdown(f"#### 👷 Contractor: {con_name}")
                df_con_entries = df_site[df_site["contractor"] == con_name].sort_values("date")
                
                rows = []
                tm, th, tl, tamt = 0, 0, 0, 0
                
                for _, row in df_con_entries.iterrows():
                    rows.append({
                        "Date": row["date_dt"].strftime("%d-%m-%Y"),
                        "Mason": row["count_mason"],
                        "Helper": row["count_helper"],
                        "Ladies": row["count_ladies"]
                    })
                    tm += row["count_mason"]; th += row["count_helper"]; tl += row["count_ladies"]
                    tamt += row["total_cost"]

                # Get Rates
                rates = df_c[df_c["name"] == con_name].sort_values("effective_date", ascending=False)
                rm, rh, rl = (0,0,0)
                if not rates.empty:
                    rm, rh, rl = rates.iloc[0]["rate_mason"], rates.iloc[0]["rate_helper"], rates.iloc[0]["rate_ladies"]
                
                # Build HTML Table
                html = f"""
                <table style="width:100%; border-collapse: collapse; color: black; background: white;">
                    <tr style="background: #e0e0e0; border-bottom: 2px solid black;">
                        <th style="padding: 8px; border: 1px solid #ccc;">Date</th>
                        <th style="padding: 8px; border: 1px solid #ccc;">Mason</th>
                        <th style="padding: 8px; border: 1px solid #ccc;">Helper</th>
                        <th style="padding: 8px; border: 1px solid #ccc;">Ladies</th>
                    </tr>
                """
                for r in rows:
                    html += f"""
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ccc;">{r['Date']}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">{r['Mason']}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">{r['Helper']}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">{r['Ladies']}</td>
                    </tr>
                    """
                
                # Totals
                html += f"""
                    <tr style="font-weight: bold; background: #f9f9f9;">
                        <td style="padding: 8px; border: 1px solid #ccc;">Total Labour</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">{tm}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">{th}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">{tl}</td>
                    </tr>
                    <tr style="font-weight: bold;">
                        <td style="padding: 8px; border: 1px solid #ccc;">Amount (₹)</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">₹{tm*rm:,.0f}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">₹{th*rh:,.0f}</td>
                        <td style="padding: 8px; border: 1px solid #ccc;">₹{tl*rl:,.0f}</td>
                    </tr>
                    <tr style="font-weight: bold; background: #e0e0e0; font-size: 1.1em;">
                        <td style="padding: 8px; border: 1px solid #ccc;">Total Amount</td>
                        <td colspan="3" style="padding: 8px; border: 1px solid #ccc; text-align: center;">₹{tamt:,.0f}</td>
                    </tr>
                </table>
                <br>
                """
                st.markdown(html, unsafe_allow_html=True)
            st.divider()

# ==========================
# 4. ADMIN TABLES (Fixed Visibility)
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
            # Check exist
            try:
                ext = supabase.table("users").select("*").eq("phone", ph).execute().data
                if ext: supabase.table("users").update({"name": nm, "role": rl, "assigned_site": sv}).eq("phone", ph).execute()
                else: supabase.table("users").insert({"phone": ph, "name": nm, "role": rl, "assigned_site": sv}).execute()
                st.success("Saved"); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# ==========================
# 5. ARCHIVE & NEW YEAR (New Feature)
# ==========================
elif current_tab == "📂 Archive & New Year":
    st.subheader("📂 Data Archive & Fresh Start")
    st.warning("⚠️ **Warning:** Archiving will move current entries to a backup file and clear the database for a new year. This cannot be undone easily.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Step 1: Backup Current Data")
        if st.button("📥 Download Full Backup JSON"):
            data = {
                "entries": fetch_data("entries").to_dict("records"),
                "contractors": fetch_data("contractors").to_dict("records"),
                "sites": fetch_data("sites").to_dict("records"),
                "users": fetch_data("users").to_dict("records"),
                "archive_date": str(datetime.now())
            }
            json_str = json.dumps(data, indent=4, default=str)
            st.download_button("Click to Save File", json_str, f"archive_{date.today()}.json", "application/json", type="primary")

    with col2:
        st.markdown("### Step 2: Start Fresh Year")
        st.markdown("This will **DELETE ALL** entry logs (Daily Entries) but keep Sites, Contractors, and Users.")
        
        confirm_text = st.text_input("Type 'DELETE ALL ENTRIES' to confirm:")
        
        if st.button("🔥 Clear Entries & Start Fresh", type="primary"):
            if confirm_text == "DELETE ALL ENTRIES":
                try:
                    # Supabase doesn't allow 'delete all' without filter usually, so we iterate or use a broad filter
                    # Deleting where ID > 0 is a common trick
                    supabase.table("entries").delete().neq("id", 0).execute() 
                    st.success("✅ All entries have been cleared. Ready for new year.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error clearing data: {e}")
            else:
                st.error("❌ Confirmation text does not match.")