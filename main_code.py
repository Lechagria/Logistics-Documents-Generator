import streamlit as st
import pandas as pd
from collections import Counter
import io
import re
import datetime
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clean_numeric(value):
    """Safely converts strings with commas or dollar signs to floats."""
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

@st.cache_data
def get_hts_map():
    try:
        df = pd.read_csv("HTS Codes.xlsx - Sheet1.csv")
        return df.set_index('Material')['Ext. Material Grp'].to_dict()
    except Exception as e:
        return {}

# ==========================================
# 2. PDF GENERATOR CLASSES
# ==========================================
class QuotePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 15, 'QUOTE REQUEST', border=0, ln=1, align='C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Date: {datetime.date.today().strftime("%B %d, %Y")}', ln=1, align='R')
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
        
        for i, d in enumerate(dims):
            label = " DIMENSIONS" if i == 0 else ""
            self.set_font('Arial', 'B', 10)
            self.cell(60, 9, label, border=1)
            self.set_font('Arial', '', 10)
            self.cell(130, 9, f" {d}", border=1, ln=1)

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
            self.cell(widths[4], 7, f"{row['Qty']:,.0f}", border=1, align='C')
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
                      "ATTORNEY'S FEES AND INTEREST IN CONNECTION WITH ANY LEGAL SERVICES INCURRED BY THE SELLER... ALL BILLS ARE PAYABLE "
                      "AND DUE IN ACCORD WITH TERMS HEREON INDICATED.")
        self.multi_cell(0, 3, disclaimer)

# ==========================================
# 3. EXCEL GENERATOR (STYLIZED PRO-FORMA)
# ==========================================
def create_stylized_excel(df, po_ref, dest_info):
    wb = Workbook()
    ws = wb.active
    ws.title = "INVOICE"
    
    ws.sheet_view.showGridLines = False

    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 18
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 50
    ws.column_dimensions['H'].width = 12
    ws.column_dimensions['I'].width = 15
    ws.column_dimensions['J'].width = 15

    bold_font = Font(bold=True)
    
    # Header
    ws['D25'] = "PRO-FORMA INVOICE"
    ws['D25'].font = Font(bold=True, size=14)

    # Document Info
    date_str = datetime.date.today().strftime('%B %d /%Y')
    ws['H27'] = "Doc No.:"
    ws['I27'] = po_ref
    ws['H28'] = "Doc. Date:"
    ws['I28'] = date_str
    ws['H29'] = "Due Date:"
    ws['I29'] = date_str
    ws['H30'] = "Ref. No.:"
    ws['I30'] = po_ref
    ws['H31'] = "Page No.:"
    ws['I31'] = "Page 1 of 1"

    grand_total = df['Total'].sum()

    # Addresses & Totals
    ws['D33'] = "BILL TO"
    ws['G33'] = "SHIP TO"
    ws['I33'] = "TOTAL DUE"
    for cell in ['D33', 'G33', 'I33']: ws[cell].font = bold_font

    ws['D34'] = "MONAT GLOBAL CANADA UCL"
    ws['G34'] = "MONAT GLOBAL CANADA"
    ws['D35'] = "135 SPARKS AVE"
    ws['G35'] = "135 SPARKS AVENUE"
    ws['I35'] = grand_total
    ws['I35'].number_format = '"$"#,##0.00'
    ws['D36'] = "TORONTO ON M2H2S5"
    ws['G36'] = "North York, ON M2H 2S5"
    ws['D37'] = "CANADA"
    ws['G37'] = "CANADA"

    ws['I37'] = "COUNTRY OF ORIGEN:"
    ws['I38'] = "U.S.A"
    ws['I39'] = "INCOTERMS"
    ws['I40'] = "CIF"

    # Table Headers
    headers = ["SKU", "HTS Code", "Origin", "Description", "Quantity", "Unit Price", "Total"]
    for col_num, header in enumerate(headers, start=4): 
        cell = ws.cell(row=42, column=col_num, value=header)
        cell.font = bold_font
        cell.alignment = Alignment(horizontal='center')

    # Table Data
    current_row = 43
    for _, row in df.iterrows():
        ws.cell(row=current_row, column=4, value=str(row['SKU']))
        ws.cell(row=current_row, column=5, value=str(row['HTS'])).alignment = Alignment(horizontal='center')
        ws.cell(row=current_row, column=6, value="USA").alignment = Alignment(horizontal='center')
        ws.cell(row=current_row, column=7, value=str(row['Description']))
        ws.cell(row=current_row, column=8, value=row['Qty']).alignment = Alignment(horizontal='center')
        ws.cell(row=current_row, column=9, value=row['Unit Price']).number_format = '"$"#,##0.000'
        ws.cell(row=current_row, column=10, value=row['Total']).number_format = '"$"#,##0.00'
        current_row += 1

    # Bottom Sub-Total
    current_row += 2
    ws.cell(row=current_row, column=8, value="SUB-TOTAL").font = bold_font
    ws.cell(row=current_row, column=10, value=grand_total).number_format = '"$"#,##0.00'
    
    current_row += 2
    disclaimer = "THIS DELIVERY BECOMES A CONTRACT AND IS FIRM AND NON-CANCELABLE. PURCHASER AGREES TO PAY ANY AND ALL COURT COST..."
    ws.cell(row=current_row, column=4, value=disclaimer).font = Font(italic=True, size=8)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

