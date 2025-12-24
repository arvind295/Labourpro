import streamlit as st
import pandas as pd
import json
from datetime import datetime, date, timedelta
from supabase import create_client
from fpdf import FPDF
import io

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(
    page_title="LabourPro", 
    page_icon="🏗️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# LOAD SECRETS (Password Management)
try:
    if "general" in st.secrets:
        ADMIN_DELETE_CODE = st.secrets["general"].get("admin_delete_code", "9512")
        ADMIN_LOGIN_PASS = st.secrets["general"].get("admin_password", "admin123")
    else:
        ADMIN_DELETE_CODE = "9512"
        ADMIN_LOGIN_PASS = "admin123"
except Exception:
    ADMIN_DELETE_CODE = "9512"
    ADMIN_LOGIN_PASS = "admin123"

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
        
        /* Sidebar Styling */
        section[data-testid="stSidebar"] { background-color: #F8F9FA !important; border-right: 1px solid #E0E0E0; }
        section[data-testid="stSidebar"] * { color: #000000 !important; }
        
        /* Inputs, Tables, Select Boxes */
        input, textarea, select, div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important; 
            color: #000000 !important; 
            border: 1px solid #ccc !important; 
        }
        /* MultiSelect Tag Styling */
        span[data-baseweb="tag"] {
            background-color: #E0E0E0 !important;
            color: black !important;
        }

        div[data-testid="stDataFrame"], div[data-testid="stTable"] {
            color: #000000 !important; 
            background-color: #FFFFFF !important;
        }
        
        /* Table Headers & Cells */
        th { background-color: #E0E0E0 !important; border-bottom: 2px solid #000 !important; }
        td { border-bottom: 1px solid #ddd !important; }
        
        /* Buttons */
        button[kind="primary"] { 
            background-color: #F39C12 !important; 
            color: #FFFFFF !important; 
            border: none !important; 
        }
        button[disabled] { 
            background-color: #cccccc !important; 
            color: #666666 !important; 
            cursor: not-allowed; 
        }
        
        /* Mobile Adjustments */
        @media only screen and (max-width: 600px) {
            h1 { font-size: 1.8rem !important; }
            .stButton button { width: 100% !important; }
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_styling()

# --- 4. HELPER FUNCTIONS & PDF ENGINE ---
def fetch_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def get_billing_start_date(entry_date):
    days_since_saturday = (entry_date.weekday() + 2) % 7
    return entry_date - timedelta(days=days_since_saturday)

class PDFBill(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Labour Payment Bill', 0, 1, 'C'); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_bytes(site_name, week_label, billing_data):
    pdf = PDFBill()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Site: {site_name}", 0, 1, 'L')
    pdf.cell(0, 10, f"Week: {week_label}", 0, 1, 'L'); pdf.ln(5)

    for con in billing_data:
        pdf.set_fill_color(220, 220, 220); pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Contractor: {con['name']}", 0, 1, 'L', fill=True)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Date", 1); pdf.cell(20, 8, "Mason", 1)
        pdf.cell(20, 8, "Helper", 1); pdf.cell(20, 8, "Ladies", 1); pdf.ln()
        
        pdf.set_font("Arial", '', 10)
        for row in con['rows']:
            pdf.cell(30, 8, str(row['Date']), 1); pdf.cell(20, 8, str(row['Mason']), 1)
            pdf.cell(20, 8, str(row['Helper']), 1); pdf.cell(20, 8, str(row['Ladies']), 1); pdf.ln()

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 8, "Totals", 1); pdf.cell(20, 8, str(con['totals']['m']), 1)
        pdf.cell(20, 8, str(con['totals']['h']), 1); pdf.cell(20, 8, str(con['totals']['l']), 1); pdf.ln()
        
        pdf.cell(30, 8, "Rate", 1); pdf.cell(20, 8, str(int(con['rates']['rm'])), 1)
        pdf.cell(20, 8, str(int(con['rates']['rh'])), 1); pdf.cell(20, 8, str(int(con['rates']['rl'])), 1); pdf.ln()

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(90, 10, f"Total: Rs. {con['totals']['amt']:,.2f}", 1, 0, 'R'); pdf.ln(15)
    return pdf.output(dest='S').encode('latin-1')

def render_weekly_bill(df_entries, df_contractors):
    if df_entries.empty: st.info("No data available."); return
    
    # Ensure date format
    df_entries["date_dt"] = pd.to_datetime(df_entries["date"], errors='coerce')
    df_contractors["effective_date"] = pd.to_datetime(df_contractors["effective_date"], errors='coerce').dt.date
    df_entries = df_entries.dropna(subset=["date_dt"])
    
    # Calculate billing weeks
    df_entries["start_date"] = df_entries["date_dt"].dt.date.apply(get_billing_start_date)
    df_entries["end_date"] = df_entries["start_date"] + timedelta(days=6)
    df_entries["week_label"] = df_entries.apply(lambda x: f"{x['start_date'].strftime('%d-%m-%Y')} to {x['end_date'].strftime('%d-%m-%Y')}", axis=1)
    
    weeks = sorted(df_entries["week_label"].unique(), reverse=True)
    sel_week = st.selectbox("Select Week", weeks) if weeks else None
    if not sel_week: return

    df_week = df_entries[df_entries["week_label"] == sel_week].copy()
    
    for site_name in df_week["site"].unique():
        st.markdown(f"### 📍 Site: {site_name}")
        df_site = df_week[df_week["site"] == site_name]
        pdf_site_data = []

        for con_name in df_site["contractor"].unique():
            st.markdown(f"#### 👷 Contractor: {con_name}")
            df_con_entries = df_site[df_site["contractor"] == con_name].sort_values("date")
            rows = []
            tm, th, tl, tamt = 0, 0, 0, 0
            
            for _, row in df_con_entries.iterrows():
                rows.append({"Date": row["date_dt"].strftime("%d-%m-%Y"), "Mason": row["count_mason"], "Helper": row["count_helper"], "Ladies": row["count_ladies"]})
                tm += row["count_mason"]; th += row["count_helper"]; tl += row["count_ladies"]; tamt += row["total_cost"]

            rates = df_contractors[df_contractors["name"] == con_name].sort_values("effective_date", ascending=False)
            rm, rh, rl = (0,0,0)
            if not rates.empty:
                valid_rates = rates[rates["effective_date"] <= df_week.iloc[0]["start_date"]]
                curr = valid_rates.iloc[0] if not valid_rates.empty else rates.iloc[0]
                rm, rh, rl = curr["rate_mason"], curr["rate_helper"], curr["rate_ladies"]
            
            pdf_site_data.append({"name": con_name, "rows": rows, "totals": {"m": tm, "h": th, "l": tl, "amt": tamt}, "rates": {"rm": rm, "rh": rh, "rl": rl}})

            st.markdown(f"""
            <table style="width:100%; border-collapse: collapse; color: black; background: white; font-size: 14px;">
            <tr style="background: #e0e0e0;"><th style="padding: 8px; border: 1px solid #ccc;">Date</th><th style="padding: 8px; border: 1px solid #ccc;">Mason</th><th style="padding: 8px; border: 1px solid #ccc;">Helper</th><th style="padding: 8px; border: 1px solid #ccc;">Ladies</th></tr>
            {''.join([f"<tr><td style='padding: 8px; border: 1px solid #ccc;'>{r['Date']}</td><td style='padding: 8px; border: 1px solid #ccc;'>{r['Mason']}</td><td style='padding: 8px; border: 1px solid #ccc;'>{r['Helper']}</td><td style='padding: 8px; border: 1px solid #ccc;'>{r['Ladies']}</td></tr>" for r in rows])}
            <tr style="font-weight: bold; background: #e0e0e0;"><td style="padding: 8px; border: 1px solid #ccc;">Total: ₹{tamt:,.0f}</td><td style="padding: 8px; border: 1px solid #ccc;">{tm}</td><td style="padding: 8px; border: 1px solid #ccc;">{th}</td><td style="padding: 8px; border: 1px solid #ccc;">{tl}</td></tr>
            </table><br>""", unsafe_allow_html=True)
        
        if pdf_site_data:
            try:
                pdf_bytes = generate_pdf_bytes(site_name, sel_week, pdf_site_data)
                st.download_button(label=f"⬇️ Download PDF ({site_name})", data=pdf_bytes, file_name=f"Bill_{site_name}_{sel_week}.pdf", mime="application/pdf", key=f"pdf_{site_name}")
            except: pass
        st.divider()

# --- 5. LOGIN SYSTEM ---
if "logged_in" not in st.session_state: st.session_state.update({"logged_in": False, "phone": None, "role": None})

def login_process():
    col1, col2, col3 = st.columns([1, 10, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center; color: black;'>🏗️ LabourPro</h1><p style='text-align: center; color: grey;'>Site Entry Portal</p><hr>", unsafe_allow_html=True)
        
        st.subheader("👷 Team Login")
        with st.form("u_log"):
            ph = st.text_input("Enter Mobile Number", max_chars=10)
            if st.form_submit_button("🚀 Login", type="primary", use_container_width=True):
                try:
                    d = supabase.table("users").select("*").eq("phone", ph).execute().data
                    if d:
                        if d[0].get("status") == "Resigned": st.error("⚠️ Account Deactivated.")
                        elif d[0].get("role") == "admin": st.error("Please use Admin Login below.")
                        else:
                            st.session_state.update({"logged_in": True, "phone": d[0]["phone"], "role": "user"})
                            st.rerun()
                    else: st.error("User not found.")
                except: st.error("Connection Error")

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔐 Admin Login"):
            with st.form("a_log"):
                ph_a = st.text_input("Admin Mobile"); pw_a = st.text_input("Password", type="password")
                if st.form_submit_button("Admin Login", use_container_width=True):
                    # SECURE PASSWORD CHECK FROM SECRETS
                    if pw_a == ADMIN_LOGIN_PASS:
                        try:
                            d = supabase.table("users").select("*").eq("phone", ph_a).execute().data
                            if d and d[0].get("role") == "admin":
                                st.session_state.update({"logged_in": True, "phone": d[0]["phone"], "role": "admin"})
                                st.rerun()
                            else: st.error("Not an Admin Account")
                        except: st.error("Error fetching user data")
                    else: st.error("Wrong Password")

if not st.session_state["logged_in"]: login_process(); st.stop()

# --- 6. MAIN APP LOGIC ---
with st.sidebar:
    st.info(f"Role: **{st.session_state['role'].upper()}**")
    if st.button("Logout"): st.session_state.clear(); st.rerun()

tabs = ["📝 Daily Entry"]
if st.session_state["role"] == "admin": tabs += ["🔍 Site Logs", "📊 Weekly Bill", "📍 Sites", "👷 Contractors", "👥 Users", "📂 Archive & Recovery"]
current_tab = st.selectbox("Navigate", tabs, label_visibility="collapsed"); st.divider()

# TAB 1: DAILY ENTRY
if current_tab == "📝 Daily Entry":
    df_sites = fetch_data("sites"); df_con = fetch_data("contractors")
    if df_sites.empty: st.warning("Admin must add sites.")
    else:
        av_sites = df_sites["name"].unique().tolist()
        
        # LOGIC FOR MULTIPLE ASSIGNED SITES
        if st.session_state["role"] != "admin":
            u = supabase.table("users").select("assigned_site").eq("phone", st.session_state["phone"]).single().execute()
            if u.data and u.data.get("assigned_site"):
                # Split the comma-separated string into a list
                raw_assignments = u.data.get("assigned_site", "")
                assigned_list = [s.strip() for s in raw_assignments.split(",")]
                
                # Filter available sites to only those assigned
                if "None/All" in assigned_list or "All" in assigned_list:
                    pass # User keeps all sites
                else:
                    av_sites = [s for s in av_sites if s in assigned_list]
            else:
                st.error("No site assigned."); st.stop()

        if not av_sites:
            st.error("You are assigned to sites that no longer exist.")
            st.stop()

        st.subheader("New Work Entry")
        c1, c2, c3 = st.columns(3)
        dt = c1.date_input("Date", date.today(), format="DD-MM-YYYY")
        st_sel = c2.selectbox("Site", av_sites)
        con_sel = c3.selectbox("Contractor", df_con["name"].unique()) if not df_con.empty else None
        
        if con_sel:
            exist = None
            try:
                r = supabase.table("entries").select("*").eq("date", str(dt)).eq("site", st_sel).eq("contractor", con_sel).execute()
                if r.data: exist = r.data[0]
            except: pass

            vm, vh, vl, vd, mode = (0.0, 0.0, 0.0, "", "new")
            if exist: mode = "edit"; vm, vh, vl, vd = float(exist.get("count_mason", 0)), float(exist.get("count_helper", 0)), float(exist.get("count_ladies", 0)), exist.get("work_description", ""); st.warning("✏️ Editing Entry")

            k1, k2, k3 = st.columns(3)
            nm = k1.number_input("Mason", value=vm, step=0.5)
            nh = k2.number_input("Helper", value=vh, step=0.5)
            nl = k3.number_input("Ladies", value=vl, step=0.5)
            wdesc = st.text_area("Description", value=vd)

            rate_row = None
            try:
                rr = supabase.table("contractors").select("*").eq("name", con_sel).lte("effective_date", str(dt)).order("effective_date", desc=True).limit(1).execute()
                if rr.data: rate_row = rr.data[0]
            except: pass

            if rate_row:
                cost = (nm * rate_row['rate_mason']) + (nh * rate_row['rate_helper']) + (nl * rate_row['rate_ladies'])
                if st.session_state["role"] == "admin": st.info(f"💰 Est Cost: ₹{cost:,.2f}")
                
                if st.button("Save Entry", type="primary", use_container_width=True): 
                    load = {"date": str(dt), "site": st_sel, "contractor": con_sel, "count_mason": nm, "count_helper": nh, "count_ladies": nl, "total_cost": cost, "work_description": wdesc}
                    if mode == "new": supabase.table("entries").insert(load).execute()
                    else: supabase.table("entries").update(load).eq("id", exist["id"]).execute()
                    st.success("Saved"); st.rerun()
            else: st.error("No rate found for this date.")

# TAB 2: SITE LOGS
elif current_tab == "🔍 Site Logs":
    st.subheader("🔍 Site Logs")
    df_e = pd.DataFrame(supabase.table("entries").select("*").order("date", desc=True).execute().data)
    if not df_e.empty:
        df_e["date_obj"] = pd.to_datetime(df_e["date"], errors='coerce'); df_e = df_e.dropna(subset=["date_obj"])
        df_e["Date"] = df_e["date_obj"].dt.strftime('%d-%m-%Y')
        
        c1, c2 = st.columns(2)
        fil_site = c1.selectbox("Filter Site", ["All"] + sorted(df_e["site"].unique().tolist()))
        if fil_site != "All": df_e = df_e[df_e["site"] == fil_site]
        
        st.dataframe(df_e[["id", "Date", "site", "contractor", "count_mason", "count_helper", "count_ladies", "total_cost", "work_description"]], use_container_width=True, hide_index=True)
        
        if st.session_state["role"] == "admin":
            st.divider()
            with st.expander("🗑️ Delete Entry"):
                col_d1, col_d2 = st.columns([1, 2])
                del_id = col_d1.number_input("ID to Delete", step=1, value=0)
                del_code = col_d2.text_input("Security Code", type="password")
                if st.button("Delete Permanently", type="primary"):
                    if del_code == ADMIN_DELETE_CODE:
                        supabase.table("entries").delete().eq("id", int(del_id)).execute(); st.success("Deleted"); st.rerun()
                    else: st.error("Wrong Code")
    else: st.info("No logs.")

# TAB 3: BILLING
elif current_tab == "📊 Weekly Bill":
    st.subheader("📊 Weekly Bill")
    render_weekly_bill(fetch_data("entries"), fetch_data("contractors"))

# TAB 4: SITE MANAGEMENT
elif current_tab == "📍 Sites":
    st.subheader("📍 Sites")
    st.dataframe(fetch_data("sites"), hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        n = st.text_input("New Site Name")
        if st.button("Add Site"): supabase.table("sites").insert({"name": n}).execute(); st.rerun()
    with c2:
        if "site_ul" not in st.session_state: st.session_state["site_ul"] = False
        def unlk(): st.session_state["site_ul"] = True
        st.download_button("Unlock Delete (Download Backup)", data=json.dumps({"sites": fetch_data("sites").to_dict("records")}, default=str), file_name="site_bkp.json", on_click=unlk)
        d_site = st.selectbox("Delete Site", fetch_data("sites")["name"].unique()) if not fetch_data("sites").empty else None
        if st.button("Delete Site", disabled=not st.session_state["site_ul"]):
             supabase.table("sites").delete().eq("name", d_site).execute(); st.success("Deleted"); st.rerun()

# TAB 5: CONTRACTORS
elif current_tab == "👷 Contractors":
    st.subheader("Contractor Rates")
    df_c = fetch_data("contractors")
    st.dataframe(df_c.sort_values(by=["name", "effective_date"], ascending=[True, False]), use_container_width=True, hide_index=True)
    st.divider()
    
    act = st.radio("Action", ["Add New", "Update Existing"], horizontal=True)
    with st.form("c_form"):
        cn = st.selectbox("Select", df_c["name"].unique()) if act == "Update Existing" and not df_c.empty else st.text_input("Name")
        c1, c2, c3 = st.columns(3)
        rm = c1.number_input("Mason Rate", value=0); rh = c2.number_input("Helper Rate", value=0); rl = c3.number_input("Ladies Rate", value=0)
        ed = st.date_input("Effective Date", date.today())
        if st.form_submit_button("Save"):
            supabase.table("contractors").insert({"name": cn, "rate_mason": rm, "rate_helper": rh, "rate_ladies": rl, "effective_date": str(ed)}).execute(); st.success("Saved"); st.rerun()

# TAB 6: USERS
elif current_tab == "👥 Users":
    st.subheader("Users")
    st.dataframe(fetch_data("users"), use_container_width=True)
    
    st.markdown("### ➕ Add / Update User")
    with st.form("u_add"):
        c_u1, c_u2 = st.columns(2)
        ph = c_u1.text_input("Phone (Unique ID)", max_chars=10)
        nm = c_u2.text_input("Name")
        
        c_u3, c_u4 = st.columns(2)
        rl = c_u3.selectbox("Role", ["user", "admin"])
        
        # CHANGED: Multi-select for sites
        all_sites = fetch_data("sites")["name"].tolist()
        
        # Pre-fetching existing user data to populate form would be complex in a simple form,
        # so this is a simple 'write' form. 
        # But if updating, we need to handle text better.
        asites = c_u4.multiselect("Assigned Sites", all_sites)

        if st.form_submit_button("Save User"):
            # Join list into comma-separated string for database
            site_str = ", ".join(asites) if asites else "None/All"
            
            if supabase.table("users").select("*").eq("phone", ph).execute().data:
                # Update
                supabase.table("users").update({"name": nm, "role": rl, "assigned_site": site_str}).eq("phone", ph).execute()
            else:
                # Insert
                supabase.table("users").insert({"phone": ph, "name": nm, "role": rl, "assigned_site": site_str, "status": "Active"}).execute()
            st.success("User Saved!"); st.rerun()
    
    st.divider()
    st.markdown("### 🚪 Deactivate User")
    users = fetch_data("users")
    if not users.empty:
        active = users[(users["role"] != "admin")]
        if "status" in active.columns: active = active[active["status"] != "Resigned"]
        
        if not active.empty:
            sel_u = st.selectbox("Select User to Resign", [f"{r['name']} ({r['phone']})" for _, r in active.iterrows()])
            if st.button("Confirm Deactivation"):
                ph_clean = sel_u.split("(")[-1].replace(")", "")
                supabase.table("users").update({"status": "Resigned"}).eq("phone", ph_clean).execute()
                st.success("User deactivated"); st.rerun()

# TAB 7: ARCHIVE & RECOVERY
elif current_tab == "📂 Archive & Recovery":
    st.subheader("Recovery Zone")
    t1, t2, t3 = st.tabs(["Reset Data", "View Archives (Offline)", "Restore Data"])
    
    # SUB-TAB 1: RESET
    with t1:
        st.info("Download backup to unlock reset.")
        if "reset_ul" not in st.session_state: st.session_state["reset_ul"] = False
        def ul_res(): st.session_state["reset_ul"] = True
        bkp = {"entries": fetch_data("entries").to_dict("records"), "users": fetch_data("users").to_dict("records"), "sites": fetch_data("sites").to_dict("records"), "contractors": fetch_data("contractors").to_dict("records")}
        st.download_button("Download Backup", data=json.dumps(bkp, default=str), file_name="full_backup.json", on_click=ul_res)
        
        c_del1, c_del2 = st.columns(2)
        conf_txt = c_del1.text_input("Type 'DELETE ALL'")
        conf_pass = c_del2.text_input("Admin Password", type="password")
        
        if st.button("Clear Entries", disabled=not st.session_state["reset_ul"], type="primary"):
            if conf_txt == "DELETE ALL" and conf_pass == ADMIN_DELETE_CODE:
                supabase.table("entries").delete().neq("id", 0).execute(); st.success("Reset Complete"); st.session_state["reset_ul"] = False
            else: st.error("Wrong Code or Text")

    # SUB-TAB 2: VIEW ARCHIVES
    with t2:
        st.markdown("### 📜 View Old Data (No Restore)")
        f_view = st.file_uploader("Upload JSON to View", type=["json"], key="view_upload")
        if f_view:
            try:
                d = json.load(f_view)
                st.success("File Loaded Successfully")
                
                # Option to Generate Bill from Archive
                view_mode = st.radio("View Mode", ["Raw Data Tables", "Generate Weekly Bill"])
                
                if view_mode == "Raw Data Tables":
                    cat = st.selectbox("Category", ["Entries", "Users", "Sites", "Contractors"])
                    k_map = {"Entries": "entries", "Users": "users", "Sites": "sites", "Contractors": "contractors"}
                    if d.get(k_map[cat]): st.dataframe(pd.DataFrame(d[k_map[cat]]), use_container_width=True)
                    else: st.warning("No data found for this category.")
                
                elif view_mode == "Generate Weekly Bill":
                    st.info("Generating bill from uploaded backup file...")
                    if d.get("entries") and d.get("contractors"):
                        ae = pd.DataFrame(d["entries"])
                        ac = pd.DataFrame(d["contractors"])
                        render_weekly_bill(ae, ac)
                    else:
                        st.error("Backup file missing entries or contractors data.")
            except Exception as e: st.error(f"Error reading file: {e}")

    # SUB-TAB 3: RESTORE
    with t3:
        f = st.file_uploader("Upload Backup JSON to Restore", key="res_up")
        res_pass = st.text_input("Restore Password", type="password")
        if f and st.button("Restore Now", type="primary"):
            if res_pass == ADMIN_DELETE_CODE:
                d = json.load(f)
                st.write("Restoring...")
                try:
                    def clean(r): return [{k:v for k,v in x.items() if k!='id'} for x in r]
                    if d.get("sites"): supabase.table("sites").upsert(clean(d["sites"]), on_conflict="name").execute()
                    if d.get("users"): supabase.table("users").upsert(clean(d["users"]), on_conflict="phone").execute()
                    if d.get("contractors"): supabase.table("contractors").upsert(clean(d["contractors"])).execute()
                    if d.get("entries"): 
                        ent = clean(d["entries"])
                        for i in range(0, len(ent), 50): supabase.table("entries").insert(ent[i:i+50]).execute()
                    st.success("Restored Successfully!")
                except Exception as e: st.error(f"Error: {e}")
            else: st.error("Wrong Password")