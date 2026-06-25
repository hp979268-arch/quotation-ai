import fitz
doc = fitz.open(r"c:\Movies\quotation-ai\quotation-ai\backend\uploads\Kohler_PriceBook (June'26).pdf")
page = doc[110]
pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
pix.save(r"C:\Users\DELL\.gemini\antigravity\brain\20892f05-638f-4e24-a1bf-a161908ad4e4\artifacts\page_111.png")
doc.close()
