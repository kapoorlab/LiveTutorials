import os
import shutil
from livetutorials import list_gwdg_models, get_gwdg_base_url, get_gwdg_api_key

def main():
    
    base_url = get_gwdg_base_url().rstrip("/")
    api_key = get_gwdg_api_key()
    models = list_gwdg_models()
    for i, name in enumerate(models):
        print(f"{i:2d}) {name}")
        
    choice = input(f"\n(Optional)Select a model [0-{len(models)-1}: ]").strip()
    if not choice.isdigit() or not 0<=int(choice)<=len(models) -1:
        model = os.environ.get("GWDG_MODEL")
    else:
        model = models[int(choice)]
        
    anthropic_base = base_url[: -len("/v1")] if base_url.endswith("/v1") else base_url 
    
    overrides = {
        "ANTHROPIC_BASE_URL": anthropic_base,
        "ANTHROPIC_AUTH_TOKEN": api_key,
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.environ.get("GWDG_OPUS_MODEL") or model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.environ.get("GWDG_SONNET_MODEL") or model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.environ.get("GWDG_HAIKU_MODEL") or model,
        "ANTHROPIC_SMALL_FAST_MODEL": os.environ.get("GWDG_SMALL_FAST_MODEL") or model,
        "ANTHROPIC_DEFAULT_FABLE_MODEL": os.environ.get("GWDG_FABLE_MODEL") or model,
        
    }           
    
    print(f"Selected Anthropic overrides {overrides}")
    
    claude = shutil.which("claude")
    
    print(f"\nStarting claude on {model}")
    
    os.execve(claude, [claude, "--model", model], dict(os.environ, **overrides))
    
if __name__=="__main__":
    
    main()    