import streamlit as st
import pandas as pd
import io
import datetime
from fpdf import FPDF
import os

# ==========================================
# 1. THEME & PAGE CONFIG (Matches your UI)
# ==========================================
st.set_page_config(page_title="Logistics Portal", layout="wide")

# Custom CSS to mimic the spacing and headers in your screenshots
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div.stButton > button:first-child { background-color: #262730; color: white; border-radius: 5px; }
    h1 { font-weight: 800; }
    .stDataFrame { border: 1px solid #262730; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

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
            # Re-calc Total
            q = st.session_state.df_detailed.at[row_idx, "Quantity"]
            p = st.session_state.df_detailed.at[row_idx, "Unit Price"]
            st.session_state.df_detailed.at[row_idx, "Total"] = round(q * p, 2)

# ==========================================
# 3. SIDEBAR NAVIGATION & INPUTS
# ==========================================
st.sidebar.title("Shipment Details")

# This matches the first screenshot's sidebar layout
app_mode = st.sidebar.selectbox("Select Tool", ["Quote Pipeline", "Invoice Extractor"])

if app_mode == "Quote Pipeline":
    st.sidebar.selectbox("Select Destination", ["UK - Radial FAO Monat, 26, 2..."])
    st.sidebar.selectbox("Service", ["40\" REEFER", "20\" Standard", "Air Freight"])
    st.sidebar.text_input("Commodity", "Finished goods / Haircare / Skincare")
    st.sidebar.text_input("Value of Cargo", "USD$")
    st.sidebar.selectbox("Incoterms", ["-", "EXW", "FOB", "DDP"])
else:
    # Sidebar for Invoice Extractor
    st.sidebar.info("Upload SAP file in the main window to begin extraction.")

# ==========================================
# 4. MAIN APP CONTENT
# ==========================================

# --- TOOL 1: QUOTE PIPELINE (Visual Match for Image 4) ---
if app_mode == "Quote Pipeline":
    st.title("📦 Logistics Quote Pipeline")
    st.markdown("### Upload Outbound Packing List (.xlsx)")
    
    pl_file = st.file_uploader("", type=['xlsx'])
    
    if not pl_file:
        st.info("Please upload the Outbound Packing List to begin.")
    else:
        st.success("File Received.")

# --- TOOL 2: INVOICE EXTRACTOR (Visual Match for Images 1, 2, 3) ---
elif app_mode == "Invoice Extractor":
    st.title("🧾 Invoice Line Item Extractor")
    
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
        hts_mapping = get_hts_data()
        
        if 'df_detailed' not in st.session_state:
            raw_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
            rows = []
            for _, row in raw_df.iterrows():
                sku = clean_sku(row.get('Material', ''))
                if not sku: continue
                sku_info = hts_mapping.get(sku, {"hts": "", "desc": ""})
                qty = clean_numeric(row.get('Order Quantity', 0))
                u_price = round(clean_numeric(row.get('Net Price', 0)) / 1000, 3)
                
                rows.append({
                    "SKU": sku,
                    "HTS Code": sku_info["hts"],
                    "Origin": "USA" if sku.startswith('600') else "CHINA" if sku.startswith('300') else "",
                    "Description": str(row.get('Short Text', '')).strip(),
                    "Quantity": int(qty),
                    "Unit Price": u_price,
                    "Total": round(qty * u_price, 2),
                    "Customs_Desc_Internal": sku_info["desc"]
                })
            st.session_state.df_detailed = pd.DataFrame(rows)

        # 1. Detailed Table (Matches Image 3)
        st.subheader("Detailed Line Items (Editable)")
        edited_detailed = st.data_editor(
            st.session_state.df_detailed.drop(columns=['Customs_Desc_Internal']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unit Price": st.column_config.NumberColumn(format="$%.3f"),
                "Total": st.column_config.NumberColumn(format="$%.2f", disabled=True),
                "Description": st.column_config.TextColumn("Description", disabled=True)
            },
            key="detailed_editor",
            on_change=update_detailed_state
        )

        # 2. HTS Summary (Matches Image 1)
        st.markdown("### 📊 HTS Summary (Customs Totals)")
        
        summary_df = edited_detailed.merge(
            st.session_state.df_detailed[['SKU', 'Customs_Desc_Internal']], on='SKU', how='left'
        )
        
        summary_grouped = summary_df.groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
            'Quantity': 'sum',
            'Total': 'sum'
        }).reset_index()
        summary_grouped.columns = ['HTS Code', 'Customs Description', 'Total Quantity', 'Total Value']

        st.data_editor(
            summary_grouped,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total Value": st.column_config.NumberColumn(format="$%.2f")
            },
            key="summary_editor"
        )

        # 3. Download Button (Matches Image 1)
        st.button("🕹️ Download Excel with Summary")

    if st.sidebar.button("Reset System"):
        for key in st.session_state.keys(): del st.session_state[key]
        st.rerun()
