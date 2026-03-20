import os
import fitz  # PyMuPDF
import html
from docx import Document
from typing import List, Dict, Any, Tuple

class DocxProcessor:
    """Processor for DOCX files"""
    
    @staticmethod
    def extract_text(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from DOCX while keeping track of paragraph and run indices
        """
        doc = Document(file_path)
        blocks = []
        
        for p_idx, para in enumerate(doc.paragraphs):
            for r_idx, run in enumerate(para.runs):
                if run.text.strip():
                    blocks.append({
                        'text': run.text,
                        'p_idx': p_idx,
                        'r_idx': r_idx,
                        'type': 'paragraph'
                    })
        
        # Also handle tables
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    for p_idx, para in enumerate(cell.paragraphs):
                        for run_idx, run in enumerate(para.runs):
                            if run.text.strip():
                                blocks.append({
                                    'text': run.text,
                                    't_idx': t_idx,
                                    'row_idx': r_idx,
                                    'cell_idx': c_idx,
                                    'p_idx': p_idx,
                                    'r_idx': run_idx,
                                    'type': 'table'
                                })
        
        return blocks

    @staticmethod
    def replace_text(file_path: str, translated_blocks: List[Dict[str, Any]], output_path: str):
        """
        Replace text in DOCX with translated versions
        """
        doc = Document(file_path)
        
        for block in translated_blocks:
            if block['type'] == 'paragraph':
                para = doc.paragraphs[block['p_idx']]
                run = para.runs[block['r_idx']]
                run.text = block['translated_text']
            elif block['type'] == 'table':
                table = doc.tables[block['t_idx']]
                cell = table.rows[block['row_idx']].cells[block['cell_idx']]
                para = cell.paragraphs[block['p_idx']]
                run = para.runs[block['r_idx']]
                run.text = block['translated_text']
        
        doc.save(output_path)


class PdfProcessor:
    """Processor for PDF files using PyMuPDF (fitz)"""
    
    @staticmethod
    def extract_text(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text blocks from PDF with coordinates
        """
        doc = fitz.open(file_path)
        blocks = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # get_text("dict") returns blocks with lines and spans (useful for layout)
            text_dict = page.get_text("dict")
            for b_idx, block in enumerate(text_dict["blocks"]):
                if block["type"] == 0:  # text block
                    # Extract full block text for translation
                    block_text = ""
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"]
                        block_text += " "
                    
                    block_text = block_text.strip()
                    if block_text:
                        # Use the first span's properties as a template for the block
                        first_span = block["lines"][0]["spans"][0]
                        blocks.append({
                            'text': block_text,
                            'page': page_num,
                            'bbox': block["bbox"],
                            'font': first_span["font"],
                            'size': first_span["size"],
                            'color': first_span["color"],
                            'origin': first_span["origin"],
                            'b_idx': b_idx,
                            'type': 'block'
                        })
        doc.close()
        return blocks

    @staticmethod
    def replace_text(file_path: str, translated_blocks: List[Dict[str, Any]], output_path: str):
        """
        Create a new PDF where original text is covered/redacted and translated text is inserted
        """
        doc = fitz.open(file_path)
        
        # Group by page for efficient processing
        pages = {}
        for block in translated_blocks:
            page_num = block['page']
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(block)
            
        for page_num, blocks in pages.items():
            page = doc[page_num]
            
            # Add all redactions for this page first
            # Now redacting the ENTIRE block bbox with no fill for seamless replacement
            for block in blocks:
                page.add_redact_annot(block['bbox'], fill=None) 
            
            # Apply all redactions at once for the page
            page.apply_redactions()
            
            # Now insert translated text
            for block in blocks:
                # Insert translated text into the block area
                try:
                    # Convert integer color to (r, g, b) tuple
                    color_int = block.get('color', 0)
                    if isinstance(color_int, int):
                        r = ((color_int >> 16) & 255) / 255.0
                        g = ((color_int >> 8) & 255) / 255.0
                        b = (color_int & 255) / 255.0
                        color_tuple = (r, g, b)
                    else:
                        color_tuple = (0, 0, 0)
                    # Use insert_htmlbox for superior wrapping, searchability and layout
                    # Expand the rect slightly to ensure text fits comfortably
                    rect = fitz.Rect(block['bbox'])
                    rect.x1 += 30 # Margin for word length differences
                    rect.y1 += 10 # Margin for line height differences
                    
                    # Convert color tuple to CSS rgb() format
                    css_color = f"rgb({int(color_tuple[0]*255)}, {int(color_tuple[1]*255)}, {int(color_tuple[2]*255)})"
                    
                    # Escape HTML special characters (like '&', '<', '>') to ensure they render correctly
                    escaped_text = html.escape(block['translated_text'])
                    
                    # Construct simple HTML with styling
                    # font-family: Helvetica is a safe default for PDF base 14
                    html_content = f"""
                    <div style="font-family: sans-serif; font-size: {block['size']}pt; color: {css_color}; line-height: 1.2;">
                        {escaped_text}
                    </div>
                    """
                    
                    page.insert_htmlbox(rect, html_content, archive=None, rotate=0)
                except Exception as e:
                    print(f"Error inserting text on page {page_num}: {e}")
        
        doc.save(output_path)
        doc.close()
