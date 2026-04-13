import streamlit as st
import pandas as pd
import io
import datetime
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

# --- PDF GENERATOR (REPLICATING YOUR TEMPLATE) ---
class ProFormaPDF(FPDF):
    def create_invoice(self, df, dest_info, po_ref):
        self.add_page()
        self.set_margin(10)
        
        # Header Section
        self.set_font('Arial', 'B', 14)
        self.cell(0, 8, 'PRO-FORMA INVOICE', ln=1, align='C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, 'Only for Customs Purposes', ln=1, align='C')
        
        self.set_font('Arial', '', 9)
        curr_y = self.get_y()
        self.multi_cell(90, 4, "SHIPPER:\nMonat Global\n10000 NW 15 Terrace\nDoral, FL 33172, USA")
        
        self.set_xy(130, curr_y)
        date_str = datetime.date.today().strftime('%B %d / %Y')
        self.multi_cell(60, 4, f"Doc No.: {po_ref}\nDoc. Date: {date_str}\nDue Date: {date_str}\nRef. No.: {po_ref}\nPage No.: Page 1 of 1")
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

        # Summary Info
        self.set_font('Arial', 'B', 8)
        self.cell(140, 5, "COUNTRY OF ORIGIN:  U.S.A", align='R')
        self.ln()
        self.cell(140, 5, "INCOTERMS:  CIF", align='R')
        self.ln(5)

        # Table
        cols = ["SKU", "HTS Code", "Origin", "Description", "Quantity", "Unit Price", "Total"]
        widths = [20, 25, 15, 65, 15, 25, 25]
        for i, col in enumerate(cols):
            self.cell(widths[i], 8, col, border=1, fill=True, align='C')
        self.ln()

        self.set_font('Arial', '', 7)
        grand_total = 0
        for _, row in df.iterrows():
            val = float(row['Total'])
            grand_total += val
            self.cell(widths[0], 7, str(row['SKU']), border=1)
            self.cell(widths[1], 7, str(row['HTS']), border=1, align='C')
            self.cell(widths[2], 7, "USA", border=1, align='C')
            self.cell(widths[3], 7, str(row['Description'])[:45], border=1)
            self.cell(widths[4], 7, str(row['Qty']), border=1, align='C')
            self.cell(widths[5], 7, f"${row['Unit Price']:.3f}", border=1, align='R')
            self.cell(widths[6], 7, f"${val:,.2f}", border=1, align='R', ln=1)

        # Sub-Total
        self.set_font('Arial', 'B', 8)
        self.cell(sum(widths[:-1]), 10, "SUB-TOTAL (USD)", border=1, align='R')
        self.cell(widths[-1], 10, f"${grand_total:,.2f}", border=1, align='R', ln=1)

        # Footer Legal Disclaimer
        self.ln(5)
        self.set_font('Arial', 'I', 6)
        disclaimer = ("THIS DELIVERY BECOMES A CONTRACT AND IS FIRM AND NON-CANCELABLE. PURCHASER AGREES TO PAY ANY AND ALL COURT COST. "
                      "ATTORNEY'S FEES AND INTEREST IN CONNECTION WITH ANY LEGAL SERVICES INCURRED BY THE SELLER... ALL BILLS ARE PAYABLE "
                      "AND DUE IN ACCORD WITH TERMS HEREON INDICATED.")
        self.multi_cell(0, 3, disclaimer)

# --- EXCEL GENERATOR (STYLIZED) ---
def create_stylized_excel(df, po_ref, dest_info):
    wb = Workbook()
    ws = wb.active
    ws.title = "Commercial Invoice"
    
    # Simple formatting logic to mirror the template
    ws.merge_cells('A1:G1')
    ws['A1'] = "PRO-FORMA INVOICE"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # Column Headers
    headers = ["SKU", "HTS Code", "Origin", "Description", "Quantity", "Unit Price", "Total"]
    ws.append(headers)
    
    for r in df.values.tolist():
        ws.append(r)
        
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

# --- STREAMLIT FRONTEND ---
st.set_page_config(page_title="Logistics Portal", layout="wide")
st.sidebar.title("Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Generator", "Commercial Invoice Generator"])

@st.cache_data
def load_hts_map():
    try:
        df = pd.read_csv("HTS Codes.xlsx - Sheet1.csv")
        return df.set_index('Material')['Ext. Material Grp'].to_dict()
    except: return {}

hts_map = load_hts_map()

if page == "Commercial Invoice Generator":
    st.header("🧾 Pro-Forma Invoice Generator")
    dest_box = st.text_area("Consignee Address", "MONAT GLOBAL CANADA\n135 SPARKS AVENUE\nNorth York, ON M2H 2S5")
    sap_file = st.file_uploader("Upload SAP Export", type=['csv', 'xlsx'])

    if sap_file:
        raw_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
        
        data = []
        for _, r in raw_df.iterrows():
            u_price = float(r['Net Price']) / 1000
            qty = r['Order Quantity']
            data.append({
                "SKU": r['Material'], "HTS": hts_map.get(r['Material'], ""),
                "Description": r['Short Text'], "Qty": qty,
                "Unit Price": u_price, "Total": qty * u_price
            })
        
        edit_df = st.data_editor(pd.DataFrame(data))

        if st.button("🚀 Generate Documents"):
            po_val = str(raw_df.iloc[0]['Purchasing Document'])
            
            # Generate PDF
            pdf = ProFormaPDF()
            pdf.create_invoice(edit_df, dest_box, po_val)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            
            # Generate Excel
            xl_bytes = create_stylized_excel(edit_df, po_val, dest_box)

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 Download PDF", pdf_bytes, f"Invoice_{po_val}.pdf")
            with col2:
                st.download_button("📥 Download Excel", xl_bytes, f"Invoice_{po_val}.xlsx")
