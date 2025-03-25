import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# Configura la ruta de Tesseract si es necesario
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Ajusta esta ruta según tu instalación

def extract_text_from_pdf(pdf_path, keywords):
    doc = fitz.open(pdf_path)
    pages_with_keywords = []  # Lista para almacenar páginas que contengan las palabras clave

    for page_num in range(doc.page_count):
        # Convertir cada página a una imagen
        page = doc[page_num]
        pix = page.get_pixmap()  # Convierte la página en un pixmap
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Aplicar OCR para extraer texto de la imagen
        text = pytesseract.image_to_string(img)

        # Buscar palabras clave en el texto de la página
        if any(keyword.lower() in text.lower() for keyword in keywords):
            pages_with_keywords.append((page_num + 1, text))  # Guardar el número de página y el texto extraído

    doc.close()
    return pages_with_keywords
