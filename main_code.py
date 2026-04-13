def create_stylized_excel(df, po_ref, dest_info):
    wb = Workbook()
    ws = wb.active
    ws.title = "INVOICE"
    
    # Clean up the view (hides gridlines like a real form)
    ws.sheet_view.showGridLines = False

    # Set exact column widths to match your image
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 18
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 50
    ws.column_dimensions['H'].width = 12
    ws.column_dimensions['I'].width = 15
    ws.column_dimensions['J'].width = 15

    bold_font = Font(bold=True)
    
    # 1. Header (Row 25)
    ws['D25'] = "PRO-FORMA INVOICE"
    ws['D25'].font = Font(bold=True, size=14)

    # 2. Document Info (Right side, Rows 27-31)
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

    # Calculate Grand Total for the "TOTAL DUE" box
    grand_total = df['Total'].sum()

    # 3. Addresses & Totals (Rows 33-37)
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

    # 4. Incoterms / Origin (Rows 37-40)
    ws['I37'] = "COUNTRY OF ORIGEN:"
    ws['I38'] = "U.S.A"
    ws['I39'] = "INCOTERMS"
    ws['I40'] = "CIF"

    # 5. Table Headers (Row 42)
    headers = ["SKU", "HTS Code", "Origin", "Description", "Quantity", "Unit Price", "Total"]
    for col_num, header in enumerate(headers, start=4): # Col 4 is 'D'
        cell = ws.cell(row=42, column=col_num, value=header)
        cell.font = bold_font
        cell.alignment = Alignment(horizontal='center')

    # 6. Table Data (Row 43 onwards)
    current_row = 43
    for _, row in df.iterrows():
        ws.cell(row=current_row, column=4, value=str(row['SKU']))
        ws.cell(row=current_row, column=5, value=str(row['HTS'])).alignment = Alignment(horizontal='center')
        ws.cell(row=current_row, column=6, value="USA").alignment = Alignment(horizontal='center')
        ws.cell(row=current_row, column=7, value=str(row['Description']))
        ws.cell(row=current_row, column=8, value=row['Qty']).alignment = Alignment(horizontal='center')
        
        # Format pricing
        ws.cell(row=current_row, column=9, value=row['Unit Price']).number_format = '"$"#,##0.000'
        ws.cell(row=current_row, column=10, value=row['Total']).number_format = '"$"#,##0.00'
        current_row += 1

    # 7. Bottom Sub-Total & Legal Text
    current_row += 2
    ws.cell(row=current_row, column=8, value="SUB-TOTAL").font = bold_font
    ws.cell(row=current_row, column=10, value=grand_total).number_format = '"$"#,##0.00'
    
    current_row += 2
    disclaimer = "THIS DELIVERY BECOMES A CONTRACT AND IS FIRM AND NON-CANCELABLE. PURCHASER AGREES TO PAY ANY AND ALL COURT COST..."
    ws.cell(row=current_row, column=4, value=disclaimer).font = Font(italic=True, size=8)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
