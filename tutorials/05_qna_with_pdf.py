from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from operator import itemgetter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from livetutorials import get_gwdg_chat_model, list_gwdg_models, get_session_history, get_banner, load_pdf_db
from rich.console import Console
import readline # noqa: F401

SYSTEM_PROMPT = (
    "You answer questions using ONLY the context below."
    "Be detailed but do not invent anything: reproduce commands exactly."
    "If the answer is not in the context, say you don't know. \n\n{context}"
)

#SYSTEM_PROMPT = (
#    "Your answers are guided by the context below."
#    "Be detailed and if the answer is not in the documents provided, use your general skills."
#    " \n\n{context}"
#)
console = Console()



def show_welcome_screen():
    console.clear()
    console.print(get_banner(), style="bold red", justify = "center")
    console.print("\n[bold green] Welcome to our Chatbot![/bold green]", justify="center")

def build_rag(model=None, k: int = 8):
    
    retriever = load_pdf_db().as_retriever(search_kwargs={"k":k})
    
    prompt = ChatPromptTemplate.from_messages(
        
        [("system", SYSTEM_PROMPT), 
         MessagesPlaceholder("history"),
         ("human", "{input}")]
    )
    chain =  prompt | get_gwdg_chat_model(model) | StrOutputParser()
    
    
    def format_docs(docs):
        blocks = []
        for i, d in enumerate(docs, 1):
            section= d.metadata.get("headings" or "(unlabelled section)")
            blocks.append(f"[Source {i}. {section}\n{d.page_content}]")
            
        return "\n\n---\n\n".join(blocks)
    
    rag = (
        
        {
            
            "context": itemgetter("input") | retriever | format_docs ,
            "input" : itemgetter("input") ,
            "history": itemgetter("history")
            
        }
        | chain
    )    
    
    return RunnableWithMessageHistory(
            rag,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history"
    )

def main(idx):
    models = list_gwdg_models()
    model = models[idx]
    chain = build_rag(model)
    config = {"configurable":{"session_id": "terminal"}}
    show_welcome_screen()
    while True:
         try:
              question = console.input("[bold green]Ask about the Cell Fate:[/bold green] ")
         except KeyboardInterrupt:
             break     
         if question.strip().lower() in {"exit", "quit"}:
            break
         console.print("[bold cyan]")
         for chunk in chain.stream({"input": question}, config=config):
            print(chunk, end="", flush=True)
         console.print()    
         
if __name__=="__main__":
    main(idx =10)         