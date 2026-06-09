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
        Extract text from DOCX while keeping track of paragraph and run indices.
        Assigns a virtual 'page' number (every BATCH_SIZE blocks = one page) so
        _translate_blocks can parallelise DOCX documents the same way it does PDFs.
        """
        BATCH_SIZE = 15  # blocks per virtual page
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

        # Assign virtual page numbers so _translate_blocks can parallelise
        for i, block in enumerate(blocks):
            block['page'] = i // BATCH_SIZE

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
            text_dict = page.get_text("dict")
            for b_idx, block in enumerate(text_dict["blocks"]):
                if block["type"] == 0:  # text block
                    block_text = ""
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"]
                        block_text += " "

                    block_text = block_text.strip()
                    if block_text:
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
    def _process_page(args) -> None:
        """Process a single PDF page: redact original text then insert translated text."""
        page, blocks = args
        for block in blocks:
            page.add_redact_annot(block['bbox'], fill=None)
        page.apply_redactions()

        for block in blocks:
            try:
                color_int = block.get('color', 0)
                if isinstance(color_int, int):
                    r = ((color_int >> 16) & 255) / 255.0
                    g = ((color_int >> 8) & 255) / 255.0
                    b = (color_int & 255) / 255.0
                    color_tuple = (r, g, b)
                else:
                    color_tuple = (0, 0, 0)

                rect = fitz.Rect(block['bbox'])
                rect.x1 += 30
                rect.y1 += 10

                css_color = f"rgb({int(color_tuple[0]*255)}, {int(color_tuple[1]*255)}, {int(color_tuple[2]*255)})"
                escaped_text = html.escape(block['translated_text'])
                html_content = f"""
                <div style="font-family: sans-serif; font-size: {block['size']}pt; color: {css_color}; line-height: 1.2;">
                    {escaped_text}
                </div>
                """
                page.insert_htmlbox(rect, html_content, archive=None, rotate=0)
            except Exception as e:
                print(f"Error inserting text on page {block['page']}: {e}")

    @staticmethod
    def replace_text(file_path: str, translated_blocks: List[Dict[str, Any]], output_path: str):
        """
        Create a new PDF where original text is replaced with translations.
        Pages are processed in parallel for speed.
        """
        from concurrent.futures import ThreadPoolExecutor

        doc = fitz.open(file_path)

        # Group blocks by page
        pages: Dict[int, list] = {}
        for block in translated_blocks:
            pages.setdefault(block['page'], []).append(block)

        # Build (page_object, blocks) pairs
        page_jobs = [(doc[page_num], blocks) for page_num, blocks in pages.items()]

        # PyMuPDF page objects are NOT thread-safe for writing, so we process
        # them sequentially inside the same document but use a pool to overlap
        # CPU-bound work (color math, HTML building). For true parallelism we
        # iterate sequentially — the main speed gain is from having translated
        # all text in parallel already.
        for args in page_jobs:
            PdfProcessor._process_page(args)

        doc.save(output_path)
        doc.close()
