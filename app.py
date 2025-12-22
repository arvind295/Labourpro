import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="LabourPro", page_icon="🏗️")
ADMIN_PASSWORD = "admin123"  # <--- CHANGE YOUR ADMIN PASSWORD HERE

# --- 2. CONNECT TO SUPABASE ---
try:
    @st.cache_resource
    def init_connection():
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)

    supabase = init_connection()
except Exception:
    st.error("⚠️ Error connecting to Supabase.")
    st.stop()

# --- 3. SESSION STATE SETUP ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["phone"] = None
    st.session_state["role"] = None

# --- 4. AUTHENTICATION FUNCTIONS ---
def login_process():
    st.title("🏗️ Login")
    st.write("Enter your registered mobile number to continue.")
    
    phone_input = st.text_input("Mobile Number", max_chars=10).strip()
    
    if st.button("Login"):
        if not phone_input:
            st.warning("Please enter a number.")
            return

        # Check DB for this number
        try:
            response = supabase.table("users").select("*").eq("phone", phone_input).execute()
            data = response.data
            
            if len(data) > 0:
                user = data[0]
                role = user["role"]
                
                # IF ADMIN: Ask for password
                if role == "admin":
                    st.session_state["temp_user"] = user
                    st.session_state["awaiting_password"] = True
                    st.rerun()
                
                # IF USER: Direct Login
                else:
                    st.session_state["logged_in"] = True
                    st.session_state["phone"] = user["phone"]
                    st.session_state["role"] = "user"
                    st.success(f"Welcome back, {user.get('name', 'User')}!")
                    st.rerun()
            else:
                st.error("❌ Access Denied. Your number is not authorized by Admin.")
        except Exception as e:
            st.error(f"Login Error: {e}")

    # Admin Password Check (Second Step)
    if st.session_state.get("awaiting_password", False):
        st.info(f"👤 Admin Detected: {st.session_state['temp_user']['phone']}")
        admin_pass = st.text_input("Enter Admin Password", type="password")
        if st.button("Verify Password"):
            if admin_pass == ADMIN_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["phone"] = st.session_state["temp_user"]["phone"]
                st.session_state["role"] = "admin"
                st.session_state["awaiting_password"] = False
                st.rerun()
            else:
                st.error("Wrong password.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["phone"] = None
    st.session_state["role"] = None
    st.rerun()

# --- 5. SHOW LOGIN OR APP ---
if not st.session_state["logged_in"]:
    login_process()
    st.stop()

# ==========================================
# MAIN APP (LOGGED IN)
# ==========================================

# Sidebar Info
with st.sidebar:
    st.write(f"📱: **{st.session_state['phone']}**")
    st.write(f"🔑: **{st.session_state['role'].upper()}**")
    if st.button("Logout"):
        logout()

st.title("🏗️ Labour Management Pro")

# --- DEFINE TABS ---
if st.session_state["role"] == "admin":
    # Admin gets "Manage Users" tab
    tabs = st.tabs(["📝 Daily Entry", "👥 Manage Users", "📍 Sites", "👷 Contractors", "📊 View Data"])
    tab_entry, tab_users, tab_sites, tab_con, tab_view = tabs
else:
    # User gets ONLY Entry
    st.info("👋 Welcome! Submit your daily report below.")
    tab_entry = st.container()
    tab_users, tab_sites, tab_con, tab_view = None, None, None, None

# --- HELPER: FETCH DATA ---
def fetch_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

# ------------------------------------------
# TAB: DAILY ENTRY (Everyone)
# ------------------------------------------
with tab_entry:
    st.subheader("📝 New Daily Entry")
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")
    
    if df_sites.empty or df_con.empty:
        st.warning("Admin must add Sites/Contractors first.")
    else:
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date", datetime.today())
        site = c2.selectbox("Site", df_sites["name"].unique())
        contractor = c3.selectbox("Contractor", df_con["name"].unique())
        
        st.divider()
        labor_count = st.number_input("Labor Count", min_value=1, value=1)
        
        if not df_con.empty:
            rate = df_con[df_con["name"] == contractor]["rate"].iloc[0]
            total = labor_count * float(rate)
            st.info(f"💰 Cost: ₹{total}")

        if st.button("✅ Save Entry", use_container_width=True):
            supabase.table("entries").insert({
                "date": str(entry_date),
                "site": site,
                "contractor": contractor,
                "labor_count": labor_count,
                "total_cost": total
            }).execute()
            st.success("Saved!")
            time.sleep(1)
            st.rerun()

# ------------------------------------------
# ADMIN TABS
# ------------------------------------------
if st.session_state["role"] == "admin":

    # --- TAB: MANAGE USERS (Authorize Mobile Numbers) ---
    with tab_users:
        st.subheader("👥 Authorize Users")
        
        # 1. Add New User
        c1, c2 = st.columns([2, 1])
        new_phone = c1.text_input("Enter Mobile Number to Authorize")
        new_name = c2.text_input("User Name (Optional)")
        
        if st.button("➕ Authorize Number"):
            if new_phone:
                try:
                    supabase.table("users").insert({
                        "phone": new_phone, 
                        "role": "user",
                        "name": new_name
                    }).execute()
                    st.success(f"Authorized {new_phone}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error (Maybe already exists?): {e}")

        st.divider()
        
        # 2. List / Delete Users
        users_df = fetch_data("users")
        if not users_df.empty:
            st.dataframe(users_df[["phone", "name", "role"]], hide_index=True)
            
            del_user = st.selectbox("Select Number to Remove", users_df["phone"].unique())
            if st.button("❌ Remove User Access"):
                if del_user == st.session_state["phone"]:
                    st.error("You cannot delete yourself!")
                else:
                    supabase.table("users").delete().eq("phone", del_user).execute()
                    st.warning(f"Removed access for {del_user}")
                    st.rerun()

    # --- TAB: SITES ---
    with tab_sites:
        st.subheader("📍 Manage Sites")
        df_sites = fetch_data("sites")
        if not df_sites.empty: st.dataframe(df_sites, hide_index=True)
        
        new_site = st.text_input("New Site Name")
        if st.button("Add Site"):
            supabase.table("sites").insert({"name": new_site}).execute()
            st.rerun()
            
    # --- TAB: CONTRACTORS ---
    with tab_con:
        st.subheader("👷 Manage Contractors")
        df_c = fetch_data("contractors")
        if not df_c.empty: st.dataframe(df_c, hide_index=True)
        
        n_name = st.text_input("Name")
        n_rate = st.number_input("Rate", 500)
        if st.button("Add Contractor"):
            supabase.table("contractors").insert({"name": n_name, "rate": n_rate}).execute()
            st.rerun()

    # --- TAB: VIEW DATA ---
    with tab_view:
        st.subheader("📊 Data Log")
        df_e = fetch_data("entries")
        if not df_e.empty:
            st.dataframe(df_e.sort_values("date", ascending=False), hide_index=True)