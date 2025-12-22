import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="LabourPro", page_icon="🏗️", layout="wide")
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
    return pd.DataFrame(supabase.table(table).select("*").execute().data)

def get_billing_start_date(entry_date):
    """Calculates the Saturday that started the billing week."""
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

# --- 4. LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    st.title("🏗️ Login")
    phone = st.text_input("Mobile Number", max_chars=10).strip()
    if st.button("Login"):
        try:
            user_data = supabase.table("users").select("*").eq("phone", phone).execute().data
            if user_data:
                user = user_data[0]
                if user["role"] == "admin":
                    st.session_state["temp_user"] = user
                    st.session_state["awaiting_pass"] = True
                    st.rerun()
                else:
                    st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                    st.rerun()
            else:
                st.error("❌ Number not found.")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.get("awaiting_pass", False):
        st.info(f"Admin: {st.session_state['temp_user']['phone']}")
        if st.text_input("Password", type="password") == ADMIN_PASSWORD:
            st.session_state.update({
                "logged_in": True, 
                "phone": st.session_state['temp_user']['phone'], 
                "role": "admin", 
                "awaiting_pass": False
            })
            st.rerun()

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
    tabs += ["📊 Weekly Bill (Details)", "💰 Payment Summary", "📍 Sites", "👷 Contractors", "👥 Users"]

current_tab = st.radio("Navigate", tabs, horizontal=True, label_visibility="collapsed")
st.divider()

# ==========================
# 1. DAILY ENTRY (SITE RESTRICTED)
# ==========================
if current_tab == "📝 Daily Entry":
    st.subheader("📝 Daily Work Entry")
    
    # Fetch Master Data
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")

    if df_sites.empty or df_con.empty:
        st.warning("⚠️ Admin must add Sites and Contractors first.")
    else:
        # --- SITE ACCESS LOGIC ---
        # 1. Get all sites initially
        available_sites = df_sites["name"].unique().tolist()
        
        # 2. If user is NOT admin, restrict them
        if my_role != "admin":
            try:
                # Fetch fresh user profile to get assigned_site
                user_profile = supabase.table("users").select("assigned_site").eq("phone", my_phone).single().execute()
                assigned_site = user_profile.data.get("assigned_site")
                
                if assigned_site and assigned_site in available_sites:
                    available_sites = [assigned_site] # Restrict to ONLY this site
                    st.success(f"📍 You are logged in to: **{assigned_site}**")
                else:
                    st.error("⛔ You have not been assigned a site yet. Please contact Admin.")
                    st.stop()
            except Exception as e:
                st.error(f"Error checking site access: {e}")
                st.stop()

        # Input Columns
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date of Work", date.today())
        site = c2.selectbox("Site", available_sites) # Filtered list
        contractor = c3.selectbox("Contractor", df_con["name"].unique())
        
        st.write("---")

        # Check existing
        existing_entry = None
        try:
            resp = supabase.table("entries").select("*") \
                .eq("date", str(entry_date)) \
                .eq("site", site) \
                .eq("contractor", contractor) \
                .execute()
            if resp.data:
                existing_entry = resp.data[0]
        except:
            pass

        # Mode setup
        mode = "new"
        current_edits = 0
        val_m, val_h, val_l = 0.0, 0.0, 0.0

        if existing_entry:
            mode = "edit"
            current_edits = existing_entry.get("edit_count") or 0
            val_m = float(existing_entry["count_mason"])
            val_h = float(existing_entry["count_helper"])
            val_l = float(existing_entry["count_ladies"])
            
            if current_edits >= 2:
                st.error(f"⛔ Locked: This entry has been edited 2 times already.")
                st.warning(f"Existing Data: Masons: {val_m} | Helpers: {val_h} | Ladies: {val_l}")
                st.stop()
            else:
                st.warning(f"✏️ Editing existing entry. (Edits used: {current_edits}/2)")

        # Inputs
        k1, k2, k3 = st.columns(3)
        n_mason = k1.number_input("🧱 Masons", min_value=0.0, step=0.5, value=val_m, format="%.1f")
        n_helper = k2.number_input("👷 Helpers", min_value=0.0, step=0.5, value=val_h, format="%.1f")
        n_ladies = k3.number_input("👩 Ladies", min_value=0.0, step=0.5, value=val_l, format="%.1f")

        # Rate Calculation
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

            btn_text = "✅ Save Entry" if mode == "new" else f"🔄 Update Entry (Attempt {current_edits + 1}/2)"
            
            if st.button(btn_text, type="primary"):
                if total_est > 0:
                    data_payload = {
                        "date": str(entry_date),
                        "site": site,
                        "contractor": contractor,
                        "count_mason": n_mason,
                        "count_helper": n_helper,
                        "count_ladies": n_ladies,
                        "total_cost": total_est
                    }

                    if mode == "new":
                        data_payload["edit_count"] = 0
                        supabase.table("entries").insert(data_payload).execute()
                        st.success("Saved Successfully!")
                    else:
                        if not existing_entry.get("original_values"):
                            snapshot_str = f"M:{existing_entry['count_mason']} H:{existing_entry['count_helper']} L:{existing_entry['count_ladies']} (₹{existing_entry['total_cost']})"
                            data_payload["original_values"] = snapshot_str
                        
                        data_payload["edit_count"] = current_edits + 1
                        supabase.table("entries").update(data_payload).eq("id", existing_entry["id"]).execute()
                        st.success(f"Updated! ({data_payload['edit_count']}/2 edits used)")
                    
                    st.rerun()
                else:
                    st.error("Please enter at least one labor count.")
        else:
            st.error("⚠️ No active rates found.")

