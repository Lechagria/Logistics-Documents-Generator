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
                    "customs_desc": str(row.get('Description', '')).strip()
                }
        return mapping
    except Exception as e:
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
# 3. MAIN APP
# ==========================================
st.set_page_config(page_title="Logistics Document Portal", layout="wide")
st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Invoice Line Item Extractor"])

hts_mapping = get_hts_data()

if page == "Quote Request Generator":
    st.title("📦 Quote Request Pipeline")
    # (Existing Quote Logic)

elif page == "Invoice Line Item Extractor":
    st.title("🧾 Invoice Line Item Extractor")
    st.markdown("Manually edit **HTS**, **Origin**, or **Unit Price**. The **Total** column will update automatically.")
    
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
        # Load data once and store in session state
        if 'df_invoice' not in st.session_state or st.sidebar.button("Reload File"):
            raw_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
            raw_df.columns = [str(col).strip() for col in raw_df.columns]
            
            invoice_rows = []
            for _, row in raw_df.iterrows():
                sku = clean_sku(row.get('Material', ''))
                if not sku: continue
                    
                sap_desc = str(row.get('Short Text', '')).strip()
                qty = clean_numeric(row.get('Order Quantity', 0))
                raw_net = clean_numeric(row.get('Net Price', 0))
                u_price = round(raw_net / 1000, 3)
                
                sku_info = hts_mapping.get(sku, {"hts": "", "customs_desc": ""})
                
                # Default Origin Logic
                origin = "USA" if sku.startswith('600') else "CHINA" if sku.startswith('300') else ""
                
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
            st.session_state.df_invoice = pd.DataFrame(invoice_rows)

        # 1. THE EDITABLE TABLE
        st.subheader("Detailed Line Items (Editable)")
        
        # Display editor
        edited_df = st.data_editor(
            st.session_state.df_invoice.drop(columns=['Customs_Desc_Internal']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unit Price": st.column_config.NumberColumn(format="$%.3f"),
                "Total": st.column_config.NumberColumn(format="$%.2f", disabled=True), # We calculate this automatically
                "Quantity": st.column_config.NumberColumn(disabled=True),
                "SKU": st.column_config.TextColumn(disabled=True)
            },
            key="invoice_editor"
        )

        # 2. AUTOMATIC CALCULATION FOR DETAILED LINE
        # This line updates the "Total" in the visible table immediately
        edited_df["Total"] = (edited_df["Quantity"] * edited_df["Unit Price"]).round(2)

        # 3. HTS SUMMARY
        st.divider()
        st.subheader("📊 HTS Summary (Customs Totals)")
        
        # Merge internal descriptions back for summary grouping
        summary_base = edited_df.merge(
            st.session_state.df_invoice[['SKU', 'Customs_Desc_Internal']], 
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
        
        # 4. DOWNLOAD
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            edited_df.to_excel(writer, index=False, sheet_name="Line_Items")
            summary_grouped.to_excel(writer, index=False, sheet_name="HTS_Summary")
        
        st.download_button("📥 Download Final Document", excel_buffer.getvalue(), "Custom_Invoice_Summary.xlsx")

    if st.button("Clear Data"):
        if 'df_invoice' in st.session_state:
            del st.session_state.df_invoice
            st.rerun()
