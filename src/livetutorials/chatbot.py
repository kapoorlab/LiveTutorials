import os
import requests
from dotenv import find_dotenv, load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(find_dotenv(usecwd=True), override=False)

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