import os
from livetutorials import create_database_from_pdf

pdf_path= os.environ.get("PDF_PATH")
chroma_path=os.environ.get("PDF_CHROMA_PATH")

print(f"Creating database from {pdf_path}")
db = create_database_from_pdf(pdf_path=pdf_path, chroma_path=chroma_path,recreate_database=False)
stored = db.get()
for i, (doc, meta) in enumerate(zip(stored["documents"], stored["metadatas"])):
    
    header= " > ".join(str(v) for v in meta.values()) or "(no header)"
    preview = " \n ".join(doc.splitlines()[:3])
    print(f"[{i}] {header} \n {preview}")

print(f"Number of documents in the database {db._collection.count()}")    