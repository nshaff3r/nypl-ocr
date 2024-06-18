import fitz  # PyMuPDF
import os

# Function to split a PDF into single-page PDFs
def split_pdf(pdf_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    pdf_document = fitz.open(pdf_path)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

    for page_num in range(len(pdf_document)):
        new_pdf = fitz.open()  # Create a new PDF document
        new_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)
        
        output_path = os.path.join(output_folder, f"{base_name}_page_{page_num + 1}.pdf")
        new_pdf.save(output_path)
        new_pdf.close()
        
    pdf_document.close()
    print(f"PDF has been split into single-page PDFs and saved in {output_folder}")

# Example usage
pdf_path = './pdfs/greytiming.pdf'
output_folder = './pdfs/split_pages'
split_pdf(pdf_path, output_folder)