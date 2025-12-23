import streamlit as st
import pandas as pd
import json
from datetime import datetime, date, timedelta
from supabase import create_client
import io  # Required for CSV downloads

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

# --- 3. HELPER FUNCTIONS ---
def fetch_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def get_billing_start_date(entry_date):
    """Calculates the Saturday that started the billing week."""
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

def calculate_split_costs(df_e, df_c):
    """
    Goes through every entry and calculates exact cost for Mason/Helper/Ladies
    based on the rate effective at that specific date.
    """
    if df_e.empty or df_c.empty:
        return df_e
    
    # SAFETY FIX: Create a copy to avoid 'SettingWithCopy' warnings
    df_c = df_c.copy()
    
    # Ensure dates are comparable
    df_c["effective_date"] = pd.to_datetime(df_c["effective_date"]).dt.date
    
    m_costs, h_costs, l_costs = [], [], []
    
    for index, row in df_e.iterrows():
        # Find the rate for this contractor that was active on the entry date
        rates = df_c[
            (df_c["name"] == row["contractor"]) & 
            (df_c["effective_date"] <= row["date"])
        ].sort_values("effective_date", ascending=False)
        
        if not rates.empty:
            rate = rates.iloc[0]
            m_costs.append(row["count_mason"] * rate["rate_mason"])
            h_costs.append(row["count_helper"] * rate["rate_helper"])
            l_costs.append(row["count_ladies"] * rate["rate_ladies"])
        else:
            m_costs.append(0)
            h_costs.append(0)
            l_costs.append(0)
            
    df_e["amt_mason"] = m_costs
    df_e["amt_helper"] = h_costs
    df_e["amt_ladies"] = l_costs
    return df_e

# --- 4. LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    st.title("🏗️ LabourPro Login")
    
    # 1. Toggle between User and Admin
    login_type = st.radio("Select Login Type:", ["User Login", "Admin Login"], horizontal=True)

    # --- USER LOGIN (Worker) ---
    if login_type == "User Login":
        st.subheader("Worker Access")
        with st.form("user_login"):
            phone = st.text_input("Enter Mobile Number", max_chars=10).strip()
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if not phone:
                    st.error("Please enter a mobile number.")
                else:
                    try:
                        # Check DB for user
                        data = supabase.table("users").select("*").eq("phone", phone).execute().data
                        if data:
                            user = data[0]
                            if user.get("role") == "admin":
                                st.warning("Admins should use the 'Admin Login' tab.")
                            else:
                                st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                                st.success(f"Welcome, {user.get('name', 'User')}!")
                                st.rerun()
                        else:
                            st.error("❌ Number not found. Please contact Admin.")
                    except Exception as e:
                        st.error(f"Connection Error: {e}")

    # --- ADMIN LOGIN ---
    elif login_type == "Admin Login":
        st.subheader("Admin Access")
        with st.form("admin_login"):
            phone = st.text_input("Admin Mobile Number", max_chars=10).strip()
            password = st.text_input("Admin Password", type="password")
            submitted = st.form_submit_button("Login as Admin")
            
            if submitted:
                if not phone or not password:
                    st.error("Please enter both Mobile Number and Password.")
                elif password != ADMIN_PASSWORD:
                    st.error("❌ Incorrect Password")
                else:
                    try:
                        # Check DB to ensure this number is actually an admin
                        data = supabase.table("users").select("*").eq("phone", phone).execute().data
                        if data:
                            user = data[0]
                            if user.get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "admin"})
                                st.success("✅ Admin Access Granted")
                                st.rerun()
                            else:
                                st.error("⛔ This number does not have Admin privileges.")
                        else:
                            st.error("❌ Admin number not found in database.")
                    except Exception as e:
                        st.error(f"Connection Error: {e}")

if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# --- 5. MAIN APP INTERFACE ---
with st.sidebar:
    my_role = st.session_state.get("role", "user")
    my_phone = st.session_state.get("phone")
    st.write(f"👤 **{my_role.upper()}**")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏗️ Labour Management Pro")