# ==========================
# 2. WEEKLY BILL
# ==========================
elif current_tab == "📊 Weekly Bill (Details)":
    st.subheader("📊 Detailed Site Log")
    df_e = fetch_data("entries")
    
    if not df_e.empty:
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        df_e["start_date"] = df_e["date"].apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        df_e["Billing Period"] = df_e.apply(
            lambda x: f"{x['start_date'].strftime('%d %b')} - {x['end_date'].strftime('%d %b')}", 
            axis=1
        )
        
        # --- SECTION A: Normal Bill ---
        report = df_e.groupby(["Billing Period", "start_date", "contractor", "site"])[
            ["total_cost", "count_mason", "count_helper", "count_ladies"]
        ].sum().reset_index()
        
        st.dataframe(
            report[["Billing Period", "contractor", "site", "total_cost", "count_mason", "count_helper", "count_ladies"]],
            column_config={
                "total_cost": st.column_config.NumberColumn("Site Bill (₹)", format="₹%d"),
                "count_mason": st.column_config.NumberColumn("Masons", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # --- SECTION B: AUDIT LOG ---
        st.write("---")
        st.subheader("⚠️ Edit History (Audit Log)")
        if "edit_count" in df_e.columns:
            edited_df = df_e[df_e["edit_count"] > 0].copy()
            if not edited_df.empty:
                edited_df["Changes Made"] = edited_df["edit_count"].apply(lambda x: f"{x} time(s)")
                st.dataframe(
                    edited_df[["date", "site", "contractor", "total_cost", "original_values", "Changes Made"]],
                    column_config={
                        "date": "Date of Work",
                        "total_cost": st.column_config.NumberColumn("Current Amount (₹)", format="₹%d"),
                        "original_values": st.column_config.TextColumn("Original Entry (Before Edit)", width="medium"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("✅ No edits detected.")
    else:
        st.info("No data available.")

# ==========================
# 3. PAYMENT SUMMARY
# ==========================
elif current_tab == "💰 Payment Summary":
    st.subheader("💰 Weekly Payment Dashboard")
    df_e = fetch_data("entries")
    if not df_e.empty:
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        df_e["start_date"] = df_e["date"].apply(get_billing_start_date)
        df_e["end_date"] = df_e["start_date"] + timedelta(days=6)
        df_e["Billing Period"] = df_e.apply(
            lambda x: f"{x['start_date'].strftime('%d %b')} - {x['end_date'].strftime('%d %b')}", 
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
                    breakdown = contractor_df.groupby("site")[["total_cost", "count_mason", "count_helper", "count_ladies"]].sum().reset_index()
                    st.dataframe(breakdown, hide_index=True)
            st.divider()
    else:
        st.info("No data available.")

# ==========================
# 4. SITES 
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Manage Sites")
    df_s = fetch_data("sites")
    if not df_s.empty: st.dataframe(df_s, hide_index=True)
    
    new_s = st.text_input("New Site Name")
    if st.button("Add Site"):
        existing_sites = df_s["name"].tolist() if not df_s.empty else []
        if new_s in existing_sites:
            st.error(f"❌ Site '{new_s}' already exists!")
        elif new_s:
            supabase.table("sites").insert({"name": new_s}).execute()
            st.success("Site Added!")
            st.rerun()

# ==========================
# 5. CONTRACTORS
# ==========================
elif current_tab == "👷 Contractors":
    st.subheader("👷 Manage Contractors")
    df_c = fetch_data("contractors")
    if not df_c.empty:
        st.dataframe(df_c)
        all_contractor_names = df_c["name"].unique().tolist()
    else:
        all_contractor_names = []

    st.write("---")
    st.write("#### ✏️ Add or Edit Contractor")
    c_name_input = st.selectbox("Select or Type Contractor Name", options=all_contractor_names + ["Create New..."], index=None, placeholder="Type to search...")
    final_name = ""
    is_edit_mode = False
    
    if c_name_input == "Create New...":
        final_name = st.text_input("Enter New Contractor Name").strip()
    elif c_name_input:
        final_name = c_name_input
        is_edit_mode = True

    def_m, def_h, def_l = 800, 500, 400
    if is_edit_mode and final_name:
        try:
            current_row = df_c[df_c["name"] == final_name].sort_values("effective_date", ascending=False).iloc[0]
            def_m, def_h, def_l = int(current_row["rate_mason"]), int(current_row["rate_helper"]), int(current_row["rate_ladies"])
            st.info(f"🔄 **Editing Mode:** {final_name}")
        except: pass 

    if final_name:
        c1, c2, c3 = st.columns(3)
        rm = c1.number_input("Mason Rate", value=def_m)
        rh = c2.number_input("Helper Rate", value=def_h)
        rl = c3.number_input("Ladies Rate", value=def_l)
        eff_date = st.date_input("Effective From Date", date.today())
        
        btn_label = "Update Rates" if is_edit_mode else "Add Contractor"
        if st.button(btn_label):
            supabase.table("contractors").insert({
                "name": final_name, "rate_mason": rm, "rate_helper": rh, "rate_ladies": rl, "effective_date": str(eff_date)
            }).execute()
            st.success(f"{final_name} saved successfully!")
            st.rerun()

    st.write("---")
    with st.expander("🗑️ Delete Contractor (Danger Zone)"):
        del_name = st.selectbox("Select Contractor to Delete", options=all_contractor_names, index=None)
        if st.button("❌ Delete Permanently", type="primary"):
            if del_name:
                supabase.table("contractors").delete().eq("name", del_name).execute()
                st.success(f"Contractor '{del_name}' deleted.")
                st.rerun()

# ==========================
# 6. USERS (UPDATED: SITE ASSIGNMENT)
# ==========================
elif current_tab == "👥 Users":
    st.subheader("👥 User Access")
    df_u = fetch_data("users")
    st.dataframe(df_u)
    
    st.write("---")
    st.write("#### ➕ Add New User")
    
    u_ph = st.text_input("Phone Number")
    u_nm = st.text_input("User Name")
    
    c1, c2 = st.columns(2)
    u_role = c1.selectbox("Role", ["user", "admin"])
    
    # FETCH SITES FOR ASSIGNMENT
    site_opts = []
    df_s = fetch_data("sites")
    if not df_s.empty:
        site_opts = df_s["name"].unique().tolist()
    
    # If role is Admin, usually they don't need assignment, but we can leave it optional
    u_site = c2.selectbox("Assign Site (Optional for Admin)", options=["None/All"] + site_opts)

    if st.button("Add / Update User"):
        try:
            site_val = None if u_site == "None/All" else u_site
            
            # Upsert logic (checking if phone exists first is better, but simple insert for now)
            # We first check if user exists to Update instead of Insert (to fix site assignment)
            exists = supabase.table("users").select("*").eq("phone", u_ph).execute().data
            
            if exists:
                supabase.table("users").update({
                    "name": u_nm, "role": u_role, "assigned_site": site_val
                }).eq("phone", u_ph).execute()
                st.success("User Updated!")
            else:
                supabase.table("users").insert({
                    "phone": u_ph, "name": u_nm, "role": u_role, "assigned_site": site_val
                }).execute()
                st.success("User Added!")
            
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")