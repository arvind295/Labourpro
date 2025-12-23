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
    initial_sidebar_state="collapsed"
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
        
        /* Mobile Adjustments */
        @media only screen and (max-width: 600px) {
            h1 { font-size: 1.8rem !important; }
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

# Reusable Function to Generate the HTML Bill
def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty:
        st.info("No data available for this period.")
        return

    # Safe Date Conversion
    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors='coerce')
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"], errors='coerce').dt.date
    
    # Drop rows with invalid dates
    df_entries = df_entries.dropna(subset=["date_dt"])
    
    # Determine Weeks
    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
    
    weeks = sorted(df_entries["week_label"].unique(), reverse=True)
    if not weeks:
        st.info("No valid weeks found.")
        return

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

            # Rate Lookup logic for display
            rates = df_contractors[df_contractors["name"] == con_name].sort_values("effective_date", ascending=False)
            rm, rh, rl = (0,0,0)
            if not rates.empty:
                start_of_week = df_week.iloc[0]["start_date"]
                valid_rates = rates[rates["effective_date"] <= start_of_week]
                if not valid_rates.empty:
                    curr = valid_rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]
                else:
                    curr = rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]
            
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
<td style="padding: 8px; border: 1px solid #ccc;">Rate (Approx)</td>
<td style="padding: 8px; border: 1px solid #ccc;">₹{rm:,.0f}</td>
<td style="padding: 8px; border: 1px solid #ccc;">₹{rh:,.0f}</td>
<td style="padding: 8px; border: 1px solid #ccc;">₹{rl:,.0f}</td>
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

# --- 5. LOGIN (MOBILE OPTIMIZED) ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    col1, col2, col3 = st.columns([1, 10, 1])
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: black;'>🏗️ LabourPro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: grey;'>Site Entry Portal</p>", unsafe_allow_html=True)
        st.divider()
        
        # --- USER LOGIN ---
        st.subheader("👷 Team Login")
        with st.form("u_log"):
            ph = st.text_input("Enter Mobile Number", max_chars=10, placeholder="98765xxxxx")
            if st.form_submit_button("🚀 Login", type="primary", use_container_width=True):
                try:
                    d = supabase.table("users").select("*").eq("phone", ph).execute().data
                    if d:
                        user = d[0]
                        if user.get("status") == "Resigned":
                            st.error("⚠️ Account Deactivated (Resigned).")
                        elif user.get("role") != "admin":
                            st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                            st.rerun()
                        else:
                            st.error("Please use Admin Login below.")
                    else:
                        st.error("User not found.")
                except Exception as e: st.error(f"Error: {e}")

        st.markdown("<br><br>", unsafe_allow_html=True)

        # --- ADMIN LOGIN ---
        with st.expander("🔐 Admin Login (Click to Expand)"):
            with st.form("a_log"):
                ph_admin = st.text_input("Admin Mobile")
                pw_admin = st.text_input("Password", type="password")
                if st.form_submit_button("Admin Login", use_container_width=True):
                    rp = st.secrets["general"]["admin_password"] if "general" in st.secrets else "admin123"
                    if pw_admin == rp:
                        try:
                            d = supabase.table("users").select("*").eq("phone", ph_admin).execute().data
                            if d and d[0].get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": d[0]["phone"], "role": "admin"})
                                st.rerun()
                            else: st.error("Not Admin Account")
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
    tabs += ["🔍 Site Logs", "📊 Weekly Bill", "📍 Sites", "👷 Contractors", "👥 Users", "📂 Archive & Recovery"]

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
            elif "All" in av_sites: pass
            else: st.error("No site assigned or site deleted."); st.stop()

        st.subheader("📝 New Work Entry")
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("Date", date.today())
        st_sel = c2.selectbox("Site", av_sites)
        
        con_options = df_con["name"].unique() if not df_con.empty else []
        if len(con_options) == 0:
            st.error("Please add contractors in Admin panel first.")
            st.stop()
            
        con_sel = c3.selectbox("Contractor", con_options)
        
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
            st.warning("✏️ Editing Existing Entry")

        k1, k2, k3 = st.columns(3)
        nm = k1.number_input("Mason", value=vm, step=0.5)
        nh = k2.number_input("Helper", value=vh, step=0.5)
        nl = k3.number_input("Ladies", value=vl, step=0.5)
        wdesc = st.text_area("Description", value=vd)

        # Rate Fetching (CRITICAL: Finds rate active on Entry Date)
        rate_row = None
        try:
            rr = supabase.table("contractors").select("*").eq("name", con_sel).lte("effective_date", str(dt)).order("effective_date", desc=True).limit(1).execute()
            if rr.data: rate_row = rr.data[0]
        except: pass

        if rate_row:
            cost = (nm * rate_row['rate_mason']) + (nh * rate_row['rate_helper']) + (nl * rate_row['rate_ladies'])
            st.info(f"💰 Est Cost: ₹{cost:,.2f}")
            if st.button("Save Entry", type="primary", use_container_width=True): 
                load = {"date": str(dt), "site": st_sel, "contractor": con_sel, "count_mason": nm, "count_helper": nh, "count_ladies": nl, "total_cost": cost, "work_description": wdesc}
                if mode == "new": supabase.table("entries").insert(load).execute()
                else: supabase.table("entries").update(load).eq("id", exist["id"]).execute()
                st.success("Saved"); st.rerun()
        else: st.error("No active rate found for this date. Check Contractor settings.")

