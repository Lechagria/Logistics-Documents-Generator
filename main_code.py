import streamlit as st
import pandas as pd
from collections import Counter
import io
import re
from fpdf import FPDF
import datetime

# --- PDF GENERATOR: PRO-FORMA INVOICE STYLE ---
class InvoicePDF(FPDF):
    def create_invoice(self, invoice_df, dest_info, po_nums):
        self.add_page()
        
        # Header Section - Matching Pro-Forma Template
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'PRO-FORMA INVOICE', border=0, ln=1, align='C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, 'Only for Customs Purposes', border=0, ln=1, align='C')
        
        self.set_font('Arial', '', 9)
        self.ln(5)
        
        # Right-aligned Info Box
        curr_y = self.get_y()
        self.set_x(130)
        self.multi_cell(60, 5, f"Doc No: {po_nums[0]}\nDoc Date: {datetime.date.today().strftime('%B %d, %Y')}\nRef No: {po_nums[0]}\nPage: Page 1 of 1", border=0)
        
        self.set_xy(10, curr_y)
        self.multi_cell(80, 5, f"SHIPPER:\nMonat Global\n10000 NW 15 Terrace\nDoral, FL 33172, USA", border=0)
        self.ln(5)

        # Bill To / Ship To Section
        self.set_fill_color(240, 240, 240)
        self.set_font('Arial', 'B', 9)
        self.cell(95, 7, ' BILL TO', border=1, fill=True)
        self.cell(95, 7, ' SHIP TO', border=1, ln=1, fill=True)
        
        self.set_font('Arial', '', 8)
        self.cell(95, 15, f"{dest_info}", border=1)
        self.cell(95, 15, f"{dest_info}", border=1, ln=1)
        self.ln(5)

        # Itemized Table
        self.set_font('Arial', 'B', 8)
        cols = ["SKU", "HTS Code", "Origin", "Description", "Qty", "Unit Price", "Total"]
        widths = [25, 25, 15, 60, 15, 25, 25]
        for i, col in enumerate(cols):
            self.cell(widths[i], 8, col, border=1, fill=True, align='C')
        self.ln()

        self.set_font('Arial', '', 7)
        grand_total = 0
        for _, row in invoice_df.iterrows():
            grand_total += row['Total']
            self.cell(widths[0], 7, str(row['SKU']), border=1)
            self.cell(widths[1], 7, str(row['HTS']), border=1, align='C')
            self.cell(widths[2], 7, "USA", border=1, align='C')
            self.cell(widths[3], 7, str(row['Description'])[:40], border=1)
            self.cell(widths[4], 7, str(row['Qty']), border=1, align='C')
            self.cell(widths[5], 7, f"${row['Unit Price']:.3f}", border=1, align='R')
            self.cell(widths[6], 7, f"${row['Total']:,.2f}", border=1, align='R', ln=1)

        # Totals
        self.set_font('Arial', 'B', 9)
        self.cell(sum(widths[:-1]), 10, "SUB-TOTAL (USD)", border=1, align='R')
        self.cell(widths[-1], 10, f"${grand_total:,.2f}", border=1, align='R', ln=1)
        
        # Legal Disclaimer from Template
        self.ln(5)
        self.set_font('Arial', 'I', 6)
        disclaimer = "THIS DELIVERY BECOMES A CONTRACT AND IS FIRM AND NON-CANCELABLE... ALL BILLS ARE PAYABLE AND DUE IN ACCORD WITH TERMS HEREON INDICATED."
        self.multi_cell(0, 3, disclaimer, border=0)

# --- PORTAL LOGIC ---
st.set_page_config(page_title="Logistics Portal", layout="wide")
page = st.sidebar.selectbox("Select Tool", ["Quote Generator", "Commercial Invoice Generator"])

# Permanent HTS Database 
@st.cache_data
def load_hts_master():
    try:
        df = pd.read_csv("HTS Codes.xlsx - Sheet1.csv")
        return df.set_index('Material')['Ext. Material Grp'].to_dict()
    except: return {}

hts_lookup = load_hts_master()

if page == "Commercial Invoice Generator":
    st.header("🧾 Commercial Invoice Generator")
    
    with st.sidebar:
        st.header("Invoice Settings")
        dest_info = st.text_area("Consignee Address", "MONAT GLOBAL CANADA\n135 SPARKS AVENUE\nNorth York, ON M2H 2S5")
    
    sap_file = st.file_uploader("Upload SAP Export (EXPORT-1.xlsx)", type=['csv', 'xlsx'])

    if sap_file:
        sap_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
        unique_pos = sap_df['Purchasing Document'].unique().astype(str)

        # Processing 
        invoice_rows = []
        for _, row in sap_df.iterrows():
            unit_price = float(row['Net Price']) / 1000  # Logic: Net/1000 [cite: 1]
            qty = row['Order Quantity']
            invoice_rows.append({
                "SKU": str(row['Material']),
                "HTS": hts_lookup.get(row['Material'], ""), # XLOOKUP 
                "Description": row['Short Text'],
                "Qty": qty,
                "Unit Price": unit_price,
                "Total": qty * unit_price
            })
        
        # Interactive Editor for manual HTS entry
        st.subheader("Invoice Data Review")
        st.info("💡 You can manually type missing HTS codes directly into the table below.")
        edited_df = st.data_editor(pd.DataFrame(invoice_rows), num_rows="dynamic")

        if st.button("🛠️ Generate Final Documents"):
            # PDF Creation
            pdf = InvoicePDF()
            pdf.create_invoice(edited_df, dest_info, unique_pos)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            
            # Excel Creation
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                edited_df.to_excel(writer, index=False)

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 Download PDF Invoice", data=pdf_bytes, file_name=f"Invoice_{unique_pos[0]}.pdf")
            with c2:
                st.download_button("📥 Download Excel Invoice", data=excel_buf.getvalue(), file_name=f"Invoice_{unique_pos[0]}.xlsx")
