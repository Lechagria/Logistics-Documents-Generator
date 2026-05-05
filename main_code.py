import streamlit as st
import pandas as pd
from collections import Counter
import io
import datetime
import os
import re

# ==========================================
# 1. PAGE CONFIG & THEME
# ==========================================
st.set_page_config(page_title="Logistics Portal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div.stButton > button:first-child { 
        background-color: #262730; 
        color: white; 
        border-radius: 5px; 
        width: 100%;
        height: 50px;
        font-size: 20px;
        font-weight: bold;
    }
    .stTable { border: 1px solid #262730; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session State for Navigation
if 'active_tool' not in st.session_state:
    st.session_state.active_tool = None

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def clean_numeric(value):
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    clean_val = str(value).replace(',', '').replace('$', '').strip()
    try: return float(clean_val)
    except ValueError: return 0.0

def clean_sku(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.endswith('.0'): s = s[:-2]
    return s

def get_hts_data():
    try:
        current_folder = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_folder, "Cleaned_HTS_Codes.csv")
        df = pd.read_csv(file_path, dtype=str)
        mapping = {}
        for _, row in df.iterrows():
            sku = clean_sku(row.get('SKU', ''))
            if sku:
                mapping[sku] = {
                    "hts": clean_sku(row.get('HTS', '')),
                    "desc": str(row.get('Description', '')).strip()
                }
        return mapping
    except: return {}

def update_detailed_state():
    if "detailed_editor" in st.session_state:
        edits = st.session_state["detailed_editor"]["edited_rows"]
        for row_idx, changes in edits.items():
            for col_name, new_val in changes.items():
                st.session_state.df_detailed.at[row_idx, col_name] = new_val
            
            q = st.session_state.df_detailed.at[row_idx, "Quantity"]
            p = st.session_state.df_detailed.at[row_idx, "Unit Price"]
            uw = st.session_state.df_detailed.at[row_idx, "Unit_Weight_KG"]
            
            st.session_state.df_detailed.at[row_idx, "Total"] = round(q * p, 2)
            st.session_state.df_detailed.at[row_idx, "Total Weight (KG)"] = round(q * uw, 2)

# ==========================================
# 3. DASHBOARD / TOOL SELECTION (CENTER)
# ==========================================
if st.session_state.active_tool is None:
    st.title("📂 Logistics Operations Portal")
    st.subheader("Select a tool to begin:")
    st.write("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📦 Quote Generator"):
            st.session_state.active_tool = "Quote Pipeline"
            st.rerun()
        st.info("Extract packing list data and generate shipment quote templates for carriers.")

    with col2:
        if st.button("🧾 Data Extractor for Invoice & SLI"):
            st.session_state.active_tool = "Invoice Extractor"
            st.rerun()
        st.info("Convert SAP Exports into formatted Customs Invoices with editable HTS summaries.")

# ==========================================
# 4. MAIN APP CONTENT
# ==========================================
else:
    if st.sidebar.button("⬅️ Back to Portal"):
        if 'df_detailed' in st.session_state: del st.session_state.df_detailed
        st.session_state.active_tool = None
        st.rerun()

    # --- TOOL 1: QUOTE PIPELINE ---
    if st.session_state.active_tool == "Quote Pipeline":
        st.sidebar.title("Shipment Details")
        destinations = [
            "UK - Radial FAO Monat, 26, 26 Broadgate, Chadderton, Middleton Oldham OL9 9XA",
            "POLAND - Radial Poland Sp. z o.o. Moszna Parcela 29, Budynek C3 05-840 Brwinów",
            "AUSTRALIA - FDM WAREHOUSING C/O Landmark Global 7 Eucalyptus Place",
            "MONAT Global Canada — 135 SPARKS AVE NORTH YORK ON M2H 2S5 Canada",
            "FENIX FWD INC. - 417 LOGISTIC LAREDO, TEXAS 78045",
            "OTHER (Type Manually below)"
        ]
        services = ["40\" REEFER", "40\" DRY", "20\" DRY", "HAZMAT LCL", "LCL Ocean", "LTL Road", "Air Freight", "Courier"]
        
        selected_dest = st.sidebar.selectbox("Select Destination", destinations)
        destination = st.sidebar.text_input("Manual Destination Entry", value=selected_dest) if selected_dest == "OTHER (Type Manually below)" else selected_dest
        service = st.sidebar.selectbox("Service", services)
        commodity = st.sidebar.text_input("Commodity", value="Finished goods / Haircare / Skincare")
        cargo_value = st.sidebar.text_input("Value of Cargo", value="USD$ ")
        incoterms = st.sidebar.selectbox("Incoterms", ["-", "EXW", "FOB", "DDP", "DAP", "CIF"])

        st.title("📦 Quote Generator")
        packing_file = st.file_uploader("Upload Outbound Packing List (.xlsx)", type=['xlsx'])

        if packing_file:
            df_raw = pd.read_excel(packing_file, header=None).astype(str)
            
            def get_val(keyword, row_off=0, col_off=0):
                for r in range(len(df_raw)-1, -1, -1):
                    for c in range(len(df_raw.columns)):
                        if keyword.lower() == str(df_raw.iloc[r, c]).lower().strip():
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

            if st.button("Generate Template"):
                quote_data = [
                    ["QUOTE REQUEST", ""], ["DESTINATION", destination], ["SERVICE", service],
                    ["UNITS", f"{units_final:,}"], ["PALLETS", pallets_final]
                ]
                if formatted_dims:
                    quote_data.append(["DIMENSIONS", formatted_dims[0]])
                    for extra_dim in formatted_dims[1:]: quote_data.append(["", extra_dim])
                
                quote_data.extend([["", ""], ["TOTAL WEIGHT", f"{lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS"],
                                   ["COMMODITY", commodity], ["INCOTERMS", incoterms], ["VALUE OF CARGO", cargo_value]])
                
                df_output = pd.DataFrame(quote_data)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df_output.to_excel(writer, index=False, header=False)

                dim_string = "".join([f"\n- • Dimensions: {d}" for d in formatted_dims])
                email_body = f"Hi Team,\n\nHope you are having a great week! \n\nPlease find the details below for a new {service} shipment quote — please include insurance cost:\n\n-• Destination: {destination}\n-• Service: {service}\n-• Total Units: {units_final:,}\n-• Pallets: {pallets_final}{dim_string}\n-• Total Weight: {lbs_final:,.2f} LBS | {kgs_final:,.2f} KGS\n-• Commodity: {commodity}\n-• Value: {cargo_value}\n-• Incoterms: {incoterms}\n\nThank you for your help."

                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("1. Download Document")
                    st.download_button("📥 Download Excel", data=buf.getvalue(), file_name=f"Quote_{pallets_final}PLTS.xlsx")
                    st.table(df_output)
                with col2:
                    st.subheader("2. Email Draft")
                    st.code(email_body, language="markdown")

    # --- TOOL 2: INVOICE EXTRACTOR (FIXED FOR MULTI-PO) ---
    elif st.session_state.active_tool == "Invoice Extractor":
        st.title("🧾 Data Extractor")
        
        c1, c2 = st.columns(2)
        with c1: sap_file = st.file_uploader("1. Upload SAP Export", type=['csv', 'xlsx'])
        with c2: pl_file = st.file_uploader("2. Upload Packing List", type=['csv', 'xlsx'])

        if sap_file and pl_file:
            hts_mapping = get_hts_data()
            
            # --- Robust Multi-PO Weight Extraction ---
            temp_pl = pd.read_excel(pl_file, header=None) if pl_file.name.endswith('.xlsx') else pd.read_csv(pl_file, header=None)
            weight_map = {}
            current_cols = None

            for i, row in temp_pl.iterrows():
                row_vals = [str(x).strip() for x in row.values]
                # Identify header row anywhere in the file
                if any(x in str(row_vals).lower() for x in ["sku", "material"]):
                    current_cols = [v.replace('\n', ' ').strip() for v in row_vals]
                    continue
                
                if current_cols:
                    row_dict = dict(zip(current_cols, row.values))
                    sku = clean_sku(row_dict.get('SKU') or row_dict.get('Material'))
                    if sku and sku != "nan":
                        tw_box = clean_numeric(row_dict.get('Total Weight / Box') or row_dict.get('Tot. Weight / Bxs'))
                        t_units = clean_numeric(row_dict.get('Total Units'))
                        if t_units > 0:
                            weight_map[sku] = (tw_box / t_units) * 0.453592

            # --- SAP Processing (Original Price Logic) ---
            if 'df_detailed' not in st.session_state:
                raw_df = pd.read_csv(sap_file) if sap_file.name.endswith('.csv') else pd.read_excel(sap_file)
                raw_df.columns = [str(col).strip() for col in raw_df.columns]
                
                rows = []
                for _, row in raw_df.iterrows():
                    sku = clean_sku(row.get('Material', ''))
                    if not sku: continue
                    
                    sku_info = hts_mapping.get(sku, {"hts": "", "desc": ""})
                    qty = clean_numeric(row.get('Order Quantity', 0))
                    
                    # Original logic as per your request
                    u_price = round(clean_numeric(row.get('Net Price', 0)) / 1000, 2)
                    u_weight = weight_map.get(sku, 0.0)
                    
                    rows.append({
                        "PO#": str(row.get('Purchasing Document', '')),
                        "SKU": sku, "HTS Code": sku_info["hts"],
                        "Origin": "USA" if sku.startswith('600') else "CHINA" if sku.startswith('300') else "",
                        "Description": str(row.get('Short Text', '')).strip(),
                        "Quantity": int(qty), "Unit Price": u_price, "Total": round(qty * u_price, 2),
                        "Unit_Weight_KG": u_weight, "Total Weight (KG)": round(qty * u_weight, 2),
                        "Customs_Desc_Internal": sku_info["desc"]
                    })
                st.session_state.df_detailed = pd.DataFrame(rows)

            st.subheader("Commercial Invoice Data (Editable)")
            edited_detailed = st.data_editor(
                st.session_state.df_detailed.drop(columns=['Customs_Desc_Internal', 'Unit_Weight_KG']),
                use_container_width=True, hide_index=True,
                column_config={
                    "Unit Price": st.column_config.NumberColumn(format="$%.3f"),
                },
                key="detailed_editor", on_change=update_detailed_state
            )

            st.markdown("### HTS Summary (SLI Weight Breakdown)")
            summary_grouped = edited_detailed.merge(
                st.session_state.df_detailed[['SKU', 'Customs_Desc_Internal']], on='SKU', how='left'
            ).groupby(['Customs_Desc_Internal', 'HTS Code']).agg({
                'Quantity': 'sum', 'Total Weight (KG)': 'sum', 'Total': 'sum'
            }).reset_index()
            
            # Renaming columns to match the requested display order
            summary_grouped.columns = ['Customs Description', 'HTS Code', 'Total Qty', 'Total Weight (KG)', 'Total Value']

            st.data_editor(
                summary_grouped, use_container_width=True, hide_index=True,
                column_config={
                    "Total Value": st.column_config.NumberColumn(format="$%.2f"),
                    "Total Weight (KG)": st.column_config.NumberColumn(format="%.2f kg")
                },
                key="summary_editor"
            )

            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                edited_detailed.to_excel(writer, index=False, sheet_name="Details")
                summary_grouped.to_excel(writer, index=False, sheet_name="Summary")
            st.download_button("📥 Download SLI Excel", excel_buf.getvalue(), "SLI_Invoice.xlsx")
