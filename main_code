import streamlit as st
import pandas as pd
from collections import Counter
import io
import re
from fpdf import FPDF
import datetime

# --- PDF GENERATOR CLASS ---
class PackingListPDF(FPDF):
    def header(self):
        # Add a logo placeholder or company name here if needed
        self.set_font('Arial', 'B', 20)
        self.cell(0, 15, 'PACKING LIST', border=0, ln=1, align='C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, f'Generated on: {datetime.date.today().strftime("%B %d, %Y")}', ln=1, align='R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def create_info_table(self, data_dict, dims):
        self.set_fill_color(240, 240, 240) # Light grey for headers
        self.set_font('Arial', 'B', 11)
        
        # Table Header
        self.cell(60, 10, ' CATEGORY', border=1, fill=True)
        self.cell(130, 10, ' SHIPMENT DETAILS', border=1, ln=1, fill=True)
        
        self.set_font('Arial', '', 10)
        # Main Data
        for key, value in data_dict.items():
            self.set_font('Arial', 'B', 10)
            self.cell(60, 9, f" {key}", border=1)
            self.set_font('Arial', '', 10)
            self.cell(130, 9, f" {value}", border=1, ln=1)
        
        # Dimensions Rows (Handles multiple sizes)
        for i, d in enumerate(dims):
            label = " Dimensions" if i == 0 else ""
            self.set_font('Arial', 'B', 10)
            self.cell(60, 9, label, border=1)
            self.set_font('Arial', '', 10)
            self.cell(130, 9, f" {d}", border=1, ln=1)

# --- APP CONFIG ---
st.set_page_config(page_title="Packing List PDF Generator", layout="wide")
st.title("📄 Packing List PDF Generator")
st.markdown("Convert your Outbound Packing List Excel into a professional PDF document.")

# --- SIDEBAR LISTS ---
destinations = [
    "UK - Radial FAO Monat, 26, 26 Broadgate, Chadderton, Middleton Oldham OL9 9XA",
    "POLAND - Radial Poland Sp. z o.o. Moszna Parcela 29, Budynek C3 05-840 Brwinów",
    "AUSTRALIA - FDM WAREHOUSING C/O Landmark Global 7 Eucalyptus Place",
    "MONAT Global Canada — 135 SPARKS AVE NORTH YORK ON M2H 2S5 Canada",
    "FENIX FWD INC. - 417 LOGISTIC LAREDO, TEXAS 78045",
    "OTHER (Type Manually below)"
]

# --- SIDEBAR INPUTS ---
with st.sidebar:
    st.header("Document Settings")
    selected_dest = st.selectbox("Destination", destinations)
    destination = st.text_input("Manual Entry", value=selected_dest) if selected_dest == "OTHER (Type Manually below)" else selected_dest
    
    commodity = st.text_input("Commodity", "Finished goods / Haircare / Skincare")
    incoterms = st.selectbox("Incoterms", ["EXW", "FOB", "DDP", "DAP", "CIF"])

# --- FILE UPLOAD & LOGIC ---
uploaded_file = st.file_uploader("Upload Outbound Packing List (.xlsx)", type=['xlsx'])

if uploaded_file:
    # 1. Extraction Logic (Ironclad)
    df_raw = pd.read_excel(uploaded_file, header=None).astype(str)
    
    def get_val(keyword, row_off=0, col_off=0):
        for r in range(len(df_raw)-1, -1, -1):
            for c in range(len(df_raw.columns)):
                if keyword.lower() == str(df_raw.iloc[r, c]).lower().strip():
                    try: return df_raw.iloc[r + row_off, c + col_off]
                    except: return "0"
        return "0"

    def clean_num(val):
        clean = re.sub(r'[^\d.]', '', str(val))
        try: return float(clean)
        except: return 0.0

    # 2. Get Data
    pallets = int(clean_num(get_val("Pallets", row_off=-1)))
    units = int(clean_num(get_val("Units", row_off=-1)))
    lbs = clean_num(get_val("Gross Weight", row_off=-1))
    kgs = lbs * 0.453592

    # Dimensions
    dim_list = []
    for c in range(len(df_raw.columns)):
        if any("dim" in str(val).lower() and "pallet" in str(val).lower() for val in df_raw.iloc[:5, c]):
            raw_dims = df_raw.iloc[3:, c].tolist()
            dim_list = [d.strip() for d in raw_dims if "x" in str(d).lower() and len(str(d)) > 5]
            break
    dim_counts = Counter(dim_list)
    formatted_dims = [f"{d} (x{count})" if count > 1 else d for d, count in dim_counts.items()]

    # 3. PDF GENERATION
    if st.button("🛠️ Build Packing List PDF"):
        shipment_data = {
            "DESTINATION": destination,
            "TOTAL UNITS": f"{units:,}",
            "TOTAL PALLETS": pallets,
            "TOTAL WEIGHT": f"{lbs:,.2f} LBS | {kgs:,.2f} KGS",
            "COMMODITY": commodity,
            "INCOTERMS": incoterms
        }

        pdf = PackingListPDF()
        pdf.add_page()
        pdf.create_info_table(shipment_data, formatted_dims)
        
        # Binary string conversion
        pdf_output = pdf.output(dest='S').encode('latin-1')
        
        st.success("✅ PDF Created Successfully!")
        st.download_button(
            label="📥 Download Packing List PDF",
            data=pdf_output,
            file_name=f"Packing_List_{datetime.date.today()}.pdf",
            mime="application/pdf"
        )
else:
    st.info("Please upload an Excel file to generate the PDF.")
