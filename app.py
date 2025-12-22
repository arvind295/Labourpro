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
def get_billing_start_date(entry_date):
    """Calculates the Saturday that started the billing week for a given date."""
    # Weekday mapping: Mon=0, Tue=1 ... Sat=5, Sun=6
    # We want to shift back to the nearest Saturday.
    # Calculate how many days have passed since the last Saturday.
    # If Sat(5) -> 0 days ago. Sun(6) -> 1 day ago. Mon(0) -> 2 days ago... Fri(4) -> 6 days ago.
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

# --- 5. APP INTERFACE ---
# Sidebar Role Display
with st.sidebar:
    my_role = st.session_state.get("role", "user")
    st.write(f"👤 **{my_role.upper()}**")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

st.title("🏗️ Labour Management Pro")

# Navigation Tabs
tabs = ["📝 Daily Entry"]
if my_role == "admin":
    tabs += ["📊 Weekly Bill", "📍 Sites", "👷 Contractors", "👥 Users"]

current_tab = st.radio("Navigate", tabs, horizontal=True, label_visibility="collapsed")
st.divider()

# fetch common data
def fetch_data(table):
    return pd.DataFrame(supabase.table(table).select("*").execute().data)

# ==========================
# 1. DAILY ENTRY (Updated)
# ==========================
if current_tab == "📝 Daily Entry":
    st.subheader("📝 New Daily Entry")
    
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")

    if df_sites.empty or df_con.empty:
        st.warning("⚠️ Admin must add Sites and Contractors first.")
    else:
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date of Work", date.today())
        site = c2.selectbox("Site", df_sites["name"].unique())
        contractor = c3.selectbox("Contractor", df_con["name"].unique())
        
        st.write("---")
        k1, k2, k3 = st.columns(3)
        n_mason = k1.number_input("🧱 Masons", min_value=0, value=0)
        n_helper = k2.number_input("👷 Helpers", min_value=0, value=0)
        n_ladies = k3.number_input("👩 Ladies", min_value=0, value=0)

        # LOGIC: FETCH RATES (Hidden from User)
        # Find active rate
        rate_row = None
        try:
            resp = supabase.table("contractors").select("*").eq("name", contractor).lte("effective_date", str(entry_date)).order("effective_date", desc=True).limit(1).execute()
            if resp.data: rate_row = resp.data[0]
        except: pass

        if rate_row:
            # Calculate Total (Backend)
            total_est = (n_mason * rate_row['rate_mason']) + \
                        (n_helper * rate_row['rate_helper']) + \
                        (n_ladies * rate_row['rate_ladies'])

            # DISPLAY LOGIC: HIDE PRICES FROM USER
            if my_role == "admin":
                st.info(f"""
                **💰 ADMIN VIEW:**
                Rates: Mason ₹{rate_row['rate_mason']} | Helper ₹{rate_row['rate_helper']} | Ladies ₹{rate_row['rate_ladies']}
                **Total for today: ₹{total_est}**
                """)
            else:
                # User sees this generic message instead
                st.info("✅ details entered. Click Save to submit.")

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
                    st.success("Saved Successfully!")
                    st.rerun()
                else:
                    st.error("Please enter at least one labor count.")
        else:
            st.error("⚠️ No active rates found for this contractor.")

# ==========================
# 2. WEEKLY BILL (New!)
# ==========================
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Billing (Saturday - Friday)")
    
    df_e = fetch_data("entries")
    if not df_e.empty:
        # Convert date column to datetime objects
        df_e["date"] = pd.to_datetime(df_e["date"]).dt.date
        
        # Calculate "Bill Week Start" for every entry
        df_e["Bill Week (Sat)"] = df_e["date"].apply(get_billing_start_date)
        
        # Group by Week and Contractor
        report = df_e.groupby(["Bill Week (Sat)", "contractor", "site"])[["total_cost", "count_mason", "count_helper", "count_ladies"]].sum().reset_index()
        
        # Sort by newest week first
        report = report.sort_values("Bill Week (Sat)", ascending=False)

        st.dataframe(
            report, 
            column_config={
                "Bill Week (Sat)": st.column_config.DateColumn("Week Starting (Sat)"),
                "total_cost": st.column_config.NumberColumn("Total Bill (₹)", format="₹%d")
            },
            use_container_width=True
        )
    else:
        st.info("No entries found.")

# ==========================
# 3. SITES (Updated Duplicate Check)
# ==========================
elif current_tab == "📍 Sites":
    st.subheader("📍 Manage Sites")
    df_s = fetch_data("sites")
    if not df_s.empty: st.dataframe(df_s, hide_index=True)
    
    new_s = st.text_input("New Site Name")
    if st.button("Add Site"):
        # DUPLICATE CHECK
        existing_sites = []
        if not df_s.empty:
            existing_sites = df_s["name"].tolist()
            
        if new_s in existing_sites:
            st.error(f"❌ Site '{new_s}' already exists!")
        elif new_s:
            supabase.table("sites").insert({"name": new_s}).execute()
            st.success("Site Added!")
            st.rerun()

# ==========================
# 4. CONTRACTORS
# ==========================
elif current_tab == "👷 Contractors":
    st.subheader("👷 Manage Contractors")
    df_c = fetch_data("contractors")
    if not df_c.empty: st.dataframe(df_c)

    with st.expander("Add/Update Contractor Rates"):
        c_name = st.text_input("Contractor Name")
        c1, c2, c3 = st.columns(3)
        rm = c1.number_input("Mason Rate", value=800)
        rh = c2.number_input("Helper Rate", value=500)
        rl = c3.number_input("Ladies Rate", value=400)
        eff_date = st.date_input("Effective From")
        
        if st.button("Save Rates"):
            supabase.table("contractors").insert({
                "name": c_name,
                "rate_mason": rm, 
                "rate_helper": rh, 
                "rate_ladies": rl,
                "effective_date": str(eff_date)
            }).execute()
            st.success("Rates Updated")
            st.rerun()

# ==========================
# 5. USERS
# ==========================
elif current_tab == "👥 Users":
    st.subheader("👥 User Access")
    df_u = fetch_data("users")
    st.dataframe(df_u)
    
    u_ph = st.text_input("Phone")
    u_nm = st.text_input("Name")
    u_role = st.selectbox("Role", ["user", "admin"])
    
    if st.button("Add User"):
        try:
            supabase.table("users").insert({"phone": u_ph, "name": u_nm, "role": u_role}).execute()
            st.success("User Added")
            st.rerun()
        except:
            st.error("Error adding user (check duplicates)")