# --- NAVIGATION ---
tabs = ["📝 Daily Entry"]
if my_role == "admin":
    tabs += [
        "🔍 Site Logs (Day-to-Day)", 
        "📊 Weekly Bill (Details)", 
        "💰 Payment Summary", 
        "📍 Sites", 
        "👷 Contractors", 
        "👥 Users",
        "💾 Backup & Restore"  # <--- NEW TAB ADDED
    ]

current_tab = st.radio("Navigate", tabs, horizontal=True, label_visibility="collapsed")
st.divider()

# ==========================
# 1. DAILY ENTRY 
# ==========================
if current_tab == "📝 Daily Entry":
    st.subheader("📝 Daily Work Entry")
    
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")

    if df_sites.empty or df_con.empty:
        st.warning("⚠️ Admin must add Sites and Contractors first.")
    else:
        # Site Access Logic
        available_sites = df_sites["name"].unique().tolist()
        if my_role != "admin":
            try:
                user_profile = supabase.table("users").select("assigned_site").eq("phone", my_phone).single().execute()
                assigned_site = user_profile.data.get("assigned_site")
                if assigned_site and assigned_site in available_sites:
                    available_sites = [assigned_site] 
                    st.success(f"📍 You are logged in to: **{assigned_site}**")
                else:
                    st.error("⛔ You have not been assigned a site yet. Please contact Admin.")
                    st.stop()
            except:
                st.stop()

        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date of Work", date.today(), format="DD/MM/YYYY")
        site = c2.selectbox("Site", available_sites) 
        contractor = c3.selectbox("Contractor", df_con["name"].unique())
        
        st.write("---")

        existing_entry = None
        try:
            resp = supabase.table("entries").select("*").eq("date", str(entry_date)).eq("site", site).eq("contractor", contractor).execute()
            if resp.data: existing_entry = resp.data[0]
        except: pass

        mode = "new"
        current_edits = 0
        val_m, val_h, val_l = 0.0, 0.0, 0.0
        val_desc = ""

        if existing_entry:
            mode = "edit"
            current_edits = existing_entry.get("edit_count") or 0
            val_m = float(existing_entry.get("count_mason", 0))
            val_h = float(existing_entry.get("count_helper", 0))
            val_l = float(existing_entry.get("count_ladies", 0))
            val_desc = existing_entry.get("work_description", "")
            
            if current_edits >= 2:
                st.error(f"⛔ Locked: Edited 2 times already.")
                st.stop()
            else:
                st.warning(f"✏️ Editing existing entry. (Edits used: {current_edits}/2)")

        # --- INPUTS ---
        k1, k2, k3 = st.columns(3)
        n_mason = k1.number_input("🧱 Masons", min_value=0.0, step=0.5, value=val_m, format="%.1f")
        n_helper = k2.number_input("👷 Helpers", min_value=0.0, step=0.5, value=val_h, format="%.1f")
        n_ladies = k3.number_input("👩 Ladies", min_value=0.0, step=0.5, value=val_l, format="%.1f")
        
        work_desc = st.text_area("📝 Work Description / Activity", value=val_desc, placeholder="e.g. Plastering 2nd floor wall...")

        rate_row = None
        try:
            resp = supabase.table("contractors").select("*").eq("name", contractor).lte("effective_date", str(entry_date)).order("effective_date", desc=True).limit(1).execute()
            if resp.data: rate_row = resp.data[0]
        except: pass

        if rate_row:
            total_est = (n_mason * rate_row['rate_mason']) + \
                        (n_helper * rate_row['rate_helper']) + \
                        (n_ladies * rate_row['rate_ladies'])

            if my_role == "admin":
                st.info(f"💰 **Total: ₹{total_est:,.2f}**")

            btn_text = "✅ Save Entry" if mode == "new" else f"🔄 Update"
            
            if st.button(btn_text, type="primary"):
                if total_est > 0 or work_desc.strip() != "":
                    data_payload = {
                        "date": str(entry_date), "site": site, "contractor": contractor,
                        "count_mason": n_mason, "count_helper": n_helper, "count_ladies": n_ladies,
                        "total_cost": total_est,
                        "work_description": work_desc
                    }

                    if mode == "new":
                        data_payload["edit_count"] = 0
                        supabase.table("entries").insert(data_payload).execute()
                        st.success("Saved!")
                    else:
                        if not existing_entry.get("original_values"):
                            snapshot_str = f"M:{existing_entry['count_mason']} H:{existing_entry['count_helper']} L:{existing_entry['count_ladies']} (₹{existing_entry['total_cost']})"
                            data_payload["original_values"] = snapshot_str
                        data_payload["edit_count"] = current_edits + 1
                        supabase.table("entries").update(data_payload).eq("id", existing_entry["id"]).execute()
                        st.success("Updated!")
                    st.rerun()
                else:
                    st.error("Enter at least one count or a description.")
        else:
            st.error("⚠️ No active rates found.")

