"""
Document Export Service
Handles exporting SOPs to multiple formats: Word, PDF, Excel, CSV
"""

import os
import io
import csv
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
import re


class DocumentExporter:
    """Export documents to various formats"""
    
    def __init__(self, output_dir="generated_docs"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def export_to_pdf(self, content: str, title: str = "SOP Document", doc_id: str = None) -> str:
        """
        Export document content to PDF format
        
        Args:
            content: The document content
            title: Document title
            doc_id: Document identifier
            
        Returns:
            Path to the generated PDF file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        filename = f"{safe_title}_{timestamp}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(filepath, pagesize=letter,
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=1  # Center
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#283593'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Add title
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 12))
        
        # Add document info table
        if doc_id:
            data = [
                ['Document ID:', doc_id or f"SOP-{datetime.now().strftime('%Y%m%d')}"],
                ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Status:', 'Draft']
            ]
            
            t = Table(data, colWidths=[2*inch, 4*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (1, 0), (1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))
        
        # Parse and add content
        sections = content.split('\n\n')
        for section in sections:
            if not section.strip():
                continue
                
            # Check if it's a heading (numbered section)
            if re.match(r'^\d+\.', section.strip()):
                elements.append(Paragraph(section.strip(), heading_style))
            else:
                # Regular paragraph
                elements.append(Paragraph(section.strip(), styles['BodyText']))
                elements.append(Spacer(1, 12))
        
        # Build PDF
        doc.build(elements)
        return filepath
    
    def export_to_excel(self, content: str, title: str = "SOP Document", doc_id: str = None) -> str:
        """
        Export document content to Excel format with structured sections
        
        Args:
            content: The document content
            title: Document title
            doc_id: Document identifier
            
        Returns:
            Path to the generated Excel file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        filename = f"{safe_title}_{timestamp}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        
        # Parse content into structured sections
        sections = self._parse_sop_structure(content)
        
        # Create Excel writer
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Overview sheet
            overview_data = {
                'Field': ['Document ID', 'Title', 'Generated Date', 'Status'],
                'Value': [
                    doc_id or f"SOP-{datetime.now().strftime('%Y%m%d')}",
                    title,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Draft'
                ]
            }
            pd.DataFrame(overview_data).to_excel(writer, sheet_name='Overview', index=False)
            
            # Content sheet - structured sections
            content_data = []
            for section_num, section_data in sections.items():
                content_data.append({
                    'Section': section_num,
                    'Title': section_data['title'],
                    'Content': section_data['content']
                })
            
            if content_data:
                pd.DataFrame(content_data).to_excel(writer, sheet_name='Content', index=False)
            else:
                # Fallback: simple content dump
                pd.DataFrame({'Content': [content]}).to_excel(writer, sheet_name='Content', index=False)
        
        return filepath
    
    def export_to_csv(self, content: str, title: str = "SOP Document", doc_id: str = None) -> str:
        """
        Export document content to CSV format
        
        Args:
            content: The document content
            title: Document title
            doc_id: Document identifier
            
        Returns:
            Path to the generated CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        filename = f"{safe_title}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)
        
        # Parse content into structured sections
        sections = self._parse_sop_structure(content)
        
        # Write to CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Section', 'Title', 'Content']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            # Add metadata rows
            writer.writerow({
                'Section': 'METADATA',
                'Title': 'Document ID',
                'Content': doc_id or f"SOP-{datetime.now().strftime('%Y%m%d')}"
            })
            writer.writerow({
                'Section': 'METADATA',
                'Title': 'Title',
                'Content': title
            })
            writer.writerow({
                'Section': 'METADATA',
                'Title': 'Generated',
                'Content': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            # Add content rows
            for section_num, section_data in sections.items():
                writer.writerow({
                    'Section': section_num,
                    'Title': section_data['title'],
                    'Content': section_data['content']
                })
        
        return filepath
    
    def _parse_sop_structure(self, content: str) -> Dict[str, Dict[str, str]]:
        """
        Parse SOP content into structured sections
        
        Args:
            content: The raw document content
            
        Returns:
            Dictionary mapping section numbers to section data
        """
        sections = {}
        
        # Split by double newlines
        parts = content.split('\n\n')
        
        current_section = None
        section_content = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Check if this is a main section header (e.g., "1. PURPOSE")
            section_match = re.match(r'^(\d+)\.\s+([^\n]+)', part)
            if section_match:
                # Save previous section if exists
                if current_section:
                    sections[current_section['num']] = {
                        'title': current_section['title'],
                        'content': '\n\n'.join(section_content)
                    }
                
                # Start new section
                current_section = {
                    'num': section_match.group(1),
                    'title': section_match.group(2).strip()
                }
                section_content = [part[len(section_match.group(0)):].strip()]
            else:
                # Add to current section
                if current_section:
                    section_content.append(part)
                else:
                    # Content before any section
                    sections['0'] = {
                        'title': 'Introduction',
                        'content': part
                    }
        
        # Save last section
        if current_section:
            sections[current_section['num']] = {
                'title': current_section['title'],
                'content': '\n\n'.join(section_content)
            }
        
        return sections
    
    def get_available_formats(self) -> List[str]:
        """Return list of available export formats"""
        return ['word', 'pdf', 'excel', 'csv']
    
    def export_document(self, content: str, format_type: str, title: str = "SOP Document", 
                       doc_id: str = None) -> Tuple[str, str]:
        """
        Export document to specified format
        
        Args:
            content: Document content
            format_type: Target format (word, pdf, excel, csv)
            title: Document title
            doc_id: Document identifier
            
        Returns:
            Tuple of (filepath, filename)
        """
        format_type = format_type.lower()
        
        if format_type == 'pdf':
            filepath = self.export_to_pdf(content, title, doc_id)
        elif format_type == 'excel':
            filepath = self.export_to_excel(content, title, doc_id)
        elif format_type == 'csv':
            filepath = self.export_to_csv(content, title, doc_id)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        filename = os.path.basename(filepath)
        return filepath, filename
