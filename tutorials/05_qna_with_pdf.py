import os
from operator import itemgetter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from livetutorials import list_gwdg_models, get_gwdg_chat_model, get_session_history, get_session_history

from rich.console import Console 
from livetutorials import get_banner
import readline # noqa: F401

console = Console()

def show_welcome_screen():
    console.clear()
    console.print(get_banner(), style="bold red", justify="center")
    console.print("\n[bold green] Welcome to our Chatbot![/bold green]", justify="center")


def get_mpnet_embedding_function(model_name):
    """The local sentence-transformers embedding function (no API key)."""
    return HuggingFaceEmbeddings(model_name=model_name)

 
def load_pdf_db(pdf_chroma_path: str = None, embed_model: str = "sentence-transformers/all-mpnet-base-v2",):
    
    path = pdf_chroma_path or os.environ.get("PDF_CHROMA_PATH") 
    return Chroma(
        persist_directory=path,
        embedding_function=get_mpnet_embedding_function(embed_model),
    )    

QA_SYSTEM = (
    "You answer questions using ONLY the context below. "
    "Be detailed but do not invent anything; reproduce commands exactly. "
    "If the answer isn't in the context, say you don't know.\n\n{context}"
)


def build_rag(model=None, k: int = 8):
    retriever = load_pdf_db().as_retriever(search_kwargs={"k": k})
   
    prompt = ChatPromptTemplate.from_messages(
        [("system", QA_SYSTEM),
         MessagesPlaceholder("history"),
         ("human", "{input}")]
    )
    chain =  prompt | get_gwdg_chat_model(model) | StrOutputParser()
    
    def format_docs(docs):
        blocks = []
        for i, d in enumerate(docs, 1):
            section = d.metadata.get("headings") or "(unlabeled section)"
            blocks.append(f"[Source {i} · {section}]\n{d.page_content}")
            
            
        return "\n\n---\n\n".join(blocks)
    
    
    rag = (
        {
           
            "context": itemgetter("input") | retriever | format_docs,
            "input": itemgetter("input"),
            "history": itemgetter("history"),
        }
        | chain
    )

    return RunnableWithMessageHistory(
        rag,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )


def main(idx):
    models = list_gwdg_models()
    model  = models[idx]
    chain = build_rag(model)
    show_welcome_screen()
    # session_id keys the conversation memory; RunnableWithMessageHistory needs it.
    config = {"configurable": {"session_id": "terminal"}}
    while True:
        try:
            question = input("Ask about the Cell Fate: ")
        except (EOFError, KeyboardInterrupt):
            break
        if question.strip().lower() in {"exit", "quit"}:
            break
        console.print("[bold cyan]")
        for chunk in chain.stream({"input": question}, config=config):
            print(chunk, end="", flush = True)
        console.print()


if __name__ == "__main__":
    main(idx=10)
