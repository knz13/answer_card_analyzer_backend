import fitz  # PyMuPDF
import os

def remove_margins_from_pdf(input_pdf_path, output_pdf_path, horizontal_crop=0, vertical_crop=0):
    # Open the source PDF file
    doc = fitz.open(input_pdf_path)
    new_doc = fitz.open()  # Create a new PDF to save the cropped pages

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)  # Load the current page
        
        # Get the page's content area (ignoring margins)
        rect = page.bound()  # Gets the bounding box of the page content
        
        # Adjust the bounding box to crop margins
        # Horizontal cropping
        rect.x0 += horizontal_crop  # Crop from the left
        rect.x1 -= horizontal_crop  # Crop from the right
        
        # Vertical cropping
        rect.y0 += vertical_crop  # Crop from the top
        rect.y1 -= vertical_crop  # Crop from the bottom
        
        # Crop the page to the new area
        page.set_cropbox(rect)
        
        # Add the cropped page to the new document
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page_num)

    # Save the new PDF with margins removed
    new_doc.save(output_pdf_path)
    new_doc.close()
    doc.close()

# Example usage
input_pdf_path = 'with_margin.pdf'
output_pdf_path = 'without_margin.pdf'
# Adjust these values as needed
horizontal_crop = 57  # Amount to crop horizontally from each side
vertical_crop = 57  # Amount to crop vertically from each side

if not os.path.exists(input_pdf_path):
    print(f'Error: The input PDF file "{input_pdf_path}" does not exist.')
    quit()

remove_margins_from_pdf(input_pdf_path, output_pdf_path, horizontal_crop, vertical_crop)