# ==========================
# 2. SITE LOGS
# ==========================
elif current_tab == "🔍 Site Logs (Day-to-Day)":
    st.subheader("🔍 Site Logs & Analytics")
    
    df_sites = fetch_data("sites")
    if not df_sites.empty:
        # 1. SITE SELECTION
        selected_site = st.selectbox("Select Site", ["All Sites"] + df_sites["name"].unique().tolist())
        
        # Fetch Data
        if selected_site == "All Sites":
            raw_data = supabase.table("entries").select("*").order("date", desc=True).execute().data
        else:
            raw_data = supabase.table("entries").select("*").eq("site", selected_site).order("date", desc=True).execute().data
            
        df_log = pd.DataFrame(raw_data)
        
        if not df_log.empty:
            df_log["date"] = pd.to_datetime(df_log["date"])
            
            # --- DATE FIX: Format for display ---
            df_log["Date"] = df_log["date"].dt.strftime('%d-%m-%Y')
            df_log["Month"] = df_log["date"].dt.strftime('%B %Y')

            # 2. SEARCH & FILTER
            c1, c2 = st.columns([2, 1])
            search_term = c1.text_input("🔍 Search Logs", placeholder="Type contractor, work description...")
            filter_month = c2.selectbox("Filter Month", ["All Months"] + df_log["Month"].unique().tolist())

            if filter_month != "All Months":
                df_log = df_log[df_log["Month"] == filter_month]

            if search_term:
                mask = df_log.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
                df_log = df_log[mask]

            # 3. DASHBOARD
            st.divider()
            m1, m2, m3 = st.columns(3)
            total_spend = df_log["total_cost"].sum()
            top_contractor = df_log.groupby("contractor")["total_cost"].sum().idxmax() if not df_log.empty else "N/A"
            total_days = df_log["date"].nunique()

            m1.metric("💰 Total Spending", f"₹{total_spend:,.0f}")
            m2.metric("👷 Top Contractor", top_contractor)
            m3.metric("📅 Work Days Logged", total_days)

            # Chart
            if not df_log.empty:
                st.caption("💸 Spending by Contractor")
                chart_data = df_log.groupby("contractor")["total_cost"].sum()
                st.bar_chart(chart_data)

            # 4. DOWNLOAD BUTTON
            st.divider()
            c_csv = df_log.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download This Data (CSV)",
                data=c_csv,
                file_name=f"site_logs_{date.today()}.csv",
                mime="text/csv",
            )

            st.dataframe(
                df_log, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "date": None,
                    "Date": st.column_config.TextColumn("Date"),
                    "total_cost": st.column_config.NumberColumn("Cost", format="₹%d"),
                    "work_description": "Work Done"
                },
                column_order=["Date", "site", "contractor", "work_description", "total_cost", "count_mason", "count_helper", "count_ladies"]
            )
        else:
            st.info("No entries found for this site.")

