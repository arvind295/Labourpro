import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="LaborPro Enterprise", page_icon="🏗️", layout="centered")

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)


# --- DATA FUNCTIONS ---

def fetch_data(worksheet_name):
    """Reads data from a specific tab in Google Sheets"""
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df if not df.empty else pd.DataFrame()
    except:
        return pd.DataFrame()


# --- PASTE THIS NEW CODE INSTEAD ---
def save_data(df, worksheet_name):
    try:
        # 1. Update the Google Sheet
        conn.update(worksheet=worksheet_name, data=df)
        
        # 2. Clear the memory
        st.cache_data.clear()
        
        # 3. PAUSE FOR 2 SECONDS (To fix the API Error)
        import time
        time.sleep(2)
        
        # 4. Restart the app
        st.rerun()
        
    except Exception as e:
        st.error(f"Error saving data: {e}")


def get_sites():
    df = fetch_data("Sites")
    if not df.empty and "Name" in df.columns:
        return df["Name"].dropna().astype(str).unique().tolist()
    return []


def get_contractor_names():
    df = fetch_data("Contractors")
    if not df.empty and "Name" in df.columns:
        return df["Name"].unique().tolist()
    return []


def get_applicable_rates(contractor_name, target_date):
    """Finds the specific rate effective for the given date"""
    df = fetch_data("Contractors")
    df = df[df["Name"] == contractor_name].copy()

    if df.empty:
        return {'Mason': 0, 'Helper': 0, 'Ladies': 0}

    if "Effective_Date" not in df.columns:
        df["Effective_Date"] = pd.Timestamp("2000-01-01")
    else:
        df["Effective_Date"] = pd.to_datetime(df["Effective_Date"], errors='coerce').fillna(pd.Timestamp("2000-01-01"))

    target = pd.to_datetime(target_date)
    valid_rates = df[df["Effective_Date"] <= target]

    if valid_rates.empty:
        chosen_row = df.sort_values("Effective_Date", ascending=True).iloc[0]
    else:
        chosen_row = valid_rates.sort_values("Effective_Date", ascending=False).iloc[0]

    return {
        'Mason': float(chosen_row["Mason_Rate"]),
        'Helper': float(chosen_row["Helper_Rate"]),
        'Ladies': float(chosen_row["Ladies_Rate"])
    }


def get_user_profile(email):
    df = fetch_data("Users")
    if not df.empty and "Email" in df.columns:
        df["Email"] = df["Email"].astype(str).str.strip()
        user_row = df[df["Email"] == email.strip()]
        if not user_row.empty:
            return user_row.iloc[0]["Name"]
    return None


def update_user_name(email, name):
    df = fetch_data("Users")
    if not df.empty:
        df["Email"] = df["Email"].astype(str).str.strip()

    if email in df["Email"].values:
        df.loc[df["Email"] == email, "Name"] = name
    else:
        new_row = pd.DataFrame([{"Email": email, "Name": name}])
        df = pd.concat([df, new_row], ignore_index=True)
    save_data(df, "Users")


def check_existing_entry(date_str, site, contractor):
    """
    Checks if an entry exists.
    FIXED: Returns the FULL dataframe (df) instead of a single row to prevent KeyError.
    """
    df = fetch_data("Entries")
    if df.empty:
        return None, df

    df["Date"] = df["Date"].astype(str)

    mask = (
            (df["Date"] == str(date_str)) &
            (df["Site"] == site) &
            (df["Contractor"] == contractor)
    )
    result = df[mask]

    if not result.empty:
        # Return index and the FULL TABLE so .loc[idx] works later
        return result.index[0], df
    return None, df


def get_site_overview(date_str, site):
    df = fetch_data("Entries")
    if df.empty:
        return pd.DataFrame()

    df["Date"] = df["Date"].astype(str)
    mask = (df["Date"] == str(date_str)) & (df["Site"] == site)
    filtered_df = df[mask]

    if not filtered_df.empty:
        cols_to_show = ["Contractor", "Mason_Count", "Helper_Count", "Submitted_Name"]
        if "Work_Description" in filtered_df.columns:
            cols_to_show.append("Work_Description")
        return filtered_df[cols_to_show]
    return pd.DataFrame()


# --- SIDEBAR ---
st.sidebar.title("🔐 Login")
user_type = st.sidebar.radio("Select User Type", ["User Entry", "Admin Dashboard"])

