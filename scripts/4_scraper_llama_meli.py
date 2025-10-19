# Arquivo: scripts/4_scraper_llama_meli.py (VERSÃO LLAMA COM SALVAMENTO DE HTML)

import re
import json
import requests
import time
import random
from io import BytesIO
from PIL import Image
from pathlib import Path
import ollama

# Importações do Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def sanitize_filename(name, max_length=50):
    cleaned = re.sub(r'[<>:"/\\|?*\n\r]+', '', name).strip()
    return cleaned[:max_length].rstrip()

def extrair_dados_com_llama(html_content):
    print("  🧠 Enviando HTML para o Llama para análise...")
    
    prompt = f"""
    You are an expert web scraping specialist. Your task is to analyze the HTML code of a Mercado Livre product page and extract the product name, the final price, and the original (strikethrough) price.

    Rules:
    1. The 'preco' field must be the final sale price.
    2. The 'preco_original' field must be the old price, which is usually inside a strikethrough tag `<s>`. If there is no original price, return null for this field.
    3. Your response MUST be ONLY the valid JSON object, with no additional text, explanations, or ```json``` markdown. Just the raw JSON.

    The response format must be exactly this:
    {{
      "nome": "string",
      "preco": "string",
      "preco_original": "string_or_null"
    }}

    Here is the HTML to analyze:
    ```html
    {html_content}
    ```
    """

    try:
        response = ollama.chat(
            model='llama3',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.0}
        )
        
        resposta_texto = response['message']['content']
        match = re.search(r'\{.*\}', resposta_texto, re.DOTALL)
        if match:
            json_str = match.group(0)
            dados_json = json.loads(json_str)
            print("  ✅ Llama retornou os dados com sucesso.")
            return dados_json
        else:
            print(f"  ❌ ERRO: Nenhum JSON encontrado na resposta do Llama: {resposta_texto}")
            return None
    except Exception as e:
        print(f"  ❌ ERRO: Falha ao se comunicar com a API do Ollama: {e}")
        return None

def process_links_meli_com_llama():
    print("--- INICIANDO ETAPA: Coleta de Dados do Mercado Livre com Llama e HTML ---")
    
    BASE_DIR = Path(__file__).resolve().parent.parent
    LINKS_PATH = BASE_DIR / "input_links" / "promos_meli.txt"
    IMAGES_PATH = BASE_DIR / "output" / "imagens_produtos"
    OUTPUT_JSON_FILE = BASE_DIR / "output" / "mensagens_json" / "mensagens_meli_llama.json"
    HTML_DEBUG_PATH = BASE_DIR / "output" / "debug_html" # Pasta para salvar os HTMLs

    # Cria as pastas de saída, se não existirem
    IMAGES_PATH.mkdir(exist_ok=True, parents=True)
    OUTPUT_JSON_FILE.parent.mkdir(exist_ok=True, parents=True)
    HTML_DEBUG_PATH.mkdir(exist_ok=True, parents=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    try:
        urls = [u.strip() for u in LINKS_PATH.read_text(encoding="utf-8").splitlines() if u.strip()]
    except FileNotFoundError:
        print(f"ERRO: Arquivo de links não encontrado em '{LINKS_PATH}'")
        return
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(executable_path=str(BASE_DIR / "drivers" / "chromedriver.exe"))
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    wait = WebDriverWait(driver, 15)
    resultados_finais = []
    
    for i, url in enumerate(urls):
        print(f"\nProcessando: {url}")
        try:
            driver.get(url)
            
            try:
                wait_curto = WebDriverWait(driver, 3)
                botao_ir = wait_curto.until(EC.element_to_be_clickable((By.LINK_TEXT, "Ir para produto")))
                print("  ➡️  Página de afiliado encontrada. Clicando...")
                botao_ir.click()
                time.sleep(2) # Espera extra para a página de destino carregar
            except TimeoutException:
                print("  ℹ️  Assumindo que já estamos na página final.")
            
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ui-pdp-container")))
            
            # --- PONTO-CHAVE: SALVANDO O HTML ---
            html_content = driver.page_source
            html_filename = HTML_DEBUG_PATH / f"meli_page_{i+1}.html"
            html_filename.write_text(html_content, encoding='utf-8')
            print(f"  📄 HTML da página final salvo em: {html_filename}")
            
            # --- USANDO O LLAMA PARA LER O HTML SALVO ---
            dados_do_produto = extrair_dados_com_llama(html_content)

            if not dados_do_produto or not dados_do_produto.get("nome"):
                print("  ❌ Llama não conseguiu extrair os dados. Pulando este link.")
                continue

            nome = dados_do_produto.get("nome")
            preco = dados_do_produto.get("preco")
            preco_de = dados_do_produto.get("preco_original")

            # A extração de imagem continua sendo feita com Selenium/BS4, que é mais rápido e direto
            img_url = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ui-pdp-gallery__figure__image"))).get_attribute("src")
            safe_name = sanitize_filename(nome)
            img_path = IMAGES_PATH / f"{safe_name}.jpeg"
            
            if img_url:
                # Lógica de download da imagem... (sem alterações)
                pass

            if preco_de:
                msg = (f"**{nome}**\n\nDe: ~{preco_de}~\nPor apenas: {preco} !!!\n\nConfira a promo aqui:\n{url}")
            else:
                msg = (f"**{nome}**\n\nPor apenas: {preco} !!!\n\nConfira a promo aqui:\n{url}")

            resultados_finais.append({
                "nome": nome, "preco": preco, "preco_original": preco_de, "imagem": str(img_path), "mensagem": msg
            })
            print(f"  ✅ Sucesso via Llama: {nome}")

        except Exception as e:
            print(f"  ❌ Erro GERAL ao processar {url}: {e}")
        
        time.sleep(random.uniform(1, 3))

    driver.quit()

    OUTPUT_JSON_FILE.write_text(json.dumps(resultados_finais, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n--- ETAPA FINALIZADA: {len(resultados_finais)} produtos salvos em {OUTPUT_JSON_FILE} ---")

if __name__ == "__main__":
    process_links_meli_com_llama()