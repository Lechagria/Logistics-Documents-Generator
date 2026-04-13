import streamlit as st
import pandas as pd
import io
import datetime
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

# --- HELPER: CLEAN NUMERIC STRINGS ---
def clean_numeric(value):
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    # Remove commas, dollar signs, and spaces
    clean_val = str(value).replace(',', '').replace('$', '').strip()
    try:
        return float(clean_val)
    except ValueError:
        return 0.0

# --- PDF GENERATOR ---
class ProFormaPDF(FPDF):
    def create_invoice(self, df, dest_info, po_ref):
        self.add_page()
        self.set_margin(10)
        
        self.set_font('Arial', 'B', 14)
        self.cell(0, 8, 'PRO-FORMA INVOICE', ln=1, align='C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, 'Only for Customs Purposes', ln=1, align='C')
        
        self.set_font('Arial', '', 9)
        curr_y = self.get_y()
        self.multi_cell(90, 4, "SHIPPER:\nMonat Global\n10000 NW 15 Terrace\nDoral, FL 33172, USA")
        
        self.set_xy(130, curr_y)
        date_str = datetime.date.today().strftime('%B %d / %Y')
        self.multi_cell(60, 4, f"Doc No.: {po_ref}\nDoc. Date: {date_str}\nRef. No.: {po_ref}\nPage: 1 of 1")
        self.ln(5)

        # Bill To / Ship To Boxes
        self.set_fill_color(235, 235, 235)
        self.set_font('Arial', 'B', 8)
        self.cell(95, 6, ' BILL TO', border=1, fill=True)
        self.cell(95, 6, ' SHIP TO', border=1, fill=True, ln=1)
        
        self.set_font('Arial', '', 8)
        box_y = self.get_y()
        self.multi_cell(95, 5, dest_info, border=1)
        bottom_y = self.get_y()
        self.set_xy(105, box_y)
        self.multi_cell(95, 5, dest_info, border=1)
        self.set_y(max(bottom_y, self.get_y()) + 2)

        # Table Header
        cols = ["SKU", "HTS Code", "Origin", "Description", "Qty", "Unit Price", "Total"]
        widths = [20, 25, 15, 65, 15, 25, 25]
        for i, col in enumerate(cols):
            self.cell(widths[i], 8, col, border=1, fill=True, align='C')
        self.ln()

        # Table Data
        self.set_font('Arial', '', 7)
        grand_total = 0
        for _, row in df.iterrows():
            qty = clean_numeric(row['Qty'])
            u_p = clean_numeric(row['Unit Price'])
            line_total = qty * u_p
            grand_total += line_total
            
            self.cell(widths[0], 7, str(row['SKU']), border=1)
            self.cell(widths[1], 7, str(row['HTS']), border=1, align='C')
            self.cell(widths[2], 7, "USA", border=1, align='C')
            self.cell(widths[3], 7, str(row['Description'])[:45], border=1)
            self.cell(widths[4], 7, f"{qty:,.0f}", border=1, align='C')
            self.cell(widths[5], 7, f"${u_p:.3f}", border=1, align='R')
            self.cell(widths[6], 7, f"${line_total:,.2f}", border=1, align='R', ln=1)

        # Sub-Total
        self.set_font('Arial', 'B', 8)
        self.cell(sum(widths[:-1]), 10, "SUB-TOTAL (USD)", border=1, align='R')
        self.cell(widths[-1], 10, f"${grand_total:,.2f}", border=1, align='R', ln=1)

# --- APP INTERFACE ---
st.set_page_config(page_title="Logistics Portal", layout="wide")

@st.cache_data
def get_hts_map():
    try:
        df = pd.read_csv("HTS Codes.xlsx - Sheet1.csv")
        return df.set_index('Material')['Ext. Material Grp'].to_dict()
    except: return {}

hts_map = get_hts_map()

st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Select Tool", ["Commercial Invoice Generator", "Quote Generator"])

if page == "Commercial Invoice Generator":
    st.header("🧾 Pro-Forma Invoice Tool")
    dest_info = st.text_area("Consignee Address", "MONAT GLOBAL CANADA\n135 SPARKS AVENUE\nNorth York, ON M2H 2S5")
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
        df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
        df.columns = [str(c).strip() for c in df.columns]
        
        invoice_rows = []
        for _, row in df.iterrows():
            sku = str(row.get('Material', ''))
            raw_net = row.get('Net Price', 0)
            qty = clean_numeric(row.get('Order Quantity', 0))
            
            # Application of the "Net Price / 1000" rule
            u_price = clean_numeric(raw_net) / 1000
            
            invoice_rows.append({
                "SKU": sku,
                "HTS": hts_map.get(sku, ""),
                "Description": row.get('Short Text', ''),
                "Qty": qty,
                "Unit Price": u_price,
                "Total": qty * u_price
            })
        
        final_df = st.data_editor(pd.DataFrame(invoice_rows))

        if st.button("🚀 Generate Final Documents"):
            po_ref = str(df.iloc[0].get('Purchasing Document', 'Invoice'))
            pdf = ProFormaPDF()
            pdf.create_invoice(final_df, dest_info, po_ref)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            
            st.download_button("📥 Download PDF Pro-Forma", pdf_bytes, f"Invoice_{po_ref}.pdf")
