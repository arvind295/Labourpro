import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- 1. SETUP PAGE CONFIGURATION ---
st.set_page_config(page_title="LabourPro", page_icon="🏗️")

# --- 2. CONNECT TO SUPABASE ---
try:
    @st.cache_resource
    def init_connection():
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)

    supabase = init_connection()
except Exception:
    st.error("⚠️ Error connecting to Supabase. Check your secrets.toml file!")
    st.stop()

# --- 3. HELPER FUNCTION ---
def fetch_data(table_name):
    """Fetch all rows from a Supabase table"""
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching {table_name}: {e}")
        return pd.DataFrame()

# --- 4. APP TITLE ---
st.title("🏗️ Labour Management Pro")

# --- 5. TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📍 Sites", "👷 Contractors", "📝 Daily Entry", "📊 View Data"])

# ==========================================
# TAB 1: MANAGE SITES
# ==========================================
with tab1:
    st.subheader("📍 Manage Sites")
    df_sites = fetch_data("sites")

    # Display Current Sites
    if not df_sites.empty:
        st.dataframe(df_sites, hide_index=True, use_container_width=True)
    else:
        st.info("No sites found.")

    st.divider()
    c1, c2 = st.columns(2)

    # Add Site
    with c1:
        new_site = st.text_input("Enter New Site Name")
        if st.button("➕ Add Site"):
            if new_site:
                try:
                    supabase.table("sites").insert({"name": new_site}).execute()
                    st.success(f"Added {new_site}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding site: {e}")
            else:
                st.warning("Please enter a name.")

    # Delete Site
    with c2:
        if not df_sites.empty:
            del_site = st.selectbox("Select Site to Remove", df_sites["name"].unique())
            if st.button("🗑️ Delete Site"):
                try:
                    supabase.table("sites").delete().eq("name", del_site).execute()
                    st.warning(f"Deleted {del_site}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting: {e}")

# ==========================================
# TAB 2: MANAGE CONTRACTORS
# ==========================================
with tab2:
    st.subheader("👷 Manage Contractors")
    df_contractors = fetch_data("contractors")

    # Display Current Contractors
    if not df_contractors.empty:
        st.dataframe(df_contractors, hide_index=True, use_container_width=True)
    else:
        st.info("No contractors found.")

    st.divider()
    c1, c2 = st.columns(2)

    # Add Contractor
    with c1:
        new_name = st.text_input("Contractor Name")
        new_rate = st.number_input("Rate per Head (₹)", value=500, step=50)
        
        if st.button("➕ Add Contractor"):
            if new_name:
                try:
                    supabase.table("contractors").insert({
                        "name": new_name, 
                        "rate": new_rate
                    }).execute()
                    st.success(f"Added {new_name} at ₹{new_rate}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding: {e}")
            else:
                st.warning("Enter a name.")

    # Delete Contractor
    with c2:
        if not df_contractors.empty:
            del_con = st.selectbox("Select Contractor to Remove", df_contractors["name"].unique())
            if st.button("🗑️ Delete Contractor"):
                try:
                    supabase.table("contractors").delete().eq("name", del_con).execute()
                    st.warning(f"Deleted {del_con}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting: {e}")

# ==========================================
# TAB 3: DAILY ENTRY
# ==========================================
with tab3:
    st.subheader("📝 New Daily Entry")
    
    # Refresh data to ensure dropdowns are current
    df_sites = fetch_data("sites")
    df_contractors = fetch_data("contractors")

    if df_sites.empty or df_contractors.empty:
        st.warning("⚠️ Please add Sites and Contractors in the first two tabs.")
    else:
        c1, c2, c3 = st.columns(3)
        entry_date = c1.date_input("Date", datetime.today())
        site = c2.selectbox("Select Site", df_sites["name"].unique())
        contractor = c3.selectbox("Select Contractor", df_contractors["name"].unique())
        
        st.divider()
        
        col_input, col_info = st.columns(2)
        with col_input:
            labor_count = st.number_input("Number of Labors", min_value=1, value=1, step=1)
        
        # Calculate cost preview
        if not df_contractors.empty:
            rate = df_contractors[df_contractors["name"] == contractor]["rate"].iloc[0]
            total_cost = labor_count * float(rate)
            with col_info:
                st.info(f"💰 Rate: ₹{rate}/head\n\n💵 Total Cost: ₹{total_cost}")

        if st.button("✅ Save Entry", use_container_width=True):
            try:
                supabase.table("entries").insert({
                    "date": str(entry_date),
                    "site": site,
                    "contractor": contractor,
                    "labor_count": labor_count,
                    "total_cost": total_cost
                }).execute()
                st.balloons()
                st.success("Entry Saved Successfully!")
            except Exception as e:
                st.error(f"Error saving entry: {e}")

# ==========================================
# TAB 4: VIEW DATA (Analysis)
# ==========================================
with tab4:
    st.subheader("📊 Data Log")
    df_entries = fetch_data("entries")
    
    if not df_entries.empty:
        # Sort by date (newest first)
        df_entries = df_entries.sort_values(by="date", ascending=False)
        st.dataframe(df_entries, hide_index=True, use_container_width=True)
        
        # Simple Summary
        total_spent = df_entries["total_cost"].sum()
        total_labor = df_entries["labor_count"].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("Total Spent", f"₹{total_spent:,.0f}")
        m2.metric("Total Labor Count", f"{total_labor}")
    else:
        st.info("No entries recorded yet.")