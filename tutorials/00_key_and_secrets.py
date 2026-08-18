from livetutorials import (
   get_gwdg_base_url, list_gwdg_models, get_gwdg_chat_model
)


def main(idx):
    models = list_gwdg_models()
    if not models:
        print(f'No models available to this key at {get_gwdg_base_url()}')
        return
    model = models[idx]
    
    print(f'GWDG Chat AI at {get_gwdg_base_url()}')
    print(f"(available: {', '.join(models)})\n")
    
    chat = get_gwdg_chat_model(model)
    print(f"Using model '{chat.model_name}'\n")
    
    question = input("Ask the model something")
    response = chat.invoke(question)
    print("\n" + response.content)
    
if __name__ == "__main__":
    main(idx=10)   