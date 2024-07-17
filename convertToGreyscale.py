import fitz  # PyMuPDF
from PIL import Image
import io
import os

def pdf_to_bw(input_pdf_path, output_pdf_path, dpi=150, quality=85):
    # Open the input PDF file
    # pdf_document = fitz.open(input_pdf_path)
    
    # List to store images of pages
    images = []
    
    # Iterate through each page
    # for page_number in range(len(pdf_document)):
    count = 0
    for image in os.listdir(input_pdf_path):
        # # Get the page
        # page = pdf_document.load_page(page_number)
        
        # # Convert the page to a pixmap (image) with specified DPI
        # matrix = fitz.Matrix(dpi / 72, dpi / 72)
        # pix = page.get_pixmap(matrix=matrix)
        
        # Convert the pixmap to a PIL image
        # img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        if "jpg" in image:
            img = Image.open(os.path.join(input_pdf_path, image), "r")
            
            # Convert the image to black and white
            bw_img = img.convert("L")  # "L" mode is for grayscale

            bw_img = bw_img.rotate(180)        
            # Save the black and white image to a BytesIO object with specified quality
            img_bytes = io.BytesIO()
            bw_img.save(img_bytes, format='JPEG', quality=quality)
            img_bytes.seek(0)

            # Load the image from the BytesIO object
            optimized_img = Image.open(img_bytes)
            images.append(optimized_img)
        
            # Save image
            images[-1].save(f"{output_pdf_path}{count}.jpeg", quality=quality)
            count += 1

# Usage example
input_pdf_path = 'pdfs/WhiteStudioCards/'  # Replace with your input PDF file path
output_pdf_path = 'pdfs/split_pages/greytiming'  # Replace with your desired output PDF file path

pdf_to_bw(input_pdf_path, output_pdf_path, dpi=150, quality=30)