# ==========================================
# 👨‍💼 ADMIN DASHBOARD
# ==========================================
if user_type == "Admin Dashboard":
    password = st.sidebar.text_input("Admin Password", type="password")

    if password == "8522":
        st.title("👨‍💼 Admin Dashboard")

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Sites", "Contractors", "Users", "All Data", "🧾 Weekly Bill"])

        # --- TAB 1: MANAGE SITES ---
        with tab1:
            st.subheader("📍 Manage Sites")
            df_sites = fetch_data("Sites")
            if not df_sites.empty:
                st.dataframe(df_sites, hide_index=True, use_container_width=True)

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                new_site = st.text_input("Enter New Site Name")
                if st.button("➕ Add Site"):
                    if new_site:
                        if not df_sites.empty and new_site in df_sites["Name"].values:
                            st.error("Site exists.")
                        else:
                        # 1. Create the new row
                            new_row = pd.DataFrame([{"Name": new_site}])
                        
                        # 2. SAFE DOWNLOAD (Retry if Google is busy)
                            try:
                                fresh_sites = conn.read(worksheet="Sites", ttl=0)
                            except Exception:
                                st.warning("Google is busy. Retrying in 3 seconds...")
                            import time
                            time.sleep(3)
                            # Try one last time
                            fresh_sites = conn.read(worksheet="Sites", ttl=0)
                        
                        # 3. Add to the FRESH list
                            final_sites = pd.concat([fresh_sites, new_row], ignore_index=True)
                        
                        # 4. Save
                            save_data(final_sites, "Sites")
            with c2:
                if not df_sites.empty:
                    del_site = st.selectbox("Remove Site", df_sites["Name"].unique())
                    if st.button("🗑️ Delete Site"):
                        df_sites = df_sites[df_sites["Name"] != del_site]
                        save_data(df_sites, "Sites")
                        st.warning(f"Deleted '{del_site}'")
                        st.rerun()

        # --- TAB 2: MANAGE CONTRACTORS ---
        with tab2:
            st.subheader("👷 Manage Contractors & Rates")
            df_contractors = fetch_data("Contractors")
            if not df_contractors.empty:
                if "Effective_Date" in df_contractors.columns:
                    display_df = df_contractors.sort_values(by=["Name", "Effective_Date"], ascending=[True, False])
                else:
                    display_df = df_contractors
                st.dataframe(display_df, hide_index=True, use_container_width=True)

            st.divider()

            # 1. ADD NEW
            with st.expander("➕ Add New Contractor", expanded=False):
                c_name = st.text_input("New Contractor Name")
                c_date = st.date_input("Start Date", datetime.today())
                c1, c2, c3 = st.columns(3)
                m_rate = c1.number_input("Mason Rate", value=800)
                h_rate = c2.number_input("Helper Rate", value=500)
                l_rate = c3.number_input("Ladies Rate", value=400)

                if st.button("Add Contractor"):
                    if c_name:
                        if not df_contractors.empty and c_name in df_contractors["Name"].values:
                            st.error("Contractor exists. Use 'Edit Rates'.")
                        else:
                            new_data = {
                                "Name": c_name, "Mason_Rate": m_rate, "Helper_Rate": h_rate, "Ladies_Rate": l_rate,
                                "Effective_Date": str(c_date)
                            }
                            new_row = pd.DataFrame([new_data])
                            df_contractors = pd.concat([df_contractors, new_row], ignore_index=True)
                            save_data(df_contractors, "Contractors")
                            st.success(f"Added {c_name}")
                            st.rerun()

            # 2. UPDATE RATES
            with st.expander("📅 Update Rates (Effective Date)", expanded=True):
                if not df_contractors.empty:
                    edit_name = st.selectbox("Select Contractor to Update", df_contractors["Name"].unique())
                    st.info(f"New rate rule for **{edit_name}**. Old rates remain for past dates.")
                    new_eff_date = st.date_input("New Rates Effective From:", datetime.today())

                    current_rates = get_applicable_rates(edit_name, datetime.today())
                    ec1, ec2, ec3 = st.columns(3)
                    new_m_rate = ec1.number_input("New Mason Rate", value=current_rates['Mason'])
                    new_h_rate = ec2.number_input("New Helper Rate", value=current_rates['Helper'])
                    new_l_rate = ec3.number_input("New Ladies Rate", value=current_rates['Ladies'])

                    if st.button("💾 Save New Rates"):
                        df_contractors["Effective_Date"] = pd.to_datetime(df_contractors["Effective_Date"],
                                                                          errors='coerce')
                        mask = (df_contractors["Name"] == edit_name) & (
                                    df_contractors["Effective_Date"] == pd.to_datetime(new_eff_date))

                        if df_contractors[mask].empty:
                            new_entry = {
                                "Name": edit_name, "Mason_Rate": new_m_rate, "Helper_Rate": new_h_rate,
                                "Ladies_Rate": new_l_rate,
                                "Effective_Date": str(new_eff_date)
                            }
                            df_contractors = pd.concat([df_contractors, pd.DataFrame([new_entry])], ignore_index=True)
                            st.success(f"New Rate Rule Added! Effective from {new_eff_date}")
                        else:
                            df_contractors.loc[mask, "Mason_Rate"] = new_m_rate
                            df_contractors.loc[mask, "Helper_Rate"] = new_h_rate
                            df_contractors.loc[mask, "Ladies_Rate"] = new_l_rate
                            st.success(f"Updated existing rates for {new_eff_date}")

                        df_contractors["Effective_Date"] = df_contractors["Effective_Date"].astype(str)
                        save_data(df_contractors, "Contractors")
                        st.rerun()

            # 3. DELETE
            with st.expander("🗑️ Remove Contractor Completely"):
                if not df_contractors.empty:
                    del_cont = st.selectbox("Select Contractor to Remove", df_contractors["Name"].unique())
                    if st.button("Delete Contractor"):
                        df_contractors = df_contractors[df_contractors["Name"] != del_cont]
                        save_data(df_contractors, "Contractors")
                        st.warning(f"Deleted {del_cont}")
                        st.rerun()

        # --- TAB 3: USERS ---
        with tab3:
            st.header("Authorize Users")
            df_users = fetch_data("Users")
            if not df_users.empty:
                st.dataframe(df_users, hide_index=True)

            new_email = st.text_input("User Email")
            if st.button("Authorize"):
                new_email = new_email.strip()
                if not df_users.empty and new_email in df_users["Email"].astype(str).values:
                    st.error("User already exists")
                else:
                    new_row = pd.DataFrame([{"Email": new_email, "Name": ""}])
                    df_users = pd.concat([df_users, new_row], ignore_index=True)
                    save_data(df_users, "Users")
                    st.success("User Authorized")
                    st.rerun()

        # --- TAB 4: RAW DATA ---
        with tab4:
            st.header("Raw Data Log")
            df = fetch_data("Entries")
            st.dataframe(df)

        # --- TAB 5: WEEKLY BILL (UPDATED) ---
        with tab5:
            st.header("🧾 Weekly Bill Preview")
            end_date = st.date_input("Select Week Ending Date (Friday)")
            start_date = end_date - timedelta(days=6)
            st.write(f"**Billing Period:** Saturday {start_date} ➡ Friday {end_date}")

            if st.button("Generate Bill View"):
                df = fetch_data("Entries")
                if not df.empty:
                    df["Date_Obj"] = pd.to_datetime(df["Date"])
                    mask = (df["Date_Obj"] >= pd.to_datetime(start_date)) & (df["Date_Obj"] <= pd.to_datetime(end_date))
                    bill_df = df.loc[mask].copy()

                    if not bill_df.empty:
                        cols = ["Mason_Count", "Helper_Count", "Ladies_Count", "Total_Cost"]
                        for c in cols: bill_df[c] = pd.to_numeric(bill_df[c])

                        # --- MODIFICATION: GROUP BY CONTRACTOR AND SITE ---
                        summary_df = bill_df.groupby(["Contractor", "Site"])[cols].sum().reset_index()

                        # Rename columns
                        summary_df.columns = ["Contractor", "Site", "Total Masons", "Total Helpers", "Total Ladies",
                                              "Total Pay (₹)"]

                        # Sort for better readability
                        summary_df = summary_df.sort_values(by=["Contractor", "Site"])

                        st.subheader("💰 Payment Summary (By Site)")
                        st.dataframe(summary_df, use_container_width=True)
                        st.success(f"**GRAND TOTAL: ₹{summary_df['Total Pay (₹)'].sum():,}**")

                        st.divider()
                        st.subheader("📄 Detailed Entries")

                        detail_cols = ["Date", "Site", "Contractor", "Mason_Count", "Helper_Count", "Ladies_Count",
                                       "Total_Cost"]
                        if "Work_Description" in bill_df.columns:
                            detail_cols.append("Work_Description")
                        detail_cols.append("Submitted_Name")

                        st.dataframe(bill_df[detail_cols], use_container_width=True)

                        csv = bill_df.to_csv(index=False).encode('utf-8')
                        st.download_button("⬇️ Download CSV", csv, "bill.csv", "text/csv")
                    else:
                        st.warning("No records found in this date range.")
                else:
                    st.warning("Database is empty.")