# ==========================================
# 4. STREAMLIT APP & NAVIGATION
# ==========================================
st.set_page_config(page_title="Logistics Document Portal", layout="wide")

st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Commercial Invoice Generator"])

hts_map = get_hts_map()

# --- QUOTE REQUEST GENERATOR ---
if page == "Quote Request Generator":
    st.title("📦 Quote Request Pipeline")
    
    destinations = [
        "UK - Radial FAO Monat, 26, 26 Broadgate, Chadderton, Middleton Oldham OL9 9XA",
        "POLAND - Radial Poland Sp. z o.o. Moszna Parcela 29, Budynek C3 05-840 Brwinów",
        "AUSTRALIA - FDM WAREHOUSING C/O Landmark Global 7 Eucalyptus Place",
        "MONAT Global Canada — 135 SPARKS AVE NORTH YORK ON M2H 2S5 Canada",
        "FENIX FWD INC. - 417 LOGISTIC LAREDO, TEXAS 78045",
        "OTHER (Type Manually below)"
    ]
    services = ["40\" REEFER", "40\" DRY", "20\" DRY", "HAZMAT LCL", "LCL Ocean", "LTL Road", "Air Freight", "Courier"]

    with st.sidebar:
        st.header("Shipment Details")
        selected_dest = st.selectbox("Select Destination", destinations)
        destination = st.text_input("Manual Destination Entry", value=selected_dest) if selected_dest == "OTHER (Type Manually below)" else selected_dest
        service = st.selectbox("Service", services)
        commodity = st.text_input("Commodity", value="Finished goods / Haircare / Skincare")
        cargo_value = st.text_input("Value of Cargo", value="USD$ ")
        incoterms = st.selectbox("Incoterms", ["-", "EXW", "FOB", "DDP", "DAP", "CIF"])

    packing_file = st.file_uploader("Upload Outbound Packing List (.xlsx)", type=['xlsx'])

    if packing_file:
        df_raw = pd.read_excel(packing_file, header=None).astype(str)
        
        def get_val(keyword, row_off=0, col_off=0):
            for r in range(len(df_raw)-1, -1, -1):
                for c in range(len(df_raw.columns)):
                    cell_val = str(df_raw.iloc[r, c]).lower().strip()
                    if keyword.lower() == cell_val:
                        try: return df_raw.iloc[r + row_off, c + col_off]
                        except: return "0"
            return "0"

        pallets_final = int(clean_numeric(get_val("Pallets", row_off=-1)))
        units_final = int(clean_numeric(get_val("Units", row_off=-1)))
        lbs_final = clean_numeric(get_val("Gross Weight", row_off=-1))
        kgs_final = lbs_final * 0.453592

        dim_list = []
        for c in range(len(df_raw.columns)):
            if any("dim" in str(val).lower() and "pallet" in str(val).lower() for val in df_raw.iloc[:5, c]):
                potential_dims = df_raw.iloc[3:, c].tolist()
                dim_list = [d.strip() for d in potential_dims if "x" in str(d).lower() and len(str(d)) > 5]
                break
        dim_counts = Counter(dim_list)
        formatted_dims = [f"{d} (x{count})" if count > 1 else d for d, count in dim_counts.items()]

        st.success(f"✅ Data Extracted: **{pallets_final}** Pallets | **{units_final:,}** Units")

        if st.button("🚀 Generate Quote Package"):
            # Excel
            quote_data = [["QUOTE REQUEST", ""], ["DESTINATION", destination], ["SERVICE", service], ["UNITS", f"{units_final:,}"], ["PALLETS", pallets_final]]
            if formatted_dims:
                quote_data.append(["DIMENSIONS", formatted_dims[0]])
                for extra_dim in formatted_dims[1:]: quote_data.append(["", extra_dim])
            quote_data.extend([["", ""], ["TOTAL WEIGHT", f"{lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS"], ["COMMODITY", commodity], ["INCOTERMS", incoterms], ["VALUE OF CARGO", cargo_value]])
            
            df_output = pd.DataFrame(quote_data)
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                df_output.to_excel(writer, index=False, header=False)

            # PDF
            shipment_info = {
                "DESTINATION": destination, "SERVICE": service, "TOTAL UNITS": f"{units_final:,}", 
                "TOTAL PALLETS": pallets_final, "TOTAL WEIGHT": f"{lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS",
                "COMMODITY": commodity, "INCOTERMS": incoterms, "VALUE": cargo_value
            }
            pdf = QuotePDF()
            pdf.add_page()
            pdf.create_table(shipment_info, formatted_dims)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')

            # Email Draft
            dim_string = "".join([f"\n- **Dimensions**: {d}" for d in formatted_dims])
            email_body = f"Hi Team,\n\nHope you are having a great week! \n\nPlease find the details below for a new {service} shipment quote:\n\n- **Destination**: {destination}\n- **Service**: {service}\n- **Total Units**: {units_final:,}\n- **Pallets**: {pallets_final}{dim_string}\n- **Total Weight**: {lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS\n- **Commodity**: {commodity}\n- **Value**: {cargo_value}\n- **Incoterms**: {incoterms}\n\nPlease let us know the best rates and estimated transit times for this.\n\nAttached are the Quote Request and Packing List.\n\nThanks!"

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("1. Download Documents")
                st.download_button("📥 Download Excel Quote", data=excel_buf.getvalue(), file_name=f"Quote_{pallets_final}PLTS.xlsx")
                st.download_button("📥 Download PDF Quote", data=pdf_bytes, file_name=f"Quote_{pallets_final}PLTS.pdf", mime="application/pdf")
            with col2:
                st.subheader("2. Email Draft")
                st.code(email_body, language="markdown")