# ==========================
# 2. SITE LOGS
# ==========================
elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    df_entries = pd.DataFrame(supabase.table("entries").select("*").order("date", desc=True).execute().data)
    df_users = fetch_data("users")

    if not df_entries.empty:
        df_entries["date_obj"] = pd.to_datetime(df_entries["date"], errors='coerce')
        df_entries = df_entries.dropna(subset=["date_obj"])
        
        df_entries["date_str"] = df_entries["date_obj"].dt.strftime('%d-%m-%Y')
        df_entries["month_year"] = df_entries["date_obj"].dt.strftime('%B %Y')

        col_f1, col_f2 = st.columns(2)
        all_sites = ["All Sites"] + sorted(df_entries["site"].unique().tolist())
        sel_site = col_f1.selectbox("📍 Filter by Site", all_sites)
        
        all_months = ["All Months"] + sorted(df_entries["month_year"].unique().tolist(), reverse=True)
        sel_month = col_f2.selectbox("📅 Filter by Month", all_months)

        df_filtered = df_entries.copy()
        if sel_site != "All Sites": df_filtered = df_filtered[df_filtered["site"] == sel_site]
        if sel_month != "All Months": df_filtered = df_filtered[df_filtered["month_year"] == sel_month]

        def get_user_for_site(site_name):
            if df_users.empty: return "Unknown"
            matched = df_users[df_users["assigned_site"] == site_name]
            if not matched.empty: return ", ".join(matched["name"].tolist()) 
            return "Admin/Unassigned"

        df_filtered["entered_by"] = df_filtered["site"].apply(get_user_for_site)
        
        st.markdown(f"**Showing {len(df_filtered)} entries**")
        df_display = df_filtered[[
            "date_str", "site", "entered_by", "contractor", 
            "count_mason", "count_helper", "count_ladies", 
            "total_cost", "work_description"
        ]].rename(columns={
            "date_str": "Date", "site": "Site", "entered_by": "Entered By",
            "contractor": "Contractor", "count_mason": "Mason", "count_helper": "Helper",
            "count_ladies": "Ladies", "total_cost": "Cost (₹)", "work_description": "Description"
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else: st.info("No logs found.")

elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill")
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    if not df_e.empty and not df_c.empty:
        render_weekly_bill(df_e, df_c)
    else:
        st.info("Insufficient data to generate bills.")

# ==========================
# 3. ADMIN MGMT
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Site Management")
    df_sites = fetch_data("sites")
    st.dataframe(df_sites, hide_index=True, use_container_width=True)
    
    col_add, col_del = st.columns(2)
    with col_add:
        st.markdown("### ➕ Add Site")
        n = st.text_input("New Site Name")
        if st.button("Add Site", type="primary"):
            if n.strip():
                supabase.table("sites").insert({"name": n}).execute()
                st.success(f"Added {n}"); st.rerun()
            else: st.error("Name cannot be empty")

    with col_del:
        st.markdown("### 🗑️ Delete Site")
        if "site_backup_unlocked" not in st.session_state: st.session_state["site_backup_unlocked"] = False
        def unlock_site_delete(): st.session_state["site_backup_unlocked"] = True
        backup_data = {"entries": fetch_data("entries").to_dict("records"), "contractors": fetch_data("contractors").to_dict("records"), "sites": fetch_data("sites").to_dict("records"), "users": fetch_data("users").to_dict("records"), "timestamp": str(datetime.now())}
        st.download_button(label="1️⃣ Download Backup to Unlock", data=json.dumps(backup_data, indent=4, default=str), file_name=f"Site_Safety_Backup_{date.today()}.json", mime="application/json", on_click=unlock_site_delete)
        if not df_sites.empty:
            del_site = st.selectbox("Select Site to Delete", df_sites["name"].unique())
            if st.button("2️⃣ Permanently Delete Site", disabled=not st.session_state["site_backup_unlocked"]):
                try:
                    supabase.table("sites").delete().eq("name", del_site).execute()
                    st.success(f"Site '{del_site}' deleted."); st.session_state["site_backup_unlocked"] = False; st.rerun()
                except Exception as e: st.error(f"Error: {e}")
        else: st.write("No sites to delete.")

# ==========================
# UPDATED CONTRACTOR TAB (New Price Hike Logic)
# ==========================
elif current_tab == "👷 Contractors":
    st.subheader("👷 Contractor Rate Management")
    
    # 1. Show Current Database (All History)
    df_con = fetch_data("contractors")
    
    # Show a cleaner table with latest rates first
    if not df_con.empty:
        st.dataframe(
            df_con.sort_values(by=["name", "effective_date"], ascending=[True, False]), 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "effective_date": st.column_config.DateColumn("Effective From", format="DD-MM-YYYY")
            }
        )
    else:
        st.info("No contractors added yet.")

    st.divider()

    # 2. Add New Rates / Update Existing
    st.markdown("### 📈 Update Rates / Add Contractor")
    
    # Toggle between New and Existing
    mode = st.radio("Action Type:", ["🆕 Add New Contractor", "✏️ Update Rates for Existing"], horizontal=True)
    
    with st.form("contractor_form"):
        # LOGIC: If updating, show dropdown. If new, show text input.
        if mode == "✏️ Update Rates for Existing":
            if df_con.empty:
                st.warning("No contractors found to update. Please add a new one first.")
                con_name = ""
            else:
                con_name = st.selectbox("Select Contractor", df_con["name"].unique())
        else:
            con_name = st.text_input("Enter New Contractor Name")

        c1, c2, c3 = st.columns(3)
        r_mason = c1.number_input("Mason Rate (₹)", value=0, step=10)
        r_helper = c2.number_input("Helper Rate (₹)", value=0, step=10)
        r_ladies = c3.number_input("Ladies Rate (₹)", value=0, step=10)
        
        # KEY FEATURE: Effective Date
        eff_date = st.date_input("📅 New Prices Effective From", value=date.today())
        
        submitted = st.form_submit_button("💾 Save Rate Card", type="primary", use_container_width=True)
        
        if submitted:
            if not con_name or str(con_name).strip() == "":
                st.error("❌ Name is required.")
            elif r_mason == 0 and r_helper == 0 and r_ladies == 0:
                st.error("❌ Please enter at least one rate.")
            else:
                try:
                    # Insert new row (History Preservation)
                    supabase.table("contractors").insert({
                        "name": con_name, 
                        "rate_mason": r_mason, 
                        "rate_helper": r_helper, 
                        "rate_ladies": r_ladies, 
                        "effective_date": str(eff_date)
                    }).execute()
                    
                    st.success(f"✅ Rates updated for {con_name} effective from {eff_date}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

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
            phone_input = st.text_input("Mobile Number", max_chars=10)
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
                        supabase.table("users").insert({"phone": phone_input, "name": name_input, "role": role_input, "assigned_site": assigned_val, "status": "Active"}).execute()
                        st.success(f"Added {name_input}")
                    st.rerun()

    with c2:
        st.markdown("### 🚪 Resign User")
        if not df_users.empty:
            df_active = df_users[(df_users["role"] != "admin") & (df_users.get("status", "Active") == "Active")] if 'status' in df_users.columns else df_users[df_users["role"] != "admin"]
            if not df_active.empty:
                user_options = [f"{row['name']} ({row['phone']})" for index, row in df_active.iterrows()]
                selected_user_str = st.selectbox("Select User", user_options)
                if selected_user_str:
                    selected_phone = selected_user_str.split("(")[-1].replace(")", "")
                    if st.button("🚫 Confirm Resignation"):
                        supabase.table("users").update({"status": "Resigned"}).eq("phone", selected_phone).execute()
                        st.success("User marked as Resigned."); st.rerun()
            else: st.info("No Active Users.")
        else: st.info("No Users.")

# ==========================
# 4. ARCHIVE, NEW YEAR & RECOVERY
# ==========================
elif current_tab == "📂 Archive & Recovery":
    st.subheader("📂 Data Management & Recovery")
    
    tab1, tab2, tab3 = st.tabs(["🚀 Start New Year (Reset)", "📜 View Old Archives", "♻️ Restore Data (Recovery)"])
    
    # --- TAB 1: RESET (Backup & Delete) ---
    with tab1:
        st.markdown("### Step 1: Mandatory Backup")
        st.info("You must download a backup before you can clear data.")
        if "backup_unlocked" not in st.session_state: st.session_state["backup_unlocked"] = False
        
        def unlock_delete(): st.session_state["backup_unlocked"] = True
        
        backup_data = {
            "entries": fetch_data("entries").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "users": fetch_data("users").to_dict("records"),
            "timestamp": str(datetime.now())
        }
        
        st.download_button(
            label="1️⃣ Download Full Backup JSON", 
            data=json.dumps(backup_data, indent=4, default=str), 
            file_name=f"LabourPro_Backup_{date.today()}.json", 
            mime="application/json", 
            type="primary", 
            on_click=unlock_delete
        )
        
        st.divider()
        st.markdown("### Step 2: Clear Data")
        st.warning("⚠️ This will delete **ALL Daily Entries**. Sites, Users, and Contractors will remain.")
        confirm_text = st.text_input("Type 'DELETE ALL' to confirm:")
        
        if st.button("2️⃣ 🔥 Clear Entries & Start Fresh", type="primary", disabled=not st.session_state["backup_unlocked"]):
            if confirm_text == "DELETE ALL":
                try:
                    supabase.table("entries").delete().neq("id", 0).execute()
                    st.success("✅ System Reset Successful! Ready for new year."); st.balloons()
                    st.session_state["backup_unlocked"] = False
                except Exception as e: st.error(f"Error: {e}")
            else: st.error("❌ Type 'DELETE ALL' exactly.")
            
    # --- TAB 2: VIEWER (Read Only) ---
    with tab2:
        st.markdown("### 📜 Archive Viewer (Read-Only)")
        uploaded_file = st.file_uploader("Upload Backup JSON to View", type=["json"], key="view_upload")
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                st.success("✅ File Loaded Successfully")
                
                ae = pd.DataFrame(data.get("entries", []))
                ac = pd.DataFrame(data.get("contractors", []))
                au = pd.DataFrame(data.get("users", []))
                asite = pd.DataFrame(data.get("sites", []))
                
                view_mode = st.selectbox(
                    "Select Data to View:", 
                    ["📊 Weekly Bill", "📝 Raw Entry Logs", "👥 Archived Users", "📍 Archived Sites", "👷 Archived Contractors"]
                )
                
                st.divider()
                
                if view_mode == "📊 Weekly Bill":
                    if not ae.empty and not ac.empty: render_weekly_bill(ae, ac)
                    else: st.warning("Not enough data for bills.")
                elif view_mode == "📝 Raw Entry Logs":
                    if not ae.empty:
                        ae["date"] = pd.to_datetime(ae["date"]).dt.strftime('%d-%m-%Y')
                        st.dataframe(ae, use_container_width=True)
                    else: st.warning("No entries.")
                elif view_mode == "👥 Archived Users":
                    st.dataframe(au, use_container_width=True) if not au.empty else st.warning("No users.")
                elif view_mode == "📍 Archived Sites":
                    st.dataframe(asite, use_container_width=True) if not asite.empty else st.warning("No sites.")
                elif view_mode == "👷 Archived Contractors":
                    st.dataframe(ac, use_container_width=True) if not ac.empty else st.warning("No contractors.")
                    
            except Exception as e: st.error(f"❌ Invalid JSON file: {e}")

    # --- TAB 3: RESTORE (Disaster Recovery) ---
    with tab3:
        st.markdown("### ♻️ Disaster Recovery")
        st.error("⚠️ **DANGER ZONE:** Use this to restore lost data. Duplicate data may occur if running multiple times.")
        
        restore_file = st.file_uploader("Upload Backup JSON to Restore", type=["json"], key="restore_upload")
        
        if restore_file is not None:
            data = json.load(restore_file)
            
            cnt_users = len(data.get("users", []))
            cnt_sites = len(data.get("sites", []))
            cnt_cons = len(data.get("contractors", []))
            cnt_entries = len(data.get("entries", []))
            
            st.markdown(f"""
                **File Summary:**
                * 👤 Users: {cnt_users}
                * 📍 Sites: {cnt_sites}
                * 👷 Contractors: {cnt_cons}
                * 📝 Entries: {cnt_entries}
            """)
            
            if st.button("🚀 Upload & Restore Data Now", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    def clean_for_insert(record_list):
                        cleaned = []
                        for item in record_list:
                            if 'id' in item: del item['id']
                            cleaned.append(item)
                        return cleaned

                    if cnt_sites > 0:
                        status_text.write("Restoring Sites...")
                        clean_sites = clean_for_insert(data["sites"])
                        supabase.table("sites").upsert(clean_sites, on_conflict="name").execute()
                    progress_bar.progress(25)
                    
                    if cnt_users > 0:
                        status_text.write("Restoring Users...")
                        clean_users = clean_for_insert(data["users"])
                        supabase.table("users").upsert(clean_users, on_conflict="phone").execute()
                    progress_bar.progress(50)

                    if cnt_cons > 0:
                        status_text.write("Restoring Contractors...")
                        clean_cons = clean_for_insert(data["contractors"])
                        try:
                            # Using upsert here might be tricky if IDs are involved,
                            # but safer than straight insert if duplicates exist.
                            # Best effort for recovery:
                            supabase.table("contractors").upsert(clean_cons).execute()
                        except:
                            pass
                    progress_bar.progress(75)

                    if cnt_entries > 0:
                        status_text.write("Restoring Entries (This may take a moment)...")
                        clean_entries = clean_for_insert(data["entries"])
                        batch_size = 100
                        for i in range(0, len(clean_entries), batch_size):
                            batch = clean_entries[i:i + batch_size]
                            supabase.table("entries").insert(batch).execute()
                            
                    progress_bar.progress(100)
                    status_text.success("✅ Restoration Complete! Your data is back online.")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"❌ Error during restore: {e}")