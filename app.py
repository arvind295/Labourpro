import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client, Client
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="LabourPro", page_icon="🏗️", layout="wide")
ADMIN_PASSWORD = "admin123"  # <--- Update if needed

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

# --- 3. LOGIN LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    st.title("🏗️ Login")
    phone = st.text_input("Mobile Number", max_chars=10).strip()
    if st.button("Login"):
        # Check user in DB
        try:
            user_data = supabase.table("users").select("*").eq("phone", phone).execute().data
            if user_data:
                user = user_data[0]
                # Admin Flow
                if user["role"] == "admin":
                    st.session_state["temp_user"] = user
                    st.session_state["awaiting_pass"] = True
                    st.rerun()
                # User Flow
                else:
                    st.session_state.update({"logged_in": True, "phone": user["phone"], "role": "user"})
                    st.rerun()
            else:
                st.error("❌ Number not found.")
        except Exception as e:
            st.error(f"Error: {e}")

    # Admin Password Step
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

# --- 4. DATA FUNCTIONS ---
def fetch_data(table):
    return pd.DataFrame(supabase.table(table).select("*").execute().data)

def get_active_rate(contractor_name, target_date):
    """Finds the rate effective for the specific date selected."""
    try:
        # Get all rates for this contractor, order by newest effective date first
        response = supabase.table("contractors")\
            .select("*")\
            .eq("name", contractor_name)\
            .lte("effective_date", str(target_date))\
            .order("effective_date", desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            return response.data[0] # Return the specific rate row
        return None
    except:
        return None

# --- 5. MAIN APP INTERFACE ---
st.title("🏗️ Labour Management Pro")

# Sidebar
with st.sidebar:
    # --- SAFE ROLE CHECK ---
    # This prevents the "NoneType" error if role is missing
    my_role = st.session_state.get("role")
    if my_role is None:
        my_role = "User"  # Default fallback
    
    st.write(f"👤 **{my_role.upper()}**")
    
    if st.button("Logout"):
        st.session_state.clear() # Wipes memory completely
        st.rerun()

# Tabs
tabs = ["📝 Daily Entry"]
if st.session_state["role"] == "admin":
    tabs += ["👥 Users", "📍 Sites", "👷 Contractors & Rates", "📊 Data"]

current_tab = st.radio("Navigate", tabs, horizontal=True, label_visibility="collapsed")
st.divider()

# ==========================
# 1. DAILY ENTRY TAB
# ==========================
if current_tab == "📝 Daily Entry":
    st.subheader("📝 New Daily Entry")
    
    df_sites = fetch_data("sites")
    # Get unique contractor names only
    df_con_raw = fetch_data("contractors")
    
    if df_sites.empty or df_con_raw.empty:
        st.warning("⚠️ Admin must add Sites and Contractors first.")
    else:
        # Inputs
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date of Work", date.today())
        site = c2.selectbox("Site", df_sites["name"].unique())
        contractor = c3.selectbox("Contractor", df_con_raw["name"].unique())
        
        st.write("---")
        st.write("Enter Labor Counts:")
        
        # 3 Separate Inputs
        k1, k2, k3 = st.columns(3)
        n_mason = k1.number_input("🧱 Masons", min_value=0, value=0)
        n_helper = k2.number_input("👷 Helpers", min_value=0, value=0)
        n_ladies = k3.number_input("👩 Ladies", min_value=0, value=0)
        
        # Dynamic Rate Calculation
        rate_info = get_active_rate(contractor, entry_date)
        
        if rate_info:
            r_m = rate_info['rate_mason']
            r_h = rate_info['rate_helper']
            r_l = rate_info['rate_ladies']
            
            # Show live calculation
            cost_m = n_mason * r_m
            cost_h = n_helper * r_h
            cost_l = n_ladies * r_l
            total_est = cost_m + cost_h + cost_l
            
            st.info(f"""
            **Active Rates for {entry_date}:** 🧱 Mason: ₹{r_m} | 👷 Helper: ₹{r_h} | 👩 Ladies: ₹{r_l}
            
            **Total Cost: ₹{total_est}**
            """)
            
            if st.button("✅ Save Entry", type="primary"):
                if total_est > 0:
                    supabase.table("entries").insert({
                        "date": str(entry_date),
                        "site": site,
                        "contractor": contractor,
                        "count_mason": n_mason,
                        "count_helper": n_helper,
                        "count_ladies": n_ladies,
                        "total_cost": total_est
                    }).execute()
                    st.success("Entry Saved!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter at least one labor.")
        else:
            st.error(f"⚠️ No rates found for {contractor} on {entry_date}. Please update rates in Admin tab.")

# ==========================
# 2. CONTRACTORS & RATES (Admin)
# ==========================
elif current_tab == "👷 Contractors & Rates":
    st.subheader("👷 Manage Contractors & Rates")
    
    df_c = fetch_data("contractors")
    if not df_c.empty:
        # Show cleaner table
        st.caption("Rate History Log")
        st.dataframe(df_c.sort_values("effective_date", ascending=False), hide_index=True)
    
    st.divider()
    
    col_add, col_update = st.columns(2)
    
    # ADD NEW or UPDATE EXISTING
    with col_add:
        st.write("### ➕ Add / Update Rates")
        is_new = st.checkbox("New Contractor?", value=True)
        
        if is_new:
            c_name = st.text_input("New Contractor Name")
        else:
            if not df_c.empty:
                c_name = st.selectbox("Select Existing Contractor", df_c["name"].unique())
            else:
                c_name = None
                st.warning("No contractors exist yet.")

        # Rate Inputs
        st.write("Set Rates:")
        rm = st.number_input("Mason Rate (₹)", value=800)
        rh = st.number_input("Helper Rate (₹)", value=500)
        rl = st.number_input("Ladies Rate (₹)", value=400)
        
        # Effective Date
        eff_date = st.date_input("🗓️ These rates apply from:", date.today())
        
        if st.button("💾 Save Rates"):
            if c_name:
                try:
                    supabase.table("contractors").insert({
                        "name": c_name,
                        "rate_mason": rm,
                        "rate_helper": rh,
                        "rate_ladies": rl,
                        "effective_date": str(eff_date)
                    }).execute()
                    st.success(f"Rates for {c_name} updated (Effective {eff_date})!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Enter a name.")

# ==========================
# 3. OTHER ADMIN TABS
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Manage Sites")
    df_s = fetch_data("sites")
    if not df_s.empty: st.dataframe(df_s, hide_index=True)
    
    new_s = st.text_input("New Site Name")
    if st.button("Add Site"):
        supabase.table("sites").insert({"name": new_s}).execute()
        st.rerun()

elif current_tab == "👥 Users":
    st.subheader("👥 User Access")
    df_u = fetch_data("users")
    st.dataframe(df_u)
    
    u_ph = st.text_input("Phone Number")
    u_nm = st.text_input("Name")
    if st.button("Authorize User"):
        supabase.table("users").insert({"phone": u_ph, "name": u_nm}).execute()
        st.success("User Authorized")

elif current_tab == "📊 Data":
    st.subheader("📊 Data Log")
    df_e = fetch_data("entries")
    if not df_e.empty:
        st.dataframe(df_e.sort_values("date", ascending=False), use_container_width=True)