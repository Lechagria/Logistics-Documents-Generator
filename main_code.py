import streamlit as st
import pandas as pd
import io
import datetime
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

# --- PDF GENERATOR: REPLICATING PRO-FORMA TEMPLATE ---
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

        # Table Header
        cols = ["SKU", "HTS Code", "Origin", "Description", "Quantity", "Unit Price", "Total"]
        widths = [20, 25, 15, 65, 15, 25, 25]
        for i, col in enumerate(cols):
            self.cell(widths[i], 8, col, border=1, fill=True, align='C')
        self.ln()

        # Table Data
        self.set_font('Arial', '', 7)
        grand_total = 0
        for _, row in df.iterrows():
            total_val = float(row['Total'])
            grand_total += total_val
            self.cell(widths[0], 7, str(row['SKU']), border=1)
            self.cell(widths[1], 7, str(row['HTS']), border=1, align='C')
            self.cell(widths[2], 7, "USA", border=1, align='C')
            self.cell(widths[3], 7, str(row['Description'])[:45], border=1)
            self.cell(widths[4], 7, str(row['Qty']), border=1, align='C')
            self.cell(widths[5], 7, f"${row['Unit Price']:.3f}", border=1, align='R')
            self.cell(widths[6], 7, f"${total_val:,.2f}", border=1, align='R', ln=1)

        # Total
        self.set_font('Arial', 'B', 8)
        self.cell(sum(widths[:-1]), 10, "SUB-TOTAL (USD)", border=1, align='R')
        self.cell(widths[-1], 10, f"${grand_total:,.2f}", border=1, align='R', ln=1)

        # Footer Legal Disclaimer
        self.ln(5)
        self.set_font('Arial', 'I', 6)
        disclaimer = ("THIS DELIVERY BECOMES A CONTRACT AND IS FIRM AND NON-CANCELABLE. PURCHASER AGREES TO PAY ANY AND ALL COURT COST. "
                      "ATTORNEY'S FEES AND INTEREST IN CONNECTION WITH ANY LEGAL SERVICES INCURRED BY THE SELLER...")
        self.multi_cell(0, 3, disclaimer)

# --- PORTAL APP ---
st.set_page_config(page_title="Logistics Portal", layout="wide")

# Persistent HTS Lookup
@st.cache_data
def get_hts_map():
    try:
        # Load your HTS master file
        hts_df = pd.read_csv("HTS Codes.xlsx - Sheet1.csv")
        return hts_df.set_index('Material')['Ext. Material Grp'].to_dict()
    except Exception as e:
        st.warning(f"HTS Master file not found. Automatic lookup disabled. Error: {e}")
        return {}

hts_map = get_hts_map()

# Sidebar Navigation
page = st.sidebar.selectbox("Select Tool", ["Commercial Invoice Generator", "Quote Generator"])

if page == "Commercial Invoice Generator":
    st.header("🧾 Commercial Invoice Generator")
    
    with st.expander("Settings", expanded=True):
        dest_info = st.text_area("Consignee Address", "MONAT GLOBAL CANADA\n135 SPARKS AVENUE\nNorth York, ON M2H 2S5")
    
    sap_file = st.file_uploader("Upload SAP Export (EXPORT-1.xlsx)", type=['csv', 'xlsx'])

    if sap_file:
        # Load SAP Data
        if sap_file.name.endswith('.csv'):
            raw_df = pd.read_csv(sap_file)
        else:
            raw_df = pd.read_excel(sap_file)

        # --- FUZZY COLUMN MATCHING ---
        # Strip invisible spaces from column names to avoid KeyErrors
        raw_df.columns = [str(col).strip() for col in raw_df.columns]
        
        invoice_rows = []
        for _, row in raw_df.iterrows():
            # Fallback logic for column names
            sku = str(row.get('Material', ''))
            net_price = float(row.get('Net Price', 0))
            qty = row.get('Order Quantity', 0)
            description = row.get('Short Text', '')
            
            # Logic: Net Price / 1000
            u_price = net_price / 1000
            total_val = qty * u_price
            
            # XLOOKUP logic for HTS
            hts_code = hts_map.get(row.get('Material'), "")
            
            invoice_rows.append({
                "SKU": sku,
                "HTS": hts_code,
                "Description": description,
                "Qty": qty,
                "Unit Price": u_price,
                "Total": total_val
            })
        
        # Editable Grid for Manual Corrections
        st.subheader("Data Preview")
        st.caption("You can edit HTS codes or Prices directly in the table below.")
        df_final = st.data_editor(pd.DataFrame(invoice_rows), num_rows="dynamic")

        if st.button("🚀 Generate Final Documents"):
            po_ref = str(raw_df.iloc[0].get('Purchasing Document', 'UNKNOWN'))
            
            # 1. Generate PDF
            pdf = ProFormaPDF()
            pdf.create_invoice(df_final, dest_info, po_ref)
            pdf_output = pdf.output(dest='S').encode('latin-1')
            
            # 2. Generate Excel
            xl_output = io.BytesIO()
            with pd.ExcelWriter(xl_output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name="Invoice")
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 Download PDF Invoice", pdf_output, f"Invoice_{po_ref}.pdf", "application/pdf")
            with c2:
                st.download_button("📥 Download Excel Invoice", xl_output.getvalue(), f"Invoice_{po_ref}.xlsx")

# (Previous Quote Generator code can be added in a separate 'if' block here)
