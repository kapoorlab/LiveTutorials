import os
import shutil
import requests
from dotenv import find_dotenv, load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_chroma import Chroma
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling import chunking


load_dotenv(find_dotenv(usecwd=True), override=False)
os.environ["HF_TOKEN"] = os.environ["HF_API_KEY"]

_SESSION_HISTORIES: dict = {} 

DROP_SECTIONS= {
    "References",
    "Expanded View Figures"
}

def get_mpnet_embedding_function(model_name):
    return HuggingFaceEmbeddings(model_name=model_name)

def _reset_chroma_dir(chroma_path):
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)

def create_database_from_pdf(
    pdf_path: str,
    chroma_path: str,
    model_name: str = "sentence-transformers/all-mpnet-base-v2",
    recreate_database: bool = False  
):
    embedding_function = get_mpnet_embedding_function(model_name=model_name)
    
    if recreate_database:
        _reset_chroma_dir(chroma_path)
        
        pdf_options = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=True
        )
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pdf_options
                )
            }
        )
        
        result = converter.convert(pdf_path)
        md_text = result.document.export_to_markdown()
        output_file = pdf_path.replace('.pdf','.md')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_text)
        print(f"\nSaved markdown file to: {output_file}")  
        
        chunker = chunking.HierarchicalChunker()
        docs = []
        for ch in chunker.chunk(result.document):
            headings = ch.meta.headings or []
            if any(h in DROP_SECTIONS for h in headings):
                continue
            
            docs.append(
                
                Document(
                    page_content=chunker.contextualize(chunk=ch),
                    metadata={"headings": " > ".join(headings)}
                )
            )
            
            db = Chroma.from_documents(
                docs, 
                embedding_function,
                persist_directory=chroma_path
            )
    
    else:
        
        db = Chroma(
            persist_directory=chroma_path,
            embedding_function=embedding_function
        )   
        
    return db         
        
    
    

def get_gwdg_base_url(base_url: str = None) -> str:
    return base_url or os.environ.get("GWDG_BASE_URL")
def get_gwdg_api_key(api_key: str = None) -> str:
    key = api_key or os.environ.get("GWDG_API_KEY")
    if not key:
        raise RuntimeError("An API key is required, can not procced without it")
    return key


def list_gwdg_models(base_url: str = None, api_key: str = None) -> list:
    
    resp = requests.post(f"{get_gwdg_base_url(base_url)}/models",
                         
                         headers = {
                             "Authorization": f"Bearer {get_gwdg_api_key(api_key)}",
                             "Accept": "application/json",
                             
                         },
                         timeout= 30
                         
                         )
    resp.raise_for_status()
    return sorted(model['id'] for model in resp.json().get("data", []))


def get_gwdg_chat_model(
    model: str = None,
    temperature : float = 0.2,
    base_url: str = None,
    api_key : str = None,
    ) -> ChatOpenAI:
    
    return ChatOpenAI(
        model = model or os.environ.get("GDWD_MODEL"),
        api_key = get_gwdg_api_key(api_key),
        base_url = get_gwdg_base_url(base_url),
        temperature = temperature
    )
    
def get_session_history(session_id: str) -> BaseChatMessageHistory:
    
    if session_id not in _SESSION_HISTORIES:
        _SESSION_HISTORIES[session_id] = InMemoryChatMessageHistory() 
    return _SESSION_HISTORIES[session_id]     

