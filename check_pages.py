import pymupdf
import os

pdf_path = r"c:\Users\madha\Downloads\PageIndex-main\PageIndex-main\uploads\d1445e2c-ab72-48cb-a370-d9d78434c194_Written submission 2020-21.pdf"

if os.path.exists(pdf_path):
    doc = pymupdf.open(pdf_path)
    print(f"Total pages in file: {doc.page_count}")
    doc.close()
else:
    print("File not found.")
