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
# 2. PDF GENERATOR (FOR QUOTE REQUEST)
# ==========================================
class QuotePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 15, 'QUOTE REQUEST - FREIGHT', border=0, ln=1, align='C')
        self.ln(5)

    def create_table(self, data_dict):
        self.set_fill_color(240, 240, 240)
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
st.set_page_config(page_title="Logistics Portal", layout="wide")
st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Invoice Line Item Extractor"])

hts_mapping = get_hts_data()

# --- TOOL 1: QUOTE REQUEST GENERATOR ---
if page == "Quote Request Generator":
    st.title("📦 Quote Request Generator")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1. General Information")
        q_origin = st.text_input("Origin (City, Country)", "Foshan, China")
        q_dest = st.text_input("Destination (City, Zip Code)", "Naranja, FL 33032")
        q_mode = st.selectbox("Shipping Mode", ["Sea Freight (LCL)", "Sea Freight (FCL)", "Air Freight", "Trucking"])
        q_incoterm = st.selectbox("Incoterm", ["EXW", "FOB", "CIF", "DDP", "DAP"])
        q_ready = st.date_input("Ready Date", datetime.date.today())
        
    with col2:
        st.subheader("2. Loading Details")
        q_load_type = st.selectbox("Load Type", ["Palletized", "Loose Cartons", "Floor Loaded"])
        q_units = st.text_input("Total Quantity / Units", "10 Pallets")
        q_dims = st.text_input("Dimensions (L x W x H)", "120x100x200 cm per pallet")
        q_weight = st.text_input("Total Weight (KG)", "1500 KG")
        q_notes = st.text_area("Special Instructions", "Stackable, fragile items.")

    st.divider()
    
    shipment_data = {
        "Origin": q_origin,
        "Destination": q_dest,
        "Ready Date": q_ready.strftime("%Y-%m-%d"),
        "Incoterms": q_incoterm,
        "Service Mode": q_mode,
        "Load Type": q_load_type,
        "Qty / Units": q_units,
        "Dimensions": q_dims,
        "Total Weight": q_weight,
        "Notes": q_notes
    }

    if st.button("🚀 Generate Quote PDF"):
        pdf = QuotePDF()
        pdf.add_page()
        pdf.create_table(shipment_data)
        
        pdf_output = pdf.output(dest='S').encode('latin-1')
        st.download_button(
            label="📥 Download Quote Request PDF",
            data=pdf_output,
            file_name=f"Quote_Request_{q_origin}_to_{q_dest}.pdf",
            mime="application/pdf"
        )

# --- TOOL 2: INVOICE LINE ITEM EXTRACTOR ---
elif page == "Invoice Line Item Extractor":
    st.title("🧾 Invoice Line Item Extractor")
    
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
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
                    "Customs_Desc_Internal": sku_info["desc"] 
                })
            st.session_state.df_detailed = pd.DataFrame(rows)

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

        st.divider()
        st.subheader("📊 HTS Summary")
        st.markdown("Edit the **Description** column below for customs purposes.")

        summary_df = edited_detailed.merge(
            st.session_state.df_detailed[['SKU', 'Customs_Desc_Internal']], on='SKU', how='left'
        )
        
        summary_grouped = summary_df.groupby(['HTS Code', 'Customs_Desc_Internal']).agg({
            'Quantity': 'sum',
            'Total': 'sum'
        }).reset_index()
        
        summary_grouped.columns = ['HTS Code', 'Description', 'Total Quantity', 'Total Value']

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

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            edited_detailed.to_excel(writer, index=False, sheet_name="Detailed_Items")
            final_summary.to_excel(writer, index=False, sheet_name="HTS_Summary")
        
        st.download_button("📥 Download Final Excel", excel_buffer.getvalue(), "Customs_Invoice_Summary.xlsx")

    if st.sidebar.button("🗑️ Clear Data"):
        if 'df_detailed' in st.session_state:
            del st.session_state.df_detailed
            st.rerun()
