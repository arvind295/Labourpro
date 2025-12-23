import streamlit as st
import pandas as pd
import json
from datetime import datetime, date, timedelta
from supabase import create_client
import io

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

# --- 3. CUSTOM STYLING ---
def apply_custom_styling():
    st.markdown("""
        <style>
        /* Force ALL Text to Black */
        * { color: #000000 !important; }
        .stApp { background-color: #FFFFFF !important; }
        section[data-testid="stSidebar"] { background-color: #F8F9FA !important; border-right: 1px solid #E0E0E0; }
        section[data-testid="stSidebar"] * { color: #000000 !important; }
        
        /* Inputs & Tables */
        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #ccc !important; 
        }
        div[data-testid="stDataFrame"], div[data-testid="stTable"] {
            color: #000000 !important; background-color: #FFFFFF !important;
        }
        th { background-color: #E0E0E0 !important; border-bottom: 2px solid #000 !important; }
        td { border-bottom: 1px solid #ddd !important; }
        
        /* Buttons */
        button[kind="primary"] { background-color: #F39C12 !important; color: #FFFFFF !important; border: none !important; }
        button[disabled] { background-color: #cccccc !important; color: #666666 !important; cursor: not-allowed; }
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

# Reuseable Function to Generate the HTML Bill (For Live & Archive)
def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty:
        st.info("No data available for this period.")
        return

    df_entries["date_dt"] = pd.to_datetime(df_entries["date"])
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"]).dt.date
    
    # Determine Weeks
    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
    
    weeks = sorted(df_entries["week_label"].unique(), reverse=True)
    sel_week = st.selectbox("Select Week", weeks)
    
    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    
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

            # Rate Lookup
            rates = df_contractors[df_contractors["name"] == con_name].sort_values("effective_date", ascending=False)
            rm, rh, rl = (0,0,0)
            if not rates.empty:
                rm, rh, rl = rates.iloc[0]["rate_mason"], rates.iloc[0]["rate_helper"], rates.iloc[0]["rate_ladies"]
            
            # --- HTML TABLE ---
            html = f"""
<table style="width:100%; border-collapse: collapse; color: black; background: white; font-size: 14px;">
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

# --- 5. LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: black;'>🏗️ LabourPro</h1>", unsafe_allow_html=True)
        st.divider()
        login_type = st.radio("Login Type:", ["User Login", "Admin Login"], horizontal=True)
        if login_type == "User Login":
            with st.form("u_log"):
                ph = st.text_input("Mobile", max_chars=10)
                if st.form_submit_button("Login", type="primary"):
                    try:
                        d = supabase.table("users").select("*").eq("phone", ph).execute().data
                        if d and d[0].get("role") != "admin":
                            st.session_state.update({"logged_in": True, "phone": d[0]["phone"], "role": "user"})
                            st.rerun()
                        else: st.error("Access Denied")
                    except: st.error("Error")
        else:
            with st.form("a_log"):
                ph = st.text_input("Admin Mobile")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Login", type="primary"):
                    rp = st.secrets["general"]["admin_password"] if "general" in st.secrets else "admin123"
                    if pw == rp:
                        try:
                            d = supabase.table("users").select("*").eq("phone", ph).execute().data
                            if d and d[0].get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": d[0]["phone"], "role": "admin"})
                                st.rerun()
                            else: st.error("Not Admin")
                        except: st.error("Error")
                    else: st.error("Wrong Password")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 6. MAIN APP ---
with st.sidebar:
    st.markdown("### 👤 Profile")
    st.info(f"Role: **{st.session_state['role'].upper()}**")
    if st.button("Logout"): st.session_state.clear(); st.rerun()

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

    if df_sites.empty: st.warning("Admin must add sites first.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        if st.session_state["role"] != "admin":
            u = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
            if u.data and u.data.get("assigned_site") in av_sites: av_sites = [u.data.get("assigned_site")]
            else: st.error("No site assigned."); st.stop()

        st.subheader("📝 New Work Entry")
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("Date", date.today())
        st_sel = c2.selectbox("Site", av_sites)
        con_sel = c3.selectbox("Contractor", df_con["name"].unique())
        
        exist = None
        try:
            r = supabase.table("entries").select("*").eq("date", str(dt)).eq("site", st_sel).eq("contractor", con_sel).execute()
            if r.data: exist = r.data[0]
        except: pass

        vm, vh, vl, vd = 0.0, 0.0, 0.0, ""
        mode = "new"
        if exist:
            mode = "edit"
            vm, vh, vl, vd = float(exist.get("count_mason", 0)), float(exist.get("count_helper", 0)), float(exist.get("count_ladies", 0)), exist.get("work_description", "")
            st.warning("✏️ Editing Entry")

        k1, k2, k3 = st.columns(3)
        nm = k1.number_input("Mason", value=vm, step=0.5)
        nh = k2.number_input("Helper", value=vh, step=0.5)
        nl = k3.number_input("Ladies", value=vl, step=0.5)
        wdesc = st.text_area("Description", value=vd)

        # Rate
        rate_row = None
        try:
            rr = supabase.table("contractors").select("*").eq("name", con_sel).lte("effective_date", str(dt)).order("effective_date", desc=True).limit(1).execute()
            if rr.data: rate_row = rr.data[0]
        except: pass

        if rate_row:
            cost = (nm * rate_row['rate_mason']) + (nh * rate_row['rate_helper']) + (nl * rate_row['rate_ladies'])
            st.info(f"💰 Est Cost: ₹{cost:,.2f}")
            if st.button("Save Entry", type="primary"):
                load = {"date": str(dt), "site": st_sel, "contractor": con_sel, "count_mason": nm, "count_helper": nh, "count_ladies": nl, "total_cost": cost, "work_description": wdesc}
                if mode == "new": supabase.table("entries").insert(load).execute()
                else: supabase.table("entries").update(load).eq("id", exist["id"]).execute()
                st.success("Saved"); st.rerun()
        else: st.error("No active rate found.")

# ==========================
# 2. SITE LOGS & BILL
# ==========================
elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    df = pd.DataFrame(supabase.table("entries").select("*").order("date", desc=True).execute().data)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime('%d-%m-%Y')
        df_show = df[["date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description"]]
        st.dataframe(df_show, use_container_width=True, hide_index=True)

elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill")
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    if not df_e.empty and not df_c.empty:
        render_weekly_bill(df_e, df_c)

# ==========================
# 3. ADMIN MGMT (UPDATED SITES)
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Site Management")
    df_sites = fetch_data("sites")
    st.dataframe(df_sites, hide_index=True, use_container_width=True)
    
    col_add, col_del = st.columns(2)
    
    # 1. ADD SITE
    with col_add:
        st.markdown("### ➕ Add Site")
        n = st.text_input("New Site Name")
        if st.button("Add Site", type="primary"):
            supabase.table("sites").insert({"name": n}).execute()
            st.success(f"Added {n}")
            st.rerun()

    # 2. DELETE SITE (LOCKED)
    with col_del:
        st.markdown("### 🗑️ Delete Site")
        
        # Lock Logic
        if "site_backup_unlocked" not in st.session_state:
            st.session_state["site_backup_unlocked"] = False
        
        def unlock_site_delete():
            st.session_state["site_backup_unlocked"] = True

        # Backup Button
        backup_data = {
            "entries": fetch_data("entries").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "users": fetch_data("users").to_dict("records"),
            "timestamp": str(datetime.now())
        }
        
        st.info("⚠️ Backup required before deletion.")
        st.download_button(
            label="1️⃣ Download Backup to Unlock",
            data=json.dumps(backup_data, indent=4, default=str),
            file_name=f"Site_Safety_Backup_{date.today()}.json",
            mime="application/json",
            on_click=unlock_site_delete
        )
        
        # Delete Interface
        if not df_sites.empty:
            del_site = st.selectbox("Select Site to Delete", df_sites["name"].unique())
            
            # Button Disabled until unlocked
            if st.button("2️⃣ Permanently Delete Site", disabled=not st.session_state["site_backup_unlocked"]):
                try:
                    supabase.table("sites").delete().eq("name", del_site).execute()
                    st.success(f"Site '{del_site}' deleted.")
                    st.session_state["site_backup_unlocked"] = False # Relock
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.write("No sites to delete.")


elif current_tab == "👷 Contractors":
    st.dataframe(fetch_data("contractors"), use_container_width=True)
    with st.form("ac"):
        n = st.text_input("Name")
        c1, c2, c3 = st.columns(3)
        r1 = c1.number_input("Mason Rate", value=800); r2 = c2.number_input("Helper Rate", value=500); r3 = c3.number_input("Ladies Rate", value=400)
        if st.form_submit_button("Save"): supabase.table("contractors").insert({"name": n, "rate_mason": r1, "rate_helper": r2, "rate_ladies": r3, "effective_date": str(date.today())}).execute(); st.rerun()

elif current_tab == "👥 Users":
    st.subheader("👥 User Management")
    df_users = fetch_data("users")
    st.dataframe(df_users, use_container_width=True)
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ✏️ Add or Edit User")
        st.info("To **change a site**, enter the user's phone, select the new site, and click Save.")
        with st.form("user_form"):
            phone_input = st.text_input("Mobile Number (Unique ID)", max_chars=10)
            name_input = st.text_input("User Name")
            role_input = st.selectbox("Role", ["user", "admin"])
            site_data = fetch_data("sites")
            site_list = ["None/All"] + site_data["name"].tolist() if not site_data.empty else ["None/All"]
            site_input = st.selectbox("Assign Site", site_list)
            if st.form_submit_button("💾 Save / Update", type="primary"):
                if not phone_input: st.error("Phone required.")
                else:
                    assigned_val = None if site_input == "None/All" else site_input
                    existing = supabase.table("users").select("*").eq("phone", phone_input).execute().data
                    if existing:
                        supabase.table("users").update({"name": name_input, "role": role_input, "assigned_site": assigned_val}).eq("phone", phone_input).execute()
                        st.success(f"Updated {name_input}")
                    else:
                        supabase.table("users").insert({"phone": phone_input, "name": name_input, "role": role_input, "assigned_site": assigned_val}).execute()
                        st.success(f"Added {name_input}")
                    st.rerun()

    with c2:
        st.markdown("### ❌ Delete User")
        st.warning("Admins cannot be deleted here.")
        if not df_users.empty:
            df_deletable = df_users[df_users["role"] != "admin"]
            if not df_deletable.empty:
                user_options = [f"{row['name']} ({row['phone']})" for index, row in df_deletable.iterrows()]
                selected_user_str = st.selectbox("Select User to Remove", user_options)
                if selected_user_str:
                    selected_phone = selected_user_str.split("(")[-1].replace(")", "")
                    if st.button("🗑️ Permanently Delete User"):
                        supabase.table("users").delete().eq("phone", selected_phone).execute()
                        st.success("User deleted."); st.rerun()
            else: st.info("No User accounts found.")

# ==========================
# 4. ARCHIVE & NEW YEAR
# ==========================
elif current_tab == "📂 Archive & New Year":
    st.subheader("📂 Data Management")
    tab1, tab2 = st.tabs(["🚀 Start New Year (Reset)", "📜 View Old Archives"])
    with tab1:
        st.markdown("### Step 1: Mandatory Backup")
        st.info("You must download a backup before you can clear data.")
        if "backup_unlocked" not in st.session_state: st.session_state["backup_unlocked"] = False
        def unlock_delete(): st.session_state["backup_unlocked"] = True
        backup_data = {"entries": fetch_data("entries").to_dict("records"), "contractors": fetch_data("contractors").to_dict("records"), "sites": fetch_data("sites").to_dict("records"), "users": fetch_data("users").to_dict("records"), "timestamp": str(datetime.now())}
        st.download_button(label="1️⃣ Download Full Backup JSON", data=json.dumps(backup_data, indent=4, default=str), file_name=f"LabourPro_Backup_{date.today()}.json", mime="application/json", type="primary", on_click=unlock_delete)
        st.divider()
        st.markdown("### Step 2: Clear Data")
        st.write("This will delete **ALL Daily Entries**. Sites, Users, and Contractors will remain.")
        confirm_text = st.text_input("Type 'DELETE ALL' to confirm:")
        if st.button("2️⃣ 🔥 Clear Entries & Start Fresh", type="primary", disabled=not st.session_state["backup_unlocked"]):
            if confirm_text == "DELETE ALL":
                try:
                    supabase.table("entries").delete().neq("id", 0).execute()
                    st.success("✅ System Reset Successful!"); st.balloons()
                    st.session_state["backup_unlocked"] = False
                except Exception as e: st.error(f"Error: {e}")
            else: st.error("❌ Type 'DELETE ALL' exactly.")
    with tab2:
        st.markdown("### 📜 Archive Viewer")
        uploaded_file = st.file_uploader("Upload Backup JSON", type=["json"])
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                st.success("✅ File Loaded")
                ae = pd.DataFrame(data.get("entries", []))
                ac = pd.DataFrame(data.get("contractors", []))
                if not ae.empty:
                    vm = st.radio("Select View:", ["Weekly Bill View", "Raw Logs View"], horizontal=True)
                    if vm == "Weekly Bill View": render_weekly_bill(ae, ac)
                    elif vm == "Raw Logs View": ae["date"] = pd.to_datetime(ae["date"]).dt.strftime('%d-%m-%Y'); st.dataframe(ae, use_container_width=True)
                else: st.warning("⚠️ No entries found.")
            except Exception as e: st.error(f"❌ Invalid JSON file: {e}")