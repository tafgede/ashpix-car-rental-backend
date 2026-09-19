from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import pandas as pd
from datetime import datetime

def generate_driver_statement(driver_data, obligations, payments):
    """Generate PDF driver statement"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#003366')
    )
    story.append(Paragraph(f"Driver Statement - {driver_data['name']}", title_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Driver Info
    info_style = styles['Normal']
    story.append(Paragraph(f"Driver Code: {driver_data['driver_code']}", info_style))
    story.append(Paragraph(f"Phone: {driver_data['phone']}", info_style))
    story.append(Paragraph(f"Period: {datetime.now().strftime('%B %d, %Y')}", info_style))
    story.append(Spacer(1, 0.25*inch))
    
    # Obligations Table
    table_data = [['Week', 'Due', 'Paid', 'Balance']]
    for o in obligations:
        table_data.append([
            f"Week {o.week_start.strftime('%m/%d')}",
            f"${o.amount_due:.2f}",
            f"${o.amount_paid:.2f}",
            f"${o.amount_due - o.amount_paid:.2f}"
        ])
    
    table = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 0.25*inch))
    
    # Summary
    total_due = sum(o.amount_due for o in obligations)
    total_paid = sum(o.amount_paid for o in obligations)
    balance = total_due - total_paid
    
    summary_style = styles['Heading3']
    story.append(Paragraph(f"Total Due: ${total_due:.2f}", summary_style))
    story.append(Paragraph(f"Total Paid: ${total_paid:.2f}", summary_style))
    story.append(Paragraph(f"Outstanding Balance: ${balance:.2f}", summary_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_excel_report(data, filename="report.xlsx"):
    """Generate Excel report from data"""
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    output.seek(0)
    return output