import streamlit as st
import pandas as pd
from collections import Counter
import io
import datetime
import os
import re

# ==========================================
# 1. PAGE CONFIG & THEME
# ==========================================
st.set_page_config(page_title="Logistics Portal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div.stButton > button:first-child { 
        background-color: #262730; 
        color: white; 
        border-radius: 5px; 
        width: 100%;
        height: 100px;
        font-size: 20px;
        font-weight: bold;
    }
    .stTable { border: 1px solid #262730; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session State for Navigation
if 'active_tool' not in st.session_state:
    st.session_state.active_tool = None

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def clean_numeric(value):
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    clean_val = str(value).replace(',', '').replace('$', '').strip()
    try: return float(clean_val)
    except ValueError: return 0.0

def clean_sku(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.endswith('.0'): s = s[:-2]
    return s

def get_hts_data():
    try:
        current_folder = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_folder, "Cleaned_HTS_Codes.csv")
        df = pd.read_csv(file_path, dtype=str)
        mapping = {}
        for _, row in df.iterrows():
            sku = clean_sku(row.get('SKU', ''))
            if sku:
                mapping[sku] = {
                    "hts": clean_sku(row.get('HTS', '')),
                    "desc": str(row.get('Description', '')).strip()
                }
        return mapping
    except: return {}

def update_detailed_state():
    if "detailed_editor" in st.session_state:
        edits = st.session_state["detailed_editor"]["edited_rows"]
        for row_idx, changes in edits.items():
            for col_name, new_val in changes.items():
                st.session_state.df_detailed.at[row_idx, col_name] = new_val
            
            q = st.session_state.df_detailed.at[row_idx, "Quantity"]
            p = st.session_state.df_detailed.at[row_idx, "Unit Price"]
            uw = st.session_state.df_detailed.at[row_idx, "Unit_Weight_KG"]
            
            st.session_state.df_detailed.at[row_idx, "Total"] = round(q * p, 2)
            st.session_state.df_detailed.at[row_idx, "Total Weight (KG)"] = round(q * uw, 2)

# ==========================================
# 3. DASHBOARD / TOOL SELECTION
# ==========================================
if st.session_state.active_tool is None:
    st.title("📂 Logistics Operations Portal")
    st.subheader("Select a tool to begin:")
    st.write("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📦 Logistics Quote Pipeline"):
            st.session_state.active_tool = "Quote Pipeline"
            st.rerun()
    with col2:
        if st.button("🧾 Invoice Line Item Extractor"):
            st.session_state.active_tool = "Invoice Extractor"
            st.rerun()

# ==========================================
# 4. MAIN APP CONTENT
# ==========================================
else:
    if st.sidebar.button("⬅️ Back to Portal"):
        if 'df_detailed' in st.session_state: del st.session_state.df_detailed
        st.session_state.active_tool = None
        st.rerun()

    # --- TOOL 1: QUOTE PIPELINE (UNMODIFIED) ---
    if st.session_state.active_tool == "Quote Pipeline":
        st.sidebar.title("Shipment Details")
        destinations = ["UK - Radial FAO Monat...", "POLAND - Radial Poland...", "AUSTRALIA - FDM...", "MONAT Canada...", "FENIX FWD INC...", "OTHER"]
        selected_dest = st.sidebar.selectbox("Select Destination", destinations)
        service = st.sidebar.selectbox("Service", ["40\" REEFER", "40\" DRY", "20\" DRY", "HAZMAT LCL", "LCL Ocean", "LTL Road", "Air Freight", "Courier"])
        commodity = st.sidebar.text_input("Commodity", value="Finished goods / Haircare / Skincare")
        cargo_value = st.sidebar.text_input("Value of Cargo", value="USD$ ")
        incoterms = st.sidebar.selectbox("Incoterms", ["-", "EXW", "FOB", "DDP", "DAP", "CIF"])

        st.title("📦 Logistics Quote Pipeline")
        packing_file = st.file_uploader("Upload Outbound Packing List (.xlsx)", type=['xlsx'])
        if packing_file:
            st.success("File uploaded. Generate template to proceed.")

    # --- TOOL 2: INVOICE EXTRACTOR (FIXED FOR MULTIPLE POs) ---
    elif st.session_state.active_tool == "Invoice Extractor":
        st.title("🧾 Invoice Line Item Extractor")
        
        c1, c2 = st.columns(2)
        with c1: sap_file = st.file_uploader("1. Upload SAP Export", type=['csv', 'xlsx'])
        with c2: pl_file = st.file_uploader("2. Upload Packing List", type=['csv', 'xlsx'])

        if sap_file and pl_file:
            hts_mapping = get_hts_data()
            
            # --- Robust Packing List Multi-PO Processing ---
            raw_pl = pd.read_excel(pl_file, header=None) if pl_file.name.endswith('.xlsx') else pd.read_csv(pl_file, header=None)
            
            sku_weight_map = {}
            last_po = ""
            current_cols = None

            for i, row in raw_pl.iterrows():
                row_vals = [str(x).strip() for x in row.values]
                
                # Identify Header Row (works for both tables)
                if "SKU" in row_vals or "Material" in row_vals:
                    current_cols = row_vals
                    continue
                
                if current_cols:
                    row_dict = dict(zip(current_cols, row.values))
                    sku = clean_sku(row_dict.get('SKU') or row_dict.get('Material'))
                    po = str(row_dict.get('P.O.') or row_dict.get('Purchasing Document') or "").strip()
                    
                    # Track PO forward-filling
                    if po and po != "nan": last_po = po
                    
                    if sku and sku != "nan":
                        # Weight Logic: Get LB and convert to KG
                        weight_lb = clean_numeric(row_dict.get('Weight / Box') or row_dict.get('Tot. Weight / Bxs'))
                        units = clean_numeric(row_dict.get('Total Units'))
                        
                        if units > 0:
                            unit_kg = (weight_lb / units) * 0.453592
                            sku_weight_map[sku] = unit_kg

            # --- SAP Processing ---
            if 'df_detailed' not in st.session_state:
                raw_sap = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
                raw_sap.columns = [str(col).strip() for col in raw_sap.columns]
                
                rows = []
                for _, row in raw_sap.iterrows():
                    sku = clean_sku(row.get('Material', ''))
                    if not sku: continue
                    
                    sku_info = hts_mapping.get(sku, {"hts": "TBD", "desc": "Unknown"})
                    qty = clean_numeric(row.get('Order Quantity', 0))
                    net_price = clean_numeric(row.get('Net Price', 0))
                    
                    # Logic: Determine Unit Price
                    u_price = round(net_price / qty, 3) if qty > 0 else 0.0
                    u_weight = sku_weight_map.get(sku, 0.0)
                    
                    rows.append({
                        "PO#": str(row.get('Purchasing Document', '')),
                        "SKU": sku, 
                        "HTS Code": sku_info["hts"],
                        "Origin": "USA" if sku.startswith('600') else "CHINA" if sku.startswith('300') else "USA",
                        "Description": str(row.get('Short Text', '')).strip(),
                        "Quantity": int(qty), 
                        "Unit Price": u_price, 
                        "Total": round(qty * u_price, 2),
                        "Unit_Weight_KG": u_weight, 
                        "Total Weight (KG)": round(qty * u_weight, 2),
                        "Customs_Desc_Internal": sku_info["desc"]
                    })
                st.session_state.df_detailed = pd.DataFrame(rows)

            # --- Display ---
            st.subheader("Detailed Line Items (Editable)")
            edited_detailed = st.data_editor(
                st.session_state.df_detailed.drop(columns=['Customs_Desc_Internal', 'Unit_Weight_KG']),
                use_container_width=True, hide_index=True,
                column_config={
                    "Unit Price": st.column_config.NumberColumn(format="$%.3f"),
                    "Total": st.column_config.NumberColumn(format="$%.2f"),
                    "Total Weight (KG)": st.column_config.NumberColumn(format="%.2f kg")
                },
                key="detailed_editor", on_change=update_detailed_state
            )

            st.markdown("### 📊 HTS Summary")
            summary_grouped = edited_detailed.merge(
                st.session_state.df_detailed[['SKU', 'Customs_Desc_Internal']], on='SKU', how='left'
            ).groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
                'Quantity': 'sum', 'Total': 'sum', 'Total Weight (KG)': 'sum'
            }).reset_index()
            
            summary_grouped.columns = ['HTS Code', 'Customs Description', 'Total Qty', 'Total Value', 'Total Weight (KG)']
            st.table(summary_grouped)

            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                edited_detailed.to_excel(writer, index=False, sheet_name="Details")
                summary_grouped.to_excel(writer, index=False, sheet_name="HTS_Summary")
            st.download_button("📥 Download SLI Excel", excel_buf.getvalue(), "Customs_Invoice.xlsx")