# ==========================================
# 👷 USER ENTRY
# ==========================================
else:
    st.title("📋 Daily Labour Entry")

    email = st.text_input("Enter your Registered Email")

    if email:
        final_name = get_user_profile(email)

        if final_name is not None:
            if final_name == "" or pd.isna(final_name):
                st.warning("First time login: Please set your name.")
                input_name = st.text_input("Enter Your Name (Set One Time)")
                if st.button("Save Name"):
                    update_user_name(email, input_name)
                    st.success("Name saved! Please reload.")
                    st.rerun()
            else:
                st.success(f"Welcome back, **{final_name}**!")

                sites = get_sites()
                contractor_list = get_contractor_names()

                if not sites:
                    st.error("⚠️ No Sites found!")
                elif not contractor_list:
                    st.error("⚠️ No Contractors found!")
                else:
                    st.markdown("### 1. Select Date & Location")
                    col_a, col_b = st.columns(2)
                    date_val = col_a.date_input("Date", datetime.now())
                    site = col_b.selectbox("Select Site", sites)

                    st.caption(f"Activity at **{site}** on {date_val}:")
                    overview_df = get_site_overview(date_val, site)
                    if not overview_df.empty:
                        st.dataframe(overview_df, hide_index=True)
                    else:
                        st.text("No entries yet.")

                    st.write("---")

                    st.markdown("### 2. Select Contractor")
                    contractor = st.selectbox("Select Contractor", contractor_list)

                    rates = get_applicable_rates(contractor, date_val)
                    idx, full_df = check_existing_entry(date_val, site, contractor)

                    # Initialize values
                    val_m, val_h, val_l = 0.0, 0.0, 0.0
                    val_desc = ""

                    edit_mode = False
                    locked = False

                    if idx is not None:
                        # Fixed Logic: accessing row from full dataframe safely
                        row = full_df.loc[idx]
                        val_m = float(row["Mason_Count"])
                        val_h = float(row["Helper_Count"])
                        val_l = float(row["Ladies_Count"])

                        if "Work_Description" in row:
                            val_desc = str(row["Work_Description"])
                            if val_desc == "nan": val_desc = ""

                        edit_cnt = int(row["Edit_Count"])
                        edit_mode = True
                        if edit_cnt >= 2:
                            st.error(f"🔒 Locked. (Edited {edit_cnt}/2 times)")
                            locked = True
                        else:
                            st.info(f"✏️ Editing existing entry.")

                    with st.form("entry_form"):
                        st.markdown(f"### 3. Enter Labour Details")

                        c1, c2, c3 = st.columns(3)
                        n_mason = c1.number_input("Masons", min_value=0.0, value=val_m, step=0.5, format="%.1f",
                                                  disabled=locked)
                        n_helper = c2.number_input("Helpers", min_value=0.0, value=val_h, step=0.5, format="%.1f",
                                                   disabled=locked)
                        n_ladies = c3.number_input("Ladies", min_value=0.0, value=val_l, step=0.5, format="%.1f",
                                                   disabled=locked)

                        st.write("**Daily Activity:**")
                        work_desc = st.text_area("What work was done today?", value=val_desc,
                                                 placeholder="e.g. Plastering 2nd floor...", disabled=locked)

                        total_cost = (n_mason * rates['Mason']) + (n_helper * rates['Helper']) + (
                                    n_ladies * rates['Ladies'])

                        if locked:
                            submit = st.form_submit_button("🔒 Locked", disabled=True)
                        elif edit_mode:
                            submit = st.form_submit_button("🔄 Update Entry")
                        else:
                            submit = st.form_submit_button("✅ Submit New Entry")

                        if submit and not locked:
                            if edit_mode:
                                full_df.at[idx, "Mason_Count"] = n_mason
                                full_df.at[idx, "Helper_Count"] = n_helper
                                full_df.at[idx, "Ladies_Count"] = n_ladies
                                full_df.at[idx, "Total_Cost"] = total_cost
                                full_df.at[idx, "Work_Description"] = work_desc
                                full_df.at[idx, "Edit_Count"] = full_df.at[idx, "Edit_Count"] + 1
                                save_data(full_df, "Entries")
                                st.success("Updated Successfully!")
                            else:
                                new_entry = {
                                    "Date": str(date_val), "Site": site, "Contractor": contractor,
                                    "Mason_Count": n_mason, "Helper_Count": n_helper, "Ladies_Count": n_ladies,
                                    "Total_Cost": total_cost, "Work_Description": work_desc,
                                    "Submitted_Email": email, "Submitted_Name": final_name,
                                    "Edit_Count": 0
                                }
 # Create the small dataframe for the new entry
            new_df = pd.DataFrame([new_entry])

            # 1. Download the REAL latest data from Google right now
            #    (This prevents the "deleting old sites" bug)
            fresh_df = conn.read(worksheet="Entries", ttl=0)

            # 2. Add your new row to the FRESH list
            final_df = pd.concat([fresh_df, new_df], ignore_index=True)

            # 3. Save (The app will automatically refresh after this line because we fixed save_data)
            save_data(final_df, "Entries")