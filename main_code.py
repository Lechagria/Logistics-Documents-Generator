import streamlit as st
import pandas as pd
from collections import Counter
import io
import datetime
from fpdf import FPDF
import os

# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clean_numeric(value):
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    clean_val = str(value).replace(',', '').replace('$', '').strip()
    try:
        return float(clean_val)
    except ValueError:
        return 0.0

def clean_sku(val):
    if pd.isna(val): 
        return ""
    s = str(val).strip()
    if s.endswith('.0'): 
        s = s[:-2]
    if s.lower() == 'nan': 
        return ""
    return s

def get_hts_data():
    """Loads SKU mapping from Cleaned_HTS_Codes.csv."""
    try:
        current_folder = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_folder, "Cleaned_HTS_Codes.csv")
        df = pd.read_csv(file_path, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        mapping = {}
        for _, row in df.iterrows():
            sku = clean_sku(row.get('SKU', ''))
            if sku:
                mapping[sku] = {
                    "hts": clean_sku(row.get('HTS', '')),
                    "desc": str(row.get('Description', '')).strip()
                }
        return mapping
    except Exception:
        return {}

def update_detailed_state():
    """Recalculates totals in the detailed table if Unit Price is edited."""
    if "detailed_editor" in st.session_state:
        edits = st.session_state["detailed_editor"]["edited_rows"]
        for row_idx, changes in edits.items():
            for col_name, new_val in changes.items():
                st.session_state.df_detailed.at[row_idx, col_name] = new_val
            # Update Total automatically
            q = st.session_state.df_detailed.at[row_idx, "Quantity"]
            p = st.session_state.df_detailed.at[row_idx, "Unit Price"]
            st.session_state.df_detailed.at[row_idx, "Total"] = round(q * p, 2)

# ==========================================
# 2. MAIN APP
# ==========================================
st.set_page_config(page_title="Logistics Portal", layout="wide")
st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Invoice Line Item Extractor"])

hts_mapping = get_hts_data()

if page == "Invoice Line Item Extractor":
    st.title("🧾 Invoice Line Item Extractor")
    
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
        # Load data into session state
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
                
                rows.append({
                    "SKU": sku,
                    "HTS Code": sku_info["hts"],
                    "Origin": "USA" if sku.startswith('600') else "CHINA" if sku.startswith('300') else "",
                    "Description": str(row.get('Short Text', '')).strip(),
                    "Quantity": int(qty),
                    "Unit Price": u_price,
                    "Total": round(qty * u_price, 2),
                    "Customs_Desc_Internal": sku_info["desc"] # Hidden source for summary
                })
            st.session_state.df_detailed = pd.DataFrame(rows)

        # --- 1. DETAILED TABLE (Manual Edits for HTS, Origin, Price) ---
        st.subheader("Detailed Line Items")
        edited_detailed = st.data_editor(
            st.session_state.df_detailed.drop(columns=['Customs_Desc_Internal']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unit Price": st.column_config.NumberColumn(format="$%.3f"),
                "Total": st.column_config.NumberColumn(format="$%.2f", disabled=True),
                "Quantity": st.column_config.NumberColumn(disabled=True),
                "Description": st.column_config.TextColumn("SAP Description", disabled=True)
            },
            key="detailed_editor",
            on_change=update_detailed_state
        )

        # --- 2. HTS SUMMARY (Editable Descriptions) ---
        st.divider()
        st.subheader("📊 HTS Summary")
        st.markdown("Edit the **Description** column below for customs purposes.")

        # Prepare summary data from current state
        # We merge back the hidden internal description to group correctly
        summary_df = edited_detailed.merge(
            st.session_state.df_detailed[['SKU', 'Customs_Desc_Internal']], on='SKU', how='left'
        )
        
        summary_grouped = summary_df.groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
            'Quantity': 'sum',
            'Total': 'sum'
        }).reset_index()
        
        summary_grouped.columns = ['HTS Code', 'Description', 'Total Quantity', 'Total Value']

        # Make the summary description editable
        final_summary = st.data_editor(
            summary_grouped,
            use_container_width=True,
            hide_index=True,
            column_config={
                "HTS Code": st.column_config.TextColumn(disabled=True),
                "Total Quantity": st.column_config.NumberColumn(disabled=True),
                "Total Value": st.column_config.NumberColumn(format="$%.2f", disabled=True),
                "Description": st.column_config.TextColumn("Customs Description (Edit here)")
            },
            key="summary_editor"
        )

        # --- 3. DOWNLOAD ---
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            edited_detailed.to_excel(writer, index=False, sheet_name="Detailed_Items")
            final_summary.to_excel(writer, index=False, sheet_name="HTS_Summary")
        
        st.download_button("📥 Download Excel", excel_buffer.getvalue(), "Customs_Invoice.xlsx")

    if st.sidebar.button("🗑️ Clear Data"):
        if 'df_detailed' in st.session_state:
            del st.session_state.df_detailed
            st.rerun()

elif page == "Quote Request Generator":
    st.title("📦 Quote Request Pipeline")
    st.info("Tool is ready for upload.")
