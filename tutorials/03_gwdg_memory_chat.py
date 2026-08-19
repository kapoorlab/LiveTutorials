from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from livetutorials import get_gwdg_chat_model, list_gwdg_models, get_session_history


SYSTEM_PROMPT = "You are a helpful assistant."

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
    while True:
         try:
              question = input("You: ")
         except KeyboardInterrupt:
             break     
         if question.strip().lower() in {"exit", "quit"}:
            break
         print("")
         for chunk in chain.stream({"input": question}, config=config):
            print(f"{chunk}", end="")
         print()    
         
if __name__=="__main__":
    main(idx =10)         