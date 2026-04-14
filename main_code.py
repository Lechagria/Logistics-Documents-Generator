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
        height: 80px;
        font-size: 18px;
        font-weight: bold;
    }
    .stTable { border: 1px solid #262730; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

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
            
            # Recalculate Row Totals
            qty = st.session_state.df_detailed.at[row_idx, "Quantity"]
            price = st.session_state.df_detailed.at[row_idx, "Unit Price"]
            u_weight = st.session_state.df_detailed.at[row_idx, "Unit_Weight_KG"]
            
            st.session_state.df_detailed.at[row_idx, "Total"] = round(qty * price, 2)
            st.session_state.df_detailed.at[row_idx, "Total Weight (KG)"] = round(qty * u_weight, 2)

# ==========================================
# 3. DASHBOARD
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

    # --- TOOL 1: QUOTE PIPELINE ---
    if st.session_state.active_tool == "Quote Pipeline":
        st.title("📦 Logistics Quote Pipeline")
        # [Existing Quote Pipeline Code remains same...]
        st.info("Quote tool logic active.")

    # --- TOOL 2: INVOICE EXTRACTOR (REPAIRED WEIGHT LOGIC) ---
    elif st.session_state.active_tool == "Invoice Extractor":
        st.title("🧾 Invoice Line Item Extractor")
        
        c1, c2 = st.columns(2)
        with c1: sap_file = st.file_uploader("1. Upload SAP Export", type=['csv', 'xlsx'])
        with c2: pl_file = st.file_uploader("2. Upload Packing List (for Weights)", type=['csv', 'xlsx'])

        if sap_file and pl_file:
            hts_mapping = get_hts_data()
            
            # 1. Parse Packing List for SKU -> Unit Weight (KG)
            # We skip rows to find the actual header in the PL
            pl_df = pd.read_excel(pl_file, header=2) if pl_file.name.endswith('.xlsx') else pd.read_csv(pl_file, header=2)
            pl_df.columns = [str(c).strip() for c in pl_df.columns]
            
            weight_map = {}
            # Logic: Use "Tot. Weight / Bxs" (Col N) divided by "Box" (Col F) or "Total Units"
            # To be safe, we calculate weight per single item
            for _, row in pl_df.iterrows():
                sku = clean_sku(row.get('SKU'))
                if not sku: continue
                
                total_weight_lbs = clean_numeric(row.get('Tot. Weight / Bxs'))
                total_units = clean_numeric(row.get('Total Units'))
                
                if total_units > 0:
                    unit_weight_lbs = total_weight_lbs / total_units
                    weight_map[sku] = unit_weight_lbs * 0.453592 # Convert to KG

            # 2. Process SAP and Join Weights
            if 'df_detailed' not in st.session_state:
                raw_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
                raw_df.columns = [str(col).strip() for col in raw_df.columns]
                
                rows = []
                for _, row in raw_df.iterrows():
                    sku = clean_sku(row.get('Material', ''))
                    if not sku: continue
                    
                    sku_info = hts_mapping.get(sku, {"hts": "NOT FOUND", "desc": ""})
                    qty = clean_numeric(row.get('Order Quantity', 0))
                    u_price = round(clean_numeric(row.get('Net Price', 0)) / 1000, 3)
                    
                    u_weight_kg = weight_map.get(sku, 0.0)
                    
                    rows.append({
                        "SKU": sku,
                        "HTS Code": sku_info["hts"],
                        "Origin": "USA" if sku.startswith('600') else "CHINA" if sku.startswith('300') else "",
                        "Description": str(row.get('Short Text', '')).strip(),
                        "Quantity": int(qty),
                        "Unit Price": u_price,
                        "Total": round(qty * u_price, 2),
                        "Unit_Weight_KG": u_weight_kg, # Helper
                        "Total Weight (KG)": round(qty * u_weight_kg, 2),
                        "Customs_Desc_Internal": sku_info["desc"]
                    })
                st.session_state.df_detailed = pd.DataFrame(rows)

            # 3. Display Detailed Table
            st.subheader("Detailed Line Items (Editable)")
            display_df = st.session_state.df_detailed.drop(columns=['Customs_Desc_Internal', 'Unit_Weight_KG'])
            
            edited_detailed = st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Unit Price": st.column_config.NumberColumn(format="$%.3f"),
                    "Total": st.column_config.NumberColumn(format="$%.2f", disabled=True),
                    "Total Weight (KG)": st.column_config.NumberColumn(format="%.2f kg", disabled=True)
                },
                key="detailed_editor",
                on_change=update_detailed_state
            )

            # 4. Aggregate HTS Summary
            st.markdown("### 📊 HTS Summary (Customs Totals)")
            
            # Merge with internal descriptions for grouping
            summary_base = edited_detailed.merge(
                st.session_state.df_detailed[['SKU', 'Customs_Desc_Internal']], on='SKU', how='left'
            )
            
            summary_grouped = summary_base.groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
                'Quantity': 'sum',
                'Total': 'sum',
                'Total Weight (KG)': 'sum'
            }).reset_index()
            
            summary_grouped.columns = ['HTS Code', 'Customs Description', 'Total Qty', 'Total Value', 'Total Weight (KG)']

            st.data_editor(
                summary_grouped,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total Value": st.column_config.NumberColumn(format="$%.2f"),
                    "Total Weight (KG)": st.column_config.NumberColumn(format="%.2f kg")
                },
                key="summary_editor"
            )

            # 5. Export
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                edited_detailed.to_excel(writer, index=False, sheet_name="Details")
                summary_grouped.to_excel(writer, index=False, sheet_name="HTS_Summary")
            
            st.download_button("📥 Download Final SLI Excel", data=excel_buf.getvalue(), file_name="Customs_Invoice_Weights.xlsx")
