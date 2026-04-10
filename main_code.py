import streamlit as st
import pandas as pd
from collections import Counter
import io
import re
from fpdf import FPDF
import datetime

# --- PDF GENERATOR: EXCEL-TO-GRID STYLE ---
class LogisticsPDF(FPDF):
    def create_packing_list(self, title, df_rows):
        self.add_page()
        self.set_font('Arial', 'B', 10)
        
        # 1. Shaded Header Row 1 (Title)
        self.set_fill_color(220, 220, 220)
        self.cell(0, 10, f"  {title}", border=1, ln=1, fill=True)
        
        # 2. Shaded Header Row 2 (Columns) 
        self.set_font('Arial', 'B', 8)
        cols = ["PALLET", "P.O.", "SKU/Description", "BOX", "UNITS", "DIM/BATCH", "WGT/BX", "TOT WGT"]
        widths = [15, 25, 55, 12, 18, 30, 15, 20]
        
        for i, col in enumerate(cols):
            self.cell(widths[i], 10, col, border=1, fill=True, align='C')
        self.ln()

        # 3. Transparent Data Grid [cite: 1, 4]
        self.set_font('Arial', '', 7)
        for row in df_rows:
            # Multi-line cell handling for descriptions
            start_y = self.get_y()
            for i, item in enumerate(row):
                self.multi_cell(widths[i], 8, str(item), border=1, align='L' if i==2 else 'C')
                self.set_xy(self.get_x() + sum(widths[:i+1]), start_y)
            self.ln(8)

# --- PORTAL NAVIGATION ---
st.set_page_config(page_title="Logistics Document Portal", layout="wide")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Packing List PDF Converter"])

# Shared input lists [cite: 2]
destinations = ["UK - Radial FAO Monat...", "POLAND - Radial Poland...", "AUSTRALIA - FDM..."]
services = ["40\" REEFER", "40\" DRY", "LCL Ocean", "Air Freight"]

if page == "Quote Request Generator":
    st.header("📋 Quote Request Pipeline")
    # ... (Insert your previous Quote Generator code here) ...

elif page == "Packing List PDF Converter":
    st.header("📄 Packing List: Excel to PDF")
    st.markdown("This tool replicates your Excel layout into a professional PDF.")
    
    uploaded_file = st.file_uploader("Upload Packing List (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        df_raw = pd.read_excel(uploaded_file, header=None).fillna("")
        
        # Data Extraction Logic [cite: 3, 5]
        title_val = str(df_raw.iloc[1, 1]) if len(df_raw) > 1 else "Packing List"
        # Extract rows starting from the data header (Row 3 onwards) [cite: 3]
        data_rows = []
        for r in range(3, len(df_raw)):
            row_data = df_raw.iloc[r, [1, 2, 3, 6, 8, 11, 12, 13]].tolist()
            if any(row_data): data_rows.append(row_data)

        if st.button("🛠️ Convert to PDF"):
            pdf = LogisticsPDF(orientation='P', unit='mm', format='A4')
            pdf.create_packing_list(title_val, data_rows)
            
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            st.success("✅ PDF Layout Matches Excel Structure")
            st.download_button("📥 Download Packing List PDF", data=pdf_bytes, file_name="Packing_List.pdf")
