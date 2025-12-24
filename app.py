import streamlit as st
import pandas as pd
import json
from datetime import datetime, date, timedelta
from supabase import create_client
from fpdf import FPDF
import io

# Setup page config
st.set_page_config(
    page_title="LabourPro", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# Admin security code for deleting logs
# Change this if you need a new password
ADMIN_DELETE_CODE = "9512" 

# Initialize Supabase connection
# Uses st.cache_resource so it doesn't reconnect on every reload
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        st.error("Could not connect to Supabase. Please check secrets.")
        st.stop()

supabase = init_connection()

# Apply some custom CSS to make it look clean (black text on white bg)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    * { color: #000000 !important; }
    
    /* Inputs */
    input, textarea, select {
        background-color: #FFFFFF !important; 
        color: #000000 !important; 
        border: 1px solid #ccc !important; 
    }
    
    /* Table headers */
    th { background-color: #E0E0E0 !important; border-bottom: 2px solid #000 !important; }
    
    /* Primary buttons */
    button[kind="primary"] { 
        background-color: #F39C12 !important; 
        color: white !important; 
        border: none !important; 
    }
    </style>
""", unsafe_allow_html=True)


# --- Helper Functions ---

def fetch_data(table_name):
    """Simple helper to get all rows from a table as a dataframe"""
    response = supabase.table(table_name).select("*").execute()
    return pd.DataFrame(response.data)

def get_billing_start_date(entry_date):
    # Find the previous Saturday for billing cycles
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

# PDF Generation Class
class PDFBill(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Labour Payment Bill', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_bytes(site_name, week_label, billing_data):
    pdf = PDFBill()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Site: {site_name}", 0, 1, 'L')
    pdf.cell(0, 10, f"Week: {week_label}", 0, 1, 'L')
    pdf.ln(5)

    for con in billing_data:
        # Grey background for contractor name
        pdf.set_fill_color(220, 220, 220)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Contractor: {con['name']}", 0, 1, 'L', fill=True)
        
        # Headers
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Date", 1)
        pdf.cell(20, 8, "Mason", 1)
        pdf.cell(20, 8, "Helper", 1)
        pdf.cell(20, 8, "Ladies", 1)
        pdf.ln()
        
        # Rows
        pdf.set_font("Arial", '', 10)
        for row in con['rows']:
            pdf.cell(30, 8, str(row['Date']), 1)
            pdf.cell(20, 8, str(row['Mason']), 1)
            pdf.cell(20, 8, str(row['Helper']), 1)
            pdf.cell(20, 8, str(row['Ladies']), 1)
            pdf.ln()

        # Totals
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Total Shifts", 1)
        pdf.cell(20, 8, str(con['totals']['m']), 1)
        pdf.cell(20, 8, str(con['totals']['h']), 1)
        pdf.cell(20, 8, str(con['totals']['l']), 1)
        pdf.ln()

        # Rates used
        pdf.cell(30, 8, "Rate", 1)
        pdf.cell(20, 8, str(int(con['rates']['rm'])), 1)
        pdf.cell(20, 8, str(int(con['rates']['rh'])), 1)
        pdf.cell(20, 8, str(int(con['rates']['rl'])), 1)
        pdf.ln()

        # Final amount
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(90, 10, f"Total Amount: Rs. {con['totals']['amt']:,.2f}", 1, 0, 'R')
        pdf.ln(15)

    return pdf.output(dest='S').encode('latin-1')


def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty:
        st.info("No data available.")
        return

    # Fix date formats
    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors='coerce')
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"], errors='coerce').dt.date
    
    df_entries = df_entries.dropna(subset=["date_dt"])
    
    # Calculate weeks
    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
    
    unique_weeks = sorted(df_entries["week_label"].unique(), reverse=True)
    
    sel_week = st.selectbox("Select Week", unique_weeks)
    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    
    # Iterate through sites for the selected week
    for site_name in df_week["site"].unique():
        st.markdown(f"### 📍 Site: {site_name}")
        df_site = df_week[df_week["site"] == site_name]
        
        pdf_data = []

        for con_name in df_site["contractor"].unique():
            st.markdown(f"#### 👷 Contractor: {con_name}")
            df_con_entries = df_site[df_site["contractor"] == con_name].sort_values("date")
            
            rows = []
            total_m, total_h, total_l, total_amt = 0, 0, 0, 0
            
            for _, row in df_con_entries.iterrows():
                rows.append({
                    "Date": row["date_dt"].strftime("%d-%m-%Y"),
                    "Mason": row["count_mason"],
                    "Helper": row["count_helper"],
                    "Ladies": row["count_ladies"]
                })
                total_m += row["count_mason"]
                total_h += row["count_helper"]
                total_l += row["count_ladies"]
                total_amt += row["total_cost"]

            # Find the correct rate based on effective date
            rates = df_contractors[df_contractors["name"] == con_name].sort_values("effective_date", ascending=False)
            rm, rh, rl = 0, 0, 0
            
            if not rates.empty:
                week_start = df_week.iloc[0]["start_date"]
                valid_rates = rates[rates["effective_date"] <= week_start]
                if not valid_rates.empty:
                    curr = valid_rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]
                else:
                    # Fallback to latest if nothing found before start date
                    curr = rates.iloc[0]
                    rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]
            
            pdf_data.append({
                "name": con_name,
                "rows": rows,
                "totals": {"m": total_m, "h": total_h, "l": total_l, "amt": total_amt},
                "rates": {"rm": rm, "rh": rh, "rl": rl}
            })

            # Render HTML table for preview
            # Using simple html for better control over layout
            table_html = f"""
            <table style="width:100%; border-collapse: collapse; color: black; background: white;">
                <tr style="background: #e0e0e0;">
                    <th style="padding:8px; border:1px solid #ccc;">Date</th>
                    <th style="padding:8px; border:1px solid #ccc;">Mason</th>
                    <th style="padding:8px; border:1px solid #ccc;">Helper</th>
                    <th style="padding:8px; border:1px solid #ccc;">Ladies</th>
                </tr>
            """
            for r in rows:
                table_html += f"""
                <tr>
                    <td style="padding:8px; border:1px solid #ccc;">{r['Date']}</td>
                    <td style="padding:8px; border:1px solid #ccc;">{r['Mason']}</td>
                    <td style="padding:8px; border:1px solid #ccc;">{r['Helper']}</td>
                    <td style="padding:8px; border:1px solid #ccc;">{r['Ladies']}</td>
                </tr>
                """
            # Totals row
            table_html += f"""
                <tr style="font-weight: bold; background: #f9f9f9;">
                    <td style="padding:8px; border:1px solid #ccc;">Total</td>
                    <td style="padding:8px; border:1px solid #ccc;">{total_m}</td>
                    <td style="padding:8px; border:1px solid #ccc;">{total_h}</td>
                    <td style="padding:8px; border:1px solid #ccc;">{total_l}</td>
                </tr>
                <tr style="font-weight: bold; background: #e0e0e0;">
                    <td style="padding:8px; border:1px solid #ccc;">Amount</td>
                    <td colspan="3" style="padding:8px; border:1px solid #ccc; text-align:center;">₹{total_amt:,.0f}</td>
                </tr>
            </table><br>
            """
            st.markdown(table_html, unsafe_allow_html=True)
        
        # Download Button
        if pdf_data:
            try:
                pdf_bytes = generate_pdf_bytes(site_name, sel_week, pdf_data)
                fname = f"Bill_{site_name}_{sel_week}.pdf".replace(" ", "_")
                st.download_button(
                    label=f"⬇️ Download PDF ({site_name})",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    key=f"btn_{site_name}"
                )
            except Exception as e:
                st.error(f"Error generating PDF: {e}")
        
        st.divider()

# --- Login System ---

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["phone"] = None
    st.session_state["role"] = None

def show_login_screen():
    c1, c2, c3 = st.columns([1, 10, 1])
    
    with c2:
        st.title("🏗️ LabourPro")
        st.caption("Site Entry Portal")
        st.divider()
        
        st.subheader("Team Login")
        with st.form("login_form"):
            phone = st.text_input("Enter Mobile Number", max_chars=10, placeholder="98765xxxxx")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                try:
                    res = supabase.table("users").select("*").eq("phone", phone).execute()
                    if res.data:
                        user = res.data[0]
                        if user.get("status") == "Resigned":
                            st.error("Account is inactive.")
                        elif user.get("role") == "admin":
                            st.error("Please use Admin Login below.")
                        else:
                            st.session_state["logged_in"] = True
                            st.session_state["phone"] = user["phone"]
                            st.session_state["role"] = "user"
                            st.rerun()
                    else:
                        st.error("User not found.")
                except Exception as e:
                    st.error(f"Login error: {e}")

        st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("🔐 Admin Login"):
            with st.form("admin_form"):
                adm_ph = st.text_input("Admin Mobile")
                adm_pw = st.text_input("Password", type="password")
                if st.form_submit_button("Admin Login", use_container_width=True):
                    # Check against secrets or default
                    real_pw = st.secrets["general"]["admin_password"] if "general" in st.secrets else "admin123"
                    
                    if adm_pw == real_pw:
                        res = supabase.table("users").select("*").eq("phone", adm_ph).execute()
                        if res.data and res.data[0].get("role") == "admin":
                            st.session_state["logged_in"] = True
                            st.session_state["phone"] = res.data[0]["phone"]
                            st.session_state["role"] = "admin"
                            st.rerun()
                        else:
                            st.error("Not an admin account")
                    else:
                        st.error("Wrong password")

if not st.session_state["logged_in"]:
    show_login_screen()
    st.stop()


# --- Main Application ---

with st.sidebar:
    st.write("### Profile")
    st.info(f"Role: **{st.session_state['role'].upper()}**")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# Define tabs based on role
tabs = ["Daily Entry"]
if st.session_state["role"] == "admin":
    tabs.extend(["Site Logs", "Weekly Bill", "Manage Sites", "Contractors", "Users", "Settings"])

page = st.selectbox("Navigate", tabs)
st.divider()


# 1. Daily Entry Page
if page == "Daily Entry":
    df_sites = fetch_data("sites")
    df_con = fetch_data("contractors")

    if df_sites.empty:
        st.warning("No sites found. Please add sites first.")
    else:
        # Filter sites for non-admins
        site_list = df_sites["name"].unique().tolist()
        if st.session_state["role"] != "admin":
            res = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
            user_site = res.data.get("assigned_site") if res.data else None
            
            if user_site and user_site in site_list:
                site_list = [user_site]
            elif "All" in site_list:
                pass 
            else:
                st.error("No site assigned to you.")
                st.stop()

        st.subheader("New Work Entry")
        
        c1, c2, c3 = st.columns(3)
        date_pick = c1.date_input("Date", date.today(), format="DD-MM-YYYY")
        site_pick = c2.selectbox("Site", site_list)
        
        con_list = df_con["name"].unique() if not df_con.empty else []
        if len(con_list) == 0:
            st.error("No contractors found.")
            st.stop()
            
        con_pick = c3.selectbox("Contractor", con_list)
        
        # Check if entry exists
        existing_entry = None
        try:
            check = supabase.table("entries").select("*").eq("date", str(date_pick)).eq("site", site_pick).eq("contractor", con_pick).execute()
            if check.data:
                existing_entry = check.data[0]
        except:
            pass

        # Pre-fill values if editing
        val_m, val_h, val_l, desc = 0.0, 0.0, 0.0, ""
        mode = "new"
        
        if existing_entry:
            mode = "edit"
            st.warning("✏️ You are editing an existing entry.")
            val_m = float(existing_entry.get("count_mason", 0))
            val_h = float(existing_entry.get("count_helper", 0))
            val_l = float(existing_entry.get("count_ladies", 0))
            desc = existing_entry.get("work_description", "")

        k1, k2, k3 = st.columns(3)
        num_m = k1.number_input("Mason", value=val_m, step=0.5)
        num_h = k2.number_input("Helper", value=val_h, step=0.5)
        num_l = k3.number_input("Ladies", value=val_l, step=0.5)
        
        work_desc = st.text_area("Description", value=desc)

        # Calculate costs logic
        rate_info = None
        try:
            # Get latest rate effective before or on the entry date
            q = supabase.table("contractors").select("*").eq("name", con_pick).lte("effective_date", str(date_pick)).order("effective_date", desc=True).limit(1).execute()
            if q.data:
                rate_info = q.data[0]
        except:
            pass

        if rate_info:
            total_cost = (num_m * rate_info['rate_mason']) + (num_h * rate_info['rate_helper']) + (num_l * rate_info['rate_ladies'])
            
            # Only show cost to admins
            if st.session_state["role"] == "admin":
                st.info(f"💰 Est. Cost: ₹{total_cost:,.2f}")
            
            if st.button("Save Entry", type="primary", use_container_width=True): 
                payload = {
                    "date": str(date_pick), 
                    "site": site_pick, 
                    "contractor": con_pick, 
                    "count_mason": num_m, 
                    "count_helper": num_h, 
                    "count_ladies": num_l, 
                    "total_cost": total_cost, 
                    "work_description": work_desc
                }
                
                if mode == "new":
                    supabase.table("entries").insert(payload).execute()
                else:
                    supabase.table("entries").update(payload).eq("id", existing_entry["id"]).execute()
                
                st.success("Entry Saved!")
                st.rerun()
        else:
            st.error("No active rates found for this date.")


# 2. Site Logs (with Delete)
elif page == "Site Logs":
    st.subheader("Search Logs")
    
    entries_df = pd.DataFrame(supabase.table("entries").select("*").order("date", desc=True).execute().data)
    users_df = fetch_data("users")

    if not entries_df.empty:
        entries_df["date_obj"] = pd.to_datetime(entries_df["date"], errors='coerce')
        entries_df = entries_df.dropna(subset=["date_obj"])
        
        # Formatting for filters
        entries_df["display_date"] = entries_df["date_obj"].dt.strftime('%d-%m-%Y')
        entries_df["month_str"] = entries_df["date_obj"].dt.strftime('%B %Y')

        c1, c2 = st.columns(2)
        
        site_opts = ["All Sites"] + sorted(entries_df["site"].unique().tolist())
        filter_site = c1.selectbox("Filter by Site", site_opts)
        
        month_opts = ["All Months"] + sorted(entries_df["month_str"].unique().tolist(), reverse=True)
        filter_month = c2.selectbox("Filter by Month", month_opts)

        filtered_df = entries_df.copy()
        if filter_site != "All Sites": 
            filtered_df = filtered_df[filtered_df["site"] == filter_site]
        if filter_month != "All Months": 
            filtered_df = filtered_df[filtered_df["month_str"] == filter_month]

        # Map user to site if possible
        def get_user_label(s_name):
            if users_df.empty: return "?"
            matches = users_df[users_df["assigned_site"] == s_name]
            if not matches.empty:
                return ", ".join(matches["name"].tolist())
            return "Admin"

        filtered_df["entered_by"] = filtered_df["site"].apply(get_user_label)
        
        st.write(f"Found {len(filtered_df)} records")
        
        # Table for display
        to_show = filtered_df[[
            "id", "display_date", "site", "entered_by", "contractor", 
            "count_mason", "count_helper", "count_ladies", 
            "total_cost", "work_description"
        ]].rename(columns={
            "id": "ID (For Deletion)",
            "display_date": "Date", 
            "site": "Site", 
            "entered_by": "User",
            "contractor": "Contractor", 
            "count_mason": "Mason", 
            "count_helper": "Helper",
            "count_ladies": "Ladies", 
            "total_cost": "Cost", 
            "work_description": "Notes"
        })
        
        st.dataframe(to_show, use_container_width=True, hide_index=True)
        
        # Delete Section
        if st.session_state["role"] == "admin":
            st.divider()
            with st.expander("🗑️ Delete Entry"):
                st.warning("Deleting is permanent.")
                col_d1, col_d2 = st.columns([1, 2])
                
                del_id = col_d1.number_input("Entry ID", step=1, value=0)
                # Password field
                del_pass = col_d2.text_input("Enter Security Code", type="password")
                
                if st.button("Delete Permanently", type="primary"):
                    if del_pass == ADMIN_DELETE_CODE:
                        if del_id > 0:
                            supabase.table("entries").delete().eq("id", int(del_id)).execute()
                            st.success(f"Deleted ID {del_id}")
                            st.rerun()
                        else:
                            st.error("Invalid ID")
                    else:
                        st.error("Wrong Code")
    else:
        st.info("No logs found in database.")

elif page == "Weekly Bill":
    st.subheader("Generate Bill")
    
    e_data = fetch_data("entries")
    c_data = fetch_data("contractors")
    
    if not e_data.empty and not c_data.empty:
        render_weekly_bill(e_data, c_data)
    else:
        st.info("Need more data to generate bills.")

elif page == "Manage Sites":
    st.subheader("Sites")
    
    curr_sites = fetch_data("sites")
    st.dataframe(curr_sites, hide_index=True, use_container_width=True)
    
    st.write("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("#### Add New Site")
        new_s = st.text_input("Site Name")
        if st.button("Add"):
            if new_s:
                supabase.table("sites").insert({"name": new_s}).execute()
                st.success("Added")
                st.rerun()
            else:
                st.error("Name cannot be empty")

    with c2:
        st.write("#### Delete Site")
        # Safety check for deletion
        if "unlock_site_del" not in st.session_state: 
            st.session_state["unlock_site_del"] = False
            
        def unlock(): st.session_state["unlock_site_del"] = True
        
        # Simple backup blob
        backup = {
            "entries": fetch_data("entries").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "users": fetch_data("users").to_dict("records")
        }
        
        st.download_button("Download Backup to Unlock", 
                           data=json.dumps(backup, default=str), 
                           file_name="site_backup.json", 
                           on_click=unlock)
        
        if not curr_sites.empty:
            del_target = st.selectbox("Select Site", curr_sites["name"].unique())
            if st.button("Delete", disabled=not st.session_state["unlock_site_del"]):
                supabase.table("sites").delete().eq("name", del_target).execute()
                st.success("Deleted")
                st.session_state["unlock_site_del"] = False
                st.rerun()

elif page == "Contractors":
    st.subheader("Contractor Rates")
    
    df_con = fetch_data("contractors")
    
    if not df_con.empty:
        # Show table
        st.dataframe(
            df_con.sort_values(by=["name", "effective_date"], ascending=[True, False]), 
            use_container_width=True, 
            hide_index=True,
            column_config={"effective_date": st.column_config.DateColumn("Effective From", format="DD-MM-YYYY")}
        )
    else:
        st.info("No contractors yet.")

    st.write("---")
    st.write("#### Add / Update Rates")
    
    action = st.radio("Action:", ["Add New Contractor", "Update Existing Rate"], horizontal=True)
    
    with st.form("rate_form"):
        if action == "Update Existing Rate":
            if df_con.empty:
                st.warning("Add a contractor first.")
                c_name = ""
            else:
                c_name = st.selectbox("Select Contractor", df_con["name"].unique())
        else:
            c_name = st.text_input("Contractor Name")

        r1, r2, r3 = st.columns(3)
        rm = r1.number_input("Mason Rate", value=0)
        rh = r2.number_input("Helper Rate", value=0)
        rl = r3.number_input("Ladies Rate", value=0)
        
        eff_dt = st.date_input("New Prices Start From", value=date.today(), format="DD-MM-YYYY")
        
        if st.form_submit_button("Save"):
            if not c_name:
                st.error("Name needed.")
            elif rm == 0 and rh == 0 and rl == 0:
                st.error("Enter at least one rate.")
            else:
                supabase.table("contractors").insert({
                    "name": c_name, 
                    "rate_mason": rm, 
                    "rate_helper": rh, 
                    "rate_ladies": rl, 
                    "effective_date": str(eff_dt)
                }).execute()
                st.success("Updated!")
                st.rerun()

elif page == "Users":
    st.subheader("User Management")
    
    curr_users = fetch_data("users")
    st.dataframe(curr_users, use_container_width=True)
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("#### Add / Edit User")
        with st.form("user_add"):
            u_ph = st.text_input("Phone", max_chars=10)
            u_name = st.text_input("Name")
            u_role = st.selectbox("Role", ["user", "admin"])
            
            # Site list for dropdown
            s_data = fetch_data("sites")
            s_opts = ["None/All"] + s_data["name"].tolist() if not s_data.empty else ["None/All"]
            u_site = st.selectbox("Assign Site", s_opts)
            
            if st.form_submit_button("Save User"):
                if u_ph:
                    site_val = None if u_site == "None/All" else u_site
                    
                    # Check if exists
                    check = supabase.table("users").select("*").eq("phone", u_ph).execute().data
                    if check:
                        supabase.table("users").update({
                            "name": u_name, 
                            "role": u_role, 
                            "assigned_site": site_val
                        }).eq("phone", u_ph).execute()
                    else:
                        supabase.table("users").insert({
                            "phone": u_ph, 
                            "name": u_name, 
                            "role": u_role, 
                            "assigned_site": site_val, 
                            "status": "Active"
                        }).execute()
                    st.success("Saved")
                    st.rerun()
                else:
                    st.error("Phone required")

    with c2:
        st.write("#### Deactivate User")
        if not curr_users.empty:
            active_usrs = curr_users[curr_users["role"] != "admin"]
            # Exclude already resigned if status column exists
            if "status" in active_usrs.columns:
                active_usrs = active_usrs[active_usrs["status"] == "Active"]
            
            if not active_usrs.empty:
                # Create label like "Name (Phone)"
                u_opts = [f"{r['name']} ({r['phone']})" for _, r in active_usrs.iterrows()]
                sel_u = st.selectbox("Select User", u_opts)
                
                if st.button("Resign User"):
                    ph_extract = sel_u.split("(")[-1].replace(")", "")
                    supabase.table("users").update({"status": "Resigned"}).eq("phone", ph_extract).execute()
                    st.success("User deactivated")
                    st.rerun()
            else:
                st.info("No active users to resign.")

elif page == "Settings":
    st.subheader("Settings & Recovery")
    
    t1, t2, t3 = st.tabs(["Reset Data", "Archives", "Restore"])
    
    with t1:
        st.write("### New Year Reset")
        st.info("Download backup first.")
        
        if "reset_unlocked" not in st.session_state: 
            st.session_state["reset_unlocked"] = False
        
        def allow_reset(): st.session_state["reset_unlocked"] = True
        
        full_backup = {
            "entries": fetch_data("entries").to_dict("records"),
            "contractors": fetch_data("contractors").to_dict("records"),
            "sites": fetch_data("sites").to_dict("records"),
            "users": fetch_data("users").to_dict("records"),
            "ts": str(datetime.now())
        }
        
        st.download_button("1. Download Full Backup", 
                           data=json.dumps(full_backup, default=str), 
                           file_name="full_backup.json", 
                           on_click=allow_reset)
        
        st.write("---")
        confirm = st.text_input("Type 'DELETE ALL' to confirm:")
        
        if st.button("2. Clear All Entries", type="primary", disabled=not st.session_state["reset_unlocked"]):
            if confirm == "DELETE ALL":
                supabase.table("entries").delete().neq("id", 0).execute()
                st.success("Done. System is clean.")
                st.session_state["reset_unlocked"] = False
            else:
                st.error("Typo in confirmation text.")

    with t2:
        st.write("### View Backup File")
        f = st.file_uploader("Upload JSON", type=["json"], key="view_up")
        
        if f:
            try:
                d = json.load(f)
                st.success("Loaded")
                
                cat = st.selectbox("View:", ["Entries", "Users", "Sites", "Contractors"])
                
                key_map = {"Entries": "entries", "Users": "users", "Sites": "sites", "Contractors": "contractors"}
                
                if d.get(key_map[cat]):
                    st.dataframe(pd.DataFrame(d[key_map[cat]]), use_container_width=True)
                else:
                    st.warning("Empty category")
            except:
                st.error("Bad file")

    with t3:
        st.error("⚠️ Restore Data (Be Careful)")
        
        f_res = st.file_uploader("Upload Backup to Restore", type=["json"], key="res_up")
        
        if f_res:
            d = json.load(f_res)
            st.write(f"Entries found: {len(d.get('entries', []))}")
            
            if st.button("Start Restore", type="primary"):
                progress = st.progress(0)
                status = st.empty()
                
                # Helper to remove IDs so supabase creates new ones
                def clean_rows(rows):
                    cleaned = []
                    for r in rows:
                        if 'id' in r: del r['id']
                        cleaned.append(r)
                    return cleaned

                try:
                    # Restore Sites
                    if d.get("sites"):
                        status.write("Restoring sites...")
                        supabase.table("sites").upsert(clean_rows(d["sites"]), on_conflict="name").execute()
                    progress.progress(20)

                    # Restore Users
                    if d.get("users"):
                        status.write("Restoring users...")
                        supabase.table("users").upsert(clean_rows(d["users"]), on_conflict="phone").execute()
                    progress.progress(40)
                    
                    # Restore Contractors
                    if d.get("contractors"):
                        status.write("Restoring contractors...")
                        try:
                            supabase.table("contractors").upsert(clean_rows(d["contractors"])).execute()
                        except: pass
                    progress.progress(60)

                    # Restore Entries (Batched)
                    if d.get("entries"):
                        status.write("Restoring entries...")
                        entries = clean_rows(d["entries"])
                        batch_size = 50
                        for i in range(0, len(entries), batch_size):
                            batch = entries[i:i+batch_size]
                            supabase.table("entries").insert(batch).execute()
                    
                    progress.progress(100)
                    status.success("Restore Finished!")
                    # Removed balloons here per request
                    
                except Exception as ex:
                    st.error(f"Failed: {ex}")