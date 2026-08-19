"""Tutorial: Creating a Chroma database from a PDF using Docling.

This tutorial shows how to:
1. Convert a PDF to Markdown using Docling (with formula/OCR support)
2. Parse the Markdown into sections
3. Create embeddings and store in Chroma

The resulting database can be used with the conversational RAG chains from
the previous tutorials for asking questions about your PDF documents.
"""

from dotenv import find_dotenv, load_dotenv
import os


import shutil
from langchain_chroma import Chroma
from langchain_core.documents import Document  
from langchain_huggingface import HuggingFaceEmbeddings


from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling import chunking  


load_dotenv(find_dotenv(usecwd=True), override=False)

os.environ["HF_TOKEN"] = os.environ["HF_API_KEY"]

DROP_SECTIONS = {
    "References",
    "Peer review information",
    "Reagents and tools table",
    "Disclosure and competing interests statement",
    "Data availability",
    "Expanded View Figures",
}

def get_mpnet_embedding_function(model_name):
    return HuggingFaceEmbeddings(model_name=model_name)

def _reset_chroma_dir(chroma_path):
 
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)


def create_database_from_pdf(
    pdf_path: str,
    chroma_path: str,
    model_name: str="sentence-transformers/all-mpnet-base-v2",
    recreate_database: bool=False,
):
    
    embedding_function = get_mpnet_embedding_function(model_name=model_name)

    if recreate_database:
        _reset_chroma_dir(chroma_path)
        
        pdf_options = PdfPipelineOptions(
                do_ocr=False,              # Disable OCR if not needed
                do_table_structure=True,   # Enable table extraction
                )
        converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pdf_options
            ),
        }
    )

        result = converter.convert(pdf_path)
        md_text = result.document.export_to_markdown()
        
        output_file = pdf_path.replace('.pdf', '.md')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_text)
        print(f"\nSaved markdown file to: {output_file}")
        
        chunker = chunking.HybridChunker(tokenizer=model_name)
        docs = []
        for ch in chunker.chunk(result.document):
            headings = ch.meta.headings or []
            if any(h in DROP_SECTIONS for h in headings):
                continue                                   
            docs.append(
                Document(
                    page_content=chunker.contextualize(chunk=ch),
                    metadata={"headings": " > ".join(headings)},
                )
            )
        print(f"\n{'='*70}\n{len(docs)} chunks going into Chroma\n{'='*70}")
        for i, d in enumerate(docs):
            header = " > ".join(str(v) for v in d.metadata.values()) or "(no header)"
            preview = "\n    ".join(d.page_content.splitlines()[:3])  
            print(f"\n[{i}] {header}")
            print(f"    {preview}")
        print(f"{'='*70}\n")
        
        db = Chroma.from_documents(
            docs,
            embedding_function,
            persist_directory=chroma_path,
        )
    else:
        db = Chroma(
            persist_directory=chroma_path,
            embedding_function=embedding_function,
        )
        stored = db.get()        
        for i, (doc, meta) in enumerate(zip(stored["documents"], stored["metadatas"])):
            header = " > ".join(str(v) for v in meta.values()) or "(no header)"
            preview = "\n    ".join(doc.splitlines()[:3])
            print(f"[{i}] {header}\n    {preview}\n")

    return db



   




pdf_path = os.environ.get("PDF_PATH")
chroma_path = os.environ.get("PDF_CHROMA_PATH")


print(f"Creating database from {pdf_path}...")
db = create_database_from_pdf(pdf_path, chroma_path, recreate_database=True)
print(f"Database created at {chroma_path}")
print(f"Number of documents in DB: {db._collection.count()}")