# ==========================
# 3. WEEKLY BILL
# ==========================
elif current_tab == "📊 Weekly Bill (Details)":
    st.subheader("📊 Detailed Weekly Bill")
    
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")
    
    if not df_e.empty:
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        
        # Calculate Splits
        if not df_c.empty:
            df_e = calculate_split_costs(df_e, df_c)
        else:
            df_e["amt_mason"] = 0; df_e["amt_helper"] = 0; df_e["amt_ladies"] = 0

        # Billing periods
        df_e["start_date"] = df_e["date"].apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        
        # --- DATE FORMAT FIX: Billing Period ---
        df_e["Billing Period"] = df_e.apply(
            lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", 
            axis=1
        )
        
        # Aggregate
        report = df_e.groupby(["Billing Period", "start_date", "contractor", "site"])[
            ["total_cost", "count_mason", "count_helper", "count_ladies", "amt_mason", "amt_helper", "amt_ladies"]
        ].sum().reset_index()
        
        # --- DOWNLOAD BUTTON ---
        csv_bill = report.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Weekly Bill (CSV)",
            data=csv_bill,
            file_name=f"weekly_bill_{date.today()}.csv",
            mime="text/csv",
            type="primary"
        )

        st.dataframe(
            report,
            column_config={
                "total_cost": st.column_config.NumberColumn("Total Bill (₹)", format="₹%d"),
                "amt_mason": st.column_config.NumberColumn("Mason Amt (₹)", format="₹%d"),
                "amt_helper": st.column_config.NumberColumn("Helper Amt (₹)", format="₹%d"),
                "amt_ladies": st.column_config.NumberColumn("Ladies Amt (₹)", format="₹%d"),
            },
            use_container_width=True,
            hide_index=True
        )

        # Audit Log
        st.write("---")
        st.subheader("⚠️ Edit History")
        if "edit_count" in df_e.columns:
            edited_df = df_e[df_e["edit_count"] > 0]
            if not edited_df.empty:
                # Format the date in audit log too
                edited_df["date"] = pd.to_datetime(edited_df["date"]).dt.strftime('%d-%m-%Y')
                st.dataframe(edited_df[["date", "site", "contractor", "total_cost", "original_values", "edit_count"]], hide_index=True)
    else:
        st.info("No entries found.")

