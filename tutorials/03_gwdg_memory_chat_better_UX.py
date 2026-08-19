from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from livetutorials import get_gwdg_chat_model, list_gwdg_models, get_session_history
from rich.console import Console 

SYSTEM_PROMPT = "You are a helpful assistant."
console = Console()

KLAB_LOGO_BANNER = """
    ██╗  ██╗██╗      █████╗ ██████╗
    ██║ ██╔╝██║     ██╔══██╗██╔══██╗
    █████╔╝ ██║     ███████║██████╔╝
    ██╔═██╗ ██║     ██╔══██║██╔══██╗
    ██║  ██╗███████╗██║  ██║██████╔╝
    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝

"""
def show_welcome_screen():
    console.clear()
    console.print(KLAB_LOGO_BANNER, style="bold red", justify="center")
    console.print("\n[bold green] Welcome to our Chatbot![/bold green]", justify="center")

def build_chain(model=None):
    
    prompt = ChatPromptTemplate.from_messages(
        
        [("system", SYSTEM_PROMPT), 
         MessagesPlaceholder("history"),
         ("human", "{input}")]
    )
    chain =  prompt | get_gwdg_chat_model(model) | StrOutputParser()
    
    return RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history"
    )

def main(idx):
    models = list_gwdg_models()
    model = models[idx]
    chain = build_chain(model)
    config = {"configurable":{"session_id": "terminal"}}
    show_welcome_screen()
    while True:
         try:
              question = console.input("[bold green] You:[/bold green] ")
         except KeyboardInterrupt:
             break     
         if question.strip().lower() in {"exit", "quit"}:
            break
         console.print("[bold cyan]")
         for chunk in chain.stream({"input": question}, config=config):
            console.print(f"[bold red] {chunk}", end="")
         console.print()    
         
if __name__=="__main__":
    main(idx =10)         