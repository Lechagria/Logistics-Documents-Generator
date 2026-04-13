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
        # Standardize column headers
        df.columns = [str(c).strip() for c in df.columns]
        
        mapping = {}
        for _, row in df.iterrows():
            sku = clean_sku(row.get('SKU', ''))
            if sku:
                # Updated to look for "Description" as requested
                mapping[sku] = {
                    "hts": clean_sku(row.get('HTS', '')),
                    "customs_desc": str(row.get('Description', '')).strip()
                }
        return mapping
    except Exception as e:
        st.error(f"⚠️ **FILE ERROR:** Could not read 'Cleaned_HTS_Codes.csv'. Check if header is 'Description'.")
        return {}

# ==========================================
# 2. PDF GENERATOR
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
# 3. MAIN APP
# ==========================================
st.set_page_config(page_title="Logistics Document Portal", layout="wide")
st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Invoice Line Item Extractor"])

# Pre-load mapping
hts_mapping = get_hts_data()

if page == "Quote Request Generator":
    st.title("📦 Quote Request Pipeline")
    # (Existing Quote Generator logic)

elif page == "Invoice Line Item Extractor":
    st.title("🧾 Invoice Line Item Extractor")
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
            u_price = raw_net / 1000
            total_val = qty * u_price
            
            sku_info = hts_mapping.get(sku, {"hts": "", "customs_desc": ""})
            
            # Origin logic (starts with 600 -> USA, 300 -> CHINA)
            if sku.startswith('600'): origin = "USA"
            elif sku.startswith('300'): origin = "CHINA"
            else: origin = ""
            
            invoice_rows.append({
                "SKU": sku,
                "HTS Code": sku_info["hts"],
                "Origin": origin,
                "Description": sap_desc,
                "Quantity": int(qty),
                "Unit Price": f"${u_price:,.3f}",  
                "Total": f"${total_val:,.2f}",
                "Customs_Desc_Internal": sku_info["customs_desc"]
            })
        
        if invoice_rows:
            df_final = pd.DataFrame(invoice_rows)
            st.success(f"✅ Successfully extracted {len(df_final)} line items!")
            
            # Detailed Table
            st.subheader("Detailed Line Items")
            st.dataframe(df_final.drop(columns=['Customs_Desc_Internal']), use_container_width=True, hide_index=True)
            
            # HTS Summary Table
            st.divider()
            st.subheader("📊 HTS Summary (Customs Totals)")
            
            df_summary = df_final.copy()
            df_summary['NumericTotal'] = df_summary['Total'].replace('[\$,]', '', regex=True).astype(float)
            
            summary_grouped = df_summary.groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
                'Quantity': 'sum',
                'NumericTotal': 'sum'
            }).reset_index()
            
            # Renaming for final output
            summary_grouped.columns = ['HTS Code', 'Customs Description', 'Total Quantity', 'Total Value']
            
            display_summary = summary_grouped.copy()
            display_summary['Total Value'] = display_summary['Total Value'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(display_summary, use_container_width=True, hide_index=True)
            
            # Download
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_final.drop(columns=['Customs_Desc_Internal']).to_excel(writer, index=False, sheet_name="Line_Items")
                summary_grouped.to_excel(writer, index=False, sheet_name="HTS_Summary")
            
            st.download_button("📥 Download Excel with Summary", excel_buffer.getvalue(), "Invoice_Summary.xlsx")
