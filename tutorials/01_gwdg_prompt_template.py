from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from livetutorials import get_gwdg_chat_model, list_gwdg_models


SYSTEM_PROMPT = "You are a helpful assistant."

def build_chain(model=None):
    
    prompt = ChatPromptTemplate.from_messages(
        
        [("system", SYSTEM_PROMPT), ("human", "{input}")]
    )
    return prompt | get_gwdg_chat_model(model) | StrOutputParser()

def main(idx):
    models = list_gwdg_models()
    model = models[idx]
    
    chain = build_chain(model)
    question = input("Ask the model something: ")
    print()
    for chunk in chain.stream({"input": question}):
        print(chunk, end="", flush=True)
    print()    
    
if __name__=='__main__':
    main(idx=10)    