# --- COMMERCIAL INVOICE GENERATOR ---
elif page == "Commercial Invoice Generator":
    st.title("🧾 Pro-Forma Invoice Generator")
    
    with st.expander("Settings", expanded=True):
        dest_info = st.text_area("Consignee Address", "MONAT GLOBAL CANADA\n135 SPARKS AVENUE\nNorth York, ON M2H 2S5")
    
    sap_file = st.file_uploader("Upload SAP Export (EXPORT-1.xlsx)", type=['csv', 'xlsx'])

    if sap_file:
        if sap_file.name.endswith('.csv'):
            raw_df = pd.read_csv(sap_file)
        else:
            raw_df = pd.read_excel(sap_file)

        # Fuzzy matching: strip spaces from columns
        raw_df.columns = [str(col).strip() for col in raw_df.columns]
        
        invoice_rows = []
        for _, row in raw_df.iterrows():
            sku = str(row.get('Material', ''))
            raw_net = row.get('Net Price', 0)
            qty = clean_numeric(row.get('Order Quantity', 0))
            description = row.get('Short Text', '')
            
            # The Critical Fix: clean_numeric is used here instead of float
            u_price = clean_numeric(raw_net) / 1000
            total_val = qty * u_price
            
            hts_code = hts_map.get(row.get('Material'), "")
            
            invoice_rows.append({
                "SKU": sku,
                "HTS": hts_code,
                "Description": description,
                "Qty": qty,
                "Unit Price": u_price,
                "Total": total_val
            })
        
        st.subheader("Data Preview")
        st.caption("Edit HTS codes or Prices directly in the table below if needed.")
        df_final = st.data_editor(pd.DataFrame(invoice_rows), num_rows="dynamic")

        if st.button("🚀 Generate Final Documents"):
            po_ref = str(raw_df.iloc[0].get('Purchasing Document', 'UNKNOWN'))
            
            # PDF Generation
            pdf = ProFormaPDF()
            pdf.create_invoice(df_final, dest_info, po_ref)
            pdf_output = pdf.output(dest='S').encode('latin-1')
            
            # Excel Generation
            xl_output = create_stylized_excel(df_final, po_ref, dest_info)
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📥 Download PDF Invoice", pdf_output, f"Invoice_{po_ref}.pdf", "application/pdf")
            with c2:
                st.download_button("📥 Download Excel Invoice", xl_output, f"Invoice_{po_ref}.xlsx")
                st.download_button("📥 Download Excel Invoice", xl_output, f"Invoice_{po_ref}.xlsx")
