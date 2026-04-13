import streamlit as st
import pandas as pd
from collections import Counter
import io
import datetime
from fpdf import FPDF

# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clean_numeric(value):
    """Safely converts strings with commas or dollar signs to floats."""
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
    """Aggressively cleans SKUs to ensure perfect matching between files."""
    if pd.isna(val): 
        return ""
    s = str(val).strip()
    if s.endswith('.0'): 
        s = s[:-2] # Strip trailing decimals
    if s.lower() == 'nan': 
        return ""
    return s

def get_hts_map():
    """Loads HTS codes fresh without caching to prevent stale blank data."""
    try:
        # Force all columns to be read as plain text instantly
        df = pd.read_csv("HTS_Codes.xlsx - Sheet1.csv", dtype=str)
        
        # Ensure there are no hidden spaces in the column headers
        df.columns = df.columns.str.strip()
        
        # Apply the exact same cleaning function to the HTS database
        df['Material'] = df['Material'].apply(clean_sku)
        df['Ext. Material Grp'] = df['Ext. Material Grp'].fillna('').apply(clean_sku)
        
        # Create the dictionary only for valid rows
        return df[df['Material'] != ""].set_index('Material')['Ext. Material Grp'].to_dict()
    
    except FileNotFoundError:
        st.error("⚠️ **ERROR:** The file `HTS Codes.xlsx - Sheet1.csv` was not found in the same folder as this app. HTS matching will be blank.")
        return {}
    except Exception as e:
        st.error(f"⚠️ **ERROR:** Something went wrong reading the HTS file: {e}")
        return {}

# ==========================================
# 2. PDF GENERATOR (For Quotes Only)
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

# ==========================================
# 3. STREAMLIT APP & NAVIGATION
# ==========================================
st.set_page_config(page_title="Logistics Document Portal", layout="wide")

st.sidebar.title("📑 Logistics Tools")
page = st.sidebar.selectbox("Select Tool", ["Quote Request Generator", "Invoice Line Item Extractor"])

# Load HTS map fresh every time
hts_map = get_hts_map()

# --- TOOL 1: QUOTE REQUEST GENERATOR ---
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
            quote_data = [["QUOTE REQUEST", ""], ["DESTINATION", destination], ["SERVICE", service], ["UNITS", f"{units_final:,}"], ["PALLETS", pallets_final]]
            if formatted_dims:
                quote_data.append(["DIMENSIONS", formatted_dims[0]])
                for extra_dim in formatted_dims[1:]: quote_data.append(["", extra_dim])
            quote_data.extend([["", ""], ["TOTAL WEIGHT", f"{lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS"], ["COMMODITY", commodity], ["INCOTERMS", incoterms], ["VALUE OF CARGO", cargo_value]])
            
            df_output = pd.DataFrame(quote_data)
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                df_output.to_excel(writer, index=False, header=False)

            shipment_info = {
                "DESTINATION": destination, "SERVICE": service, "TOTAL UNITS": f"{units_final:,}", 
                "TOTAL PALLETS": pallets_final, "TOTAL WEIGHT": f"{lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS",
                "COMMODITY": commodity, "INCOTERMS": incoterms, "VALUE": cargo_value
            }
            pdf = QuotePDF()
            pdf.add_page()
            pdf.create_table(shipment_info, formatted_dims)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("1. Download Documents")
                st.download_button("📥 Download Excel Quote", data=excel_buf.getvalue(), file_name=f"Quote_{pallets_final}PLTS.xlsx")
                st.download_button("📥 Download PDF Quote", data=pdf_bytes, file_name=f"Quote_{pallets_final}PLTS.pdf", mime="application/pdf")
            with col2:
                st.subheader("2. Email Draft")
                dim_string = "".join([f"\n- **Dimensions**: {d}" for d in formatted_dims])
                st.code(f"Hi Team,\n\nPlease find details for a new quote:\n- **Dest**: {destination}\n- **Service**: {service}\n- **Units**: {units_final:,}\n- **Pallets**: {pallets_final}{dim_string}\n- **Weight**: {lbs_final:,.2f} LBS\n\nThanks!", language="markdown")


# --- TOOL 2: INVOICE LINE ITEM EXTRACTOR ---
elif page == "Invoice Line Item Extractor":
    st.title("🧾 Invoice Line Item Extractor")
    st.markdown("Upload your **Export** file to instantly generate a ready-to-copy line item table for your Excel template. It will automatically match HTS codes and calculate unit pricing.")
    
    sap_file = st.file_uploader("Upload SAP Export (Export.xlsx or Export.csv)", type=['csv', 'xlsx'])

    if sap_file:
        # Read the file
        if sap_file.name.endswith('.csv'):
            raw_df = pd.read_csv(sap_file)
        else:
            raw_df = pd.read_excel(sap_file)

        # Clean column headers so spaces don't break the code
        raw_df.columns = [str(col).strip() for col in raw_df.columns]
        
        invoice_rows = []
        for _, row in raw_df.iterrows():
            # Clean the SKU from the export file the exact same way
            sku = clean_sku(row.get('Material', ''))
            
            # Skip rows that don't have a valid SKU
            if not sku:
                continue
                
            description = str(row.get('Short Text', '')).strip()
            qty = clean_numeric(row.get('Order Quantity', 0))
            raw_net = clean_numeric(row.get('Net Price', 0))
            
            # The exact math rule: Net Price / 1000
            u_price = raw_net / 1000
            total_val = qty * u_price
            
            # Map HTS Code securely
            hts_code = hts_map.get(sku, "")
            
            # Append to our new clean list (Pallet column successfully removed)
            invoice_rows.append({
                "SKU": sku,
                "HTS Code": hts_code,
                "Origin": "",
                "Description": description,
                "Quantity": int(qty),
                "Unit Price": f"${u_price:,.3f}",  
                "Total": f"${total_val:,.2f}"
            })
        
        # Build the final DataFrame
        if invoice_rows:
            df_final = pd.DataFrame(invoice_rows)

            # Display the results
            st.success(f"✅ Successfully extracted {len(df_final)} line items!")
            st.info("💡 **How to use:** You can either copy the table below directly, or download it as an Excel file.")
            
            # Display the dataframe cleanly without the row numbers (index)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # Create a downloadable Excel buffer
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name="Extracted_Items")
            
            st.download_button(
                label="📥 Download as Excel File",
                data=excel_buffer.getvalue(),
                file_name="Extracted_Line_Items.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.warning("No valid SKUs found in the uploaded file. Please check the file formatting.")