# ==========================
# 4. PAYMENT SUMMARY
# ==========================
elif current_tab == "💰 Payment Summary":
    st.subheader("💰 Weekly Payment Dashboard")
    
    df_e = fetch_data("entries")
    df_c = fetch_data("contractors")

    if not df_e.empty:
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        
        # Calculate Splits
        if not df_c.empty:
            df_e = calculate_split_costs(df_e, df_c)
            
        df_e["start_date"] = df_e["date"].apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        
        # --- DATE FORMAT FIX: Billing Period ---
        df_e["Billing Period"] = df_e.apply(
            lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", 
            axis=1
        )
        
        weeks_df = df_e[["Billing Period", "start_date"]].drop_duplicates().sort_values("start_date", ascending=False)
        
        for _, week_row in weeks_df.iterrows():
            current_period = week_row["Billing Period"]
            st.markdown(f"### 🗓️ Week: {current_period}")
            
            week_data = df_e[df_e["Billing Period"] == current_period]
            contractors_in_week = week_data.groupby("contractor")
            
            for contractor_name, contractor_df in contractors_in_week:
                grand_total = contractor_df["total_cost"].sum()
                
                with st.expander(f"👷 **{contractor_name}** —  Total: **₹{grand_total:,.2f}**"):
                    
                    # Detailed Breakdown table
                    breakdown = contractor_df.groupby("site")[
                        ["total_cost", "amt_mason", "amt_helper", "amt_ladies"]
                    ].sum().reset_index()
                    
                    st.dataframe(
                        breakdown,
                        column_config={
                            "site": "Site Name",
                            "total_cost": st.column_config.NumberColumn("Site Total (₹)", format="₹%d"),
                            "amt_mason": st.column_config.NumberColumn("Mason (₹)", format="₹%d"),
                            "amt_helper": st.column_config.NumberColumn("Helper (₹)", format="₹%d"),
                            "amt_ladies": st.column_config.NumberColumn("Ladies (₹)", format="₹%d"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
            st.divider()
    else:
        st.info("No data available.")

# ==========================
# 5. SITES 
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Manage Sites")
    df_s = fetch_data("sites")
    if not df_s.empty: st.dataframe(df_s, hide_index=True)
    
    new_s = st.text_input("New Site Name")
    if st.button("Add Site"):
        existing = df_s["name"].tolist() if not df_s.empty else []
        if new_s not in existing and new_s:
            supabase.table("sites").insert({"name": new_s}).execute()
            st.success("Added!")
            st.rerun()

# ==========================
# 6. CONTRACTORS
# ==========================
elif current_tab == "👷 Contractors":
    st.subheader("👷 Manage Contractors")
    df_c = fetch_data("contractors")
    if not df_c.empty:
        st.dataframe(df_c)
        all_cons = df_c["name"].unique().tolist()
    else:
        all_cons = []

    st.write("---")
    st.write("#### ✏️ Add/Edit Contractor")
    c_input = st.selectbox("Name", all_cons + ["Create New..."], index=None)
    
    fname = st.text_input("New Name") if c_input == "Create New..." else c_input
    is_edit = c_input != "Create New..." and c_input is not None

    dm, dh, dl = 800, 500, 400
    if is_edit and fname:
        try:
            row = df_c[df_c["name"] == fname].sort_values("effective_date", ascending=False).iloc[0]
            dm, dh, dl = int(row["rate_mason"]), int(row["rate_helper"]), int(row["rate_ladies"])
        except: pass

    if fname:
        c1, c2, c3 = st.columns(3)
        rm = c1.number_input("Mason Rate", value=dm)
        rh = c2.number_input("Helper Rate", value=dh)
        rl = c3.number_input("Ladies Rate", value=dl)
        ed = st.date_input("Effective From", date.today())
        
        if st.button("Save Contractor"):
            supabase.table("contractors").insert({
                "name": fname, "rate_mason": rm, "rate_helper": rh, "rate_ladies": rl, "effective_date": str(ed)
            }).execute()
            st.success("Saved!")
            st.rerun()

    with st.expander("🗑️ Delete Contractor"):
        dname = st.selectbox("Select to Delete", all_cons, index=None)
        if st.button("Delete Permanently"):
            supabase.table("contractors").delete().eq("name", dname).execute()
            st.success("Deleted.")
            st.rerun()

# ==========================
# 7. USERS
# ==========================
elif current_tab == "👥 Users":
    st.subheader("👥 User Access")
    df_u = fetch_data("users")
    st.dataframe(df_u)
    
    st.write("---")
    u_ph = st.text_input("Phone")
    u_nm = st.text_input("Name")
    c1, c2 = st.columns(2)
    u_role = c1.selectbox("Role", ["user", "admin"])
    
    site_opts = fetch_data("sites")["name"].unique().tolist() if not fetch_data("sites").empty else []
    u_site = c2.selectbox("Assign Site", ["None/All"] + site_opts)

    if st.button("Save User"):
        s_val = None if u_site == "None/All" else u_site
        exists = supabase.table("users").select("*").eq("phone", u_ph).execute().data
        if exists:
            supabase.table("users").update({"name": u_nm, "role": u_role, "assigned_site": s_val}).eq("phone", u_ph).execute()
        else:
            supabase.table("users").insert({"phone": u_ph, "name": u_nm, "role": u_role, "assigned_site": s_val}).execute()
        st.success("User Saved!")
        st.rerun()

# ==========================
# 8. BACKUP & RESTORE (IMPROVED)
# ==========================
elif current_tab == "💾 Backup & Restore":
    st.subheader("💾 Backup & Restore Database")
    st.markdown("""
    **Use this section to keep your data safe.**
    """)
    
    # --- SECTION A: BACKUP ---
    st.write("### 📤 Export Data (Backup)")
    if st.button("Generate Full Backup"):
        with st.spinner("Generating JSON file..."):
            # Fetch all tables
            data_entries = fetch_data("entries").to_dict(orient="records")
            data_contractors = fetch_data("contractors").to_dict(orient="records")
            data_sites = fetch_data("sites").to_dict(orient="records")
            data_users = fetch_data("users").to_dict(orient="records")
            
            full_backup = {
                "entries": data_entries,
                "contractors": data_contractors,
                "sites": data_sites,
                "users": data_users,
                "backup_date": str(datetime.now())
            }
            json_str = json.dumps(full_backup, indent=4, default=str)
            
            st.download_button(
                label="📥 Download Backup File (.json)",
                data=json_str,
                file_name=f"labourpro_backup_{date.today()}.json",
                mime="application/json",
                type="primary"
            )
    
    st.divider()
    
    # --- SECTION B: RESTORE ---
    st.write("### 📥 Import Data (Restore)")
    
    uploaded_file = st.file_uploader("Upload Backup JSON File", type=["json"])
    
    # THIS IS THE NEW SAFTEY FEATURE
    wipe_first = st.checkbox("⚠️ **Nuclear Option:** Delete all current data before restoring? (Guarantees exact copy, NO duplicates)", value=False)
    
    if uploaded_file is not None:
        if st.button("🔴 Start Restoration"):
            try:
                backup_data = json.load(uploaded_file)
                bar = st.progress(0)
                status = st.empty()
                
                # 1. WIPE DATA logic (If selected)
                if wipe_first:
                    status.warning("🧹 Wiping existing data... (This prevents duplicates)")
                    # We must delete 'entries' first because it depends on contractors/sites
                    try:
                        # 'neq' means 'not equal'. We delete everything where ID is not 0 (which is everything)
                        supabase.table("entries").delete().neq("id", 0).execute()
                        supabase.table("users").delete().neq("phone", "0").execute()
                        supabase.table("contractors").delete().neq("id", 0).execute()
                        supabase.table("sites").delete().neq("id", 0).execute()
                        status.success("🧹 Data wiped clean. Starting import...")
                    except Exception as e:
                        st.error(f"Error during wipe: {e}")
                        st.stop()

                # 2. RESTORE logic (Order matters: Sites/Contractors first, then Entries)
                
                # Sites
                if "sites" in backup_data and backup_data["sites"]:
                    status.text("Restoring Sites...")
                    supabase.table("sites").upsert(backup_data["sites"]).execute()
                bar.progress(25)

                # Contractors
                if "contractors" in backup_data and backup_data["contractors"]:
                    status.text("Restoring Contractors...")
                    supabase.table("contractors").upsert(backup_data["contractors"]).execute()
                bar.progress(50)
                
                # Users
                if "users" in backup_data and backup_data["users"]:
                    status.text("Restoring Users...")
                    supabase.table("users").upsert(backup_data["users"]).execute()
                bar.progress(70)

                # Entries (The big one)
                if "entries" in backup_data and backup_data["entries"]:
                    status.text("Restoring Work Entries...")
                    supabase.table("entries").upsert(backup_data["entries"]).execute()
                bar.progress(100)
                
                status.success("✅ Restoration Complete!")
                if wipe_first:
                    st.info("Database is now an exact clone of the uploaded file.")
                else:
                    st.info("Backup merged with existing data.")
                    
            except Exception as e:
                st.error(f"❌ Restoration Failed: {e}")