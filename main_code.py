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
    """Loads SKU mapping from Cleaned_HTS_Codes.csv with robust header handling."""
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
                    "customs_desc": str(row.get('Description', '')).strip()
                }
        return mapping
    except Exception as e:
        st.error(f"⚠️ **FILE ERROR:** Could not read 'Cleaned_HTS_Codes.csv'. Check if header is 'Description'.")
        return {}

# ==========================================
# 2. PDF GENERATOR (For Tool 1)
# ==========================================
class QuotePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 15, 'QUOTE REQUEST', border=0, ln=1, align='C')
        self.ln(10)

    def create_table(self, data_dict, dims):
        self.set_fill_color(230, 230, 230)
        self.set_font('Arial', 'B', 10)
        self.cell(60, 10, ' CATEGORY', border=1, fill=True)
        self.cell(130, 10, ' SHIPMENT DETAILS', border=1, ln=1, fill=True)
        self.set_font('Arial', '', 10)
        for key, value in data_dict.items():
            self.set_font('Arial', 'B', 10)
            self.cell(60, 9, f" {key}", border=1)
            self.set_font('Arial', '', 10)
            self.cell(130, 9, f" {value}", border=1, ln=1)

# ==========================================
# 3. STREAMLIT APP & NAVIGATION
# ==========================================
st.set_page_config(page_title="Logistics Document Portal", layout="wide")
st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Invoice Line Item Extractor"])

hts_mapping = get_hts_data()

# --- TOOL 1: QUOTE REQUEST GENERATOR ---
if page == "Quote Request Generator":
    st.title("📦 Quote Request Pipeline")
    # (Quote logic remains the same as your previous working version)
    # [Omitted here for brevity, keep your original Tool 1 code block here]

# --- TOOL 2: INVOICE LINE ITEM EXTRACTOR ---
elif page == "Invoice Line Item Extractor":
    st.title("🧾 Invoice Line Item Extractor")
    st.markdown("You can **manually edit** HTS, Origin, and Unit Price in the table. Totals will update automatically.")
    
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
        raw_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
        raw_df.columns = [str(col).strip() for col in raw_df.columns]
        
        invoice_rows = []
        for _, row in raw_df.iterrows():
            sku = clean_sku(row.get('Material', ''))
            if not sku: continue
                
            sap_desc = str(row.get('Short Text', '')).strip()
            qty = clean_numeric(row.get('Order Quantity', 0))
            raw_net = clean_numeric(row.get('Net Price', 0))
            u_price = round(raw_net / 1000, 3) # Starting unit price
            
            sku_info = hts_mapping.get(sku, {"hts": "", "customs_desc": ""})
            
            # Default Origin Logic
            if sku.startswith('600'): origin = "USA"
            elif sku.startswith('300'): origin = "CHINA"
            else: origin = ""
            
            invoice_rows.append({
                "SKU": sku,
                "HTS Code": sku_info["hts"],
                "Origin": origin,
                "Description": sap_desc,
                "Quantity": int(qty),
                "Unit Price": u_price,
                "Total": round(qty * u_price, 2),
                "Customs_Desc_Internal": sku_info["customs_desc"]
            })
        
        if invoice_rows:
            # 1. Prepare editable table
            df_to_edit = pd.DataFrame(invoice_rows)
            
            st.subheader("Detailed Line Items (Editable)")
            # Using data_editor to allow manual overrides
            edited_df = st.data_editor(
                df_to_edit.drop(columns=['Customs_Desc_Internal']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "HTS Code": st.column_config.TextColumn("HTS Code"),
                    "Origin": st.column_config.TextColumn("Origin"),
                    "Unit Price": st.column_config.NumberColumn("Unit Price", format="$%.3f"),
                    "Total": st.column_config.NumberColumn("Total", format="$%.2f", disabled=True),
                    "Quantity": st.column_config.NumberColumn("Quantity", disabled=True),
                    "SKU": st.column_config.TextColumn("SKU", disabled=True)
                },
                key="invoice_editor"
            )

            # 2. Recalculate Totals based on user manual edits
            edited_df["Total"] = edited_df["Quantity"] * edited_df["Unit Price"]

            # 3. HTS SUMMARY (Calculated from edited data)
            st.divider()
            st.subheader("📊 HTS Summary (Customs Totals)")
            
            # Re-merge internal descriptions for the summary calculation
            summary_base = edited_df.merge(
                df_to_edit[['SKU', 'Customs_Desc_Internal']], 
                on='SKU', 
                how='left'
            )
            
            summary_grouped = summary_base.groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
                'Quantity': 'sum',
                'Total': 'sum'
            }).reset_index()
            
            summary_grouped.columns = ['HTS Code', 'Customs Description', 'Total Quantity', 'Total Value']
            
            st.dataframe(
                summary_grouped.style.format({"Total Value": "${:,.2f}"}),
                use_container_width=True, 
                hide_index=True
            )
            
            # 4. Download Export including Summary
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                edited_df.to_excel(writer, index=False, sheet_name="Line_Items")
                summary_grouped.to_excel(writer, index=False, sheet_name="HTS_Summary")
            
            st.download_button(
                label="📥 Download Edited Invoice & Summary",
                data=excel_buffer.getvalue(),
                file_name="Edited_Invoice_Summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("No valid SKUs found in the uploaded file.")
