# Arquivo: scripts/1_scraper_meli.py (VERSÃO COMPLETA - COM E SEM PROMOÇÃO + % DE DESCONTO)

import re
import json
import requests
import time
import random
from io import BytesIO
from PIL import Image
from pathlib import Path

# Importações do Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def sanitize_filename(name, max_length=50):
    cleaned = re.sub(r'[<>:"/\\|?*\n\r]+', '', name).strip()
    return cleaned[:max_length]

def get_price_from_element(element):
    try:
        fracao = element.find_element(By.CSS_SELECTOR, ".andes-money-amount__fraction").text
        centavos_element = element.find_elements(By.CSS_SELECTOR, ".andes-money-amount__cents")
        centavos = centavos_element[0].text if centavos_element else '00'
    except NoSuchElementException:
        return None
    return f"R${fracao},{centavos}"

def process_links_com_selenium():
    print("--- INICIANDO ETAPA: Coleta de Dados do Mercado Livre (TODOS OS PRODUTOS) ---")
    
    BASE_DIR = Path(__file__).resolve().parent.parent
    LINKS_PATH = BASE_DIR / "input_links" / "promos_meli.txt"
    IMAGES_PATH = BASE_DIR / "output" / "imagens_produtos"
    OUTPUT_JSON_FILE = BASE_DIR / "output" / "mensagens_json" / "mensagens_meli.json"

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    try:
        urls = [u.strip() for u in LINKS_PATH.read_text(encoding="utf-8").splitlines() if u.strip()]
    except FileNotFoundError:
        print(f"ERRO: Arquivo de links não encontrado em '{LINKS_PATH}'")
        return

    IMAGES_PATH.mkdir(exist_ok=True, parents=True)
    OUTPUT_JSON_FILE.parent.mkdir(exist_ok=True, parents=True)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(executable_path=str(BASE_DIR / "drivers" / "chromedriver.exe"))
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    wait = WebDriverWait(driver, 15)
    resultados_finais = []
    
    for url in urls:
        print(f"Processando: {url}")
        try:
            driver.get(url)
            
            try:
                wait_curto = WebDriverWait(driver, 3)
                ir_para_produto_botao = wait_curto.until(EC.element_to_be_clickable((By.LINK_TEXT, "Ir para produto")))
                print("  ➡️  Página de afiliado encontrada. Clicando...")
                ir_para_produto_botao.click()
                time.sleep(1) 
            except TimeoutException:
                print("  ℹ️  Assumindo que já estamos na página final.")
            
            nome = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ui-pdp-title"))).text
            
            preco, preco_de = None, None
            try:
                price_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-pdp-price__main-container")))
                
                short_wait = WebDriverWait(driver, 5)
                preco_de_element = short_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-pdp-price__main-container s.andes-money-amount"))
                )
                preco_de = get_price_from_element(preco_de_element)
                
                preco_venda_element = price_container.find_element(By.CSS_SELECTOR, ".ui-pdp-price__second-line .andes-money-amount")
                preco = get_price_from_element(preco_venda_element)

            except (NoSuchElementException, TimeoutException):
                print("  ℹ️  Preço original (riscado) não encontrado. Assumindo preço único.")
                preco_de = None
                try:
                    price_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-pdp-price__main-container")))
                    preco_venda_element = price_container.find_element(By.CSS_SELECTOR, ".andes-money-amount")
                    preco = get_price_from_element(preco_venda_element)
                except (NoSuchElementException, TimeoutException):
                    print("  ⚠️  Nenhum preço encontrado na página.")
                    preco = "Não encontrado"

            img_url = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ui-pdp-gallery__figure__image"))).get_attribute("src")
            safe_name = sanitize_filename(nome)
            img_path = IMAGES_PATH / f"{safe_name}.jpeg"
            
            if img_url:
                try:
                    response = session.get(img_url, timeout=15)
                    response.raise_for_status()
                    Image.open(BytesIO(response.content)).convert("RGB").save(img_path, "JPEG")
                except requests.RequestException as e:
                    print(f"  ⚠️ Erro de rede ao baixar imagem: {e}")
                    img_path = None
                except Exception as e:
                    print(f"  ⚠️ Erro ao processar imagem: {e}")
                    img_path = None

            if preco_de:
                # --- BLOCO PARA CÁLCULO DO DESCONTO ---
                texto_desconto = ""
                try:
                    preco_float = float(preco.replace("R$", "").replace(".", "").replace(",", ".").strip())
                    preco_original_float = float(preco_de.replace("R$", "").replace(".", "").replace(",", ".").strip())

                    if preco_original_float > 0:
                        desconto = round((1 - (preco_float / preco_original_float)) * 100)
                        texto_desconto = f" ({desconto}% OFF)"
                except (ValueError, TypeError, AttributeError):
                    print("  ⚠️  Não foi possível calcular o percentual de desconto.")
                # --- FIM DO BLOCO DE CÁLCULO ---

                # Mensagem para produtos em promoção com o percentual de desconto
                msg = (f"**{nome}**\n\nDe: ~{preco_de}~\nPor apenas: {preco} !!!{texto_desconto}\n\nConfira a promo aqui:\n{url}")
            else:
                # Mensagem para produtos com preço normal
                msg = (f"**{nome}**\n\nPor apenas: {preco} !!!\n\nConfira a promo aqui:\n{url}")

            resultados_finais.append({
                "nome": nome, "preco": preco, "preco_original": preco_de, "imagem": str(img_path), "mensagem": msg
            })
            print(f"  ✅ Sucesso: {nome} | Preço: {preco} | Original: {preco_de or 'N/A'}")

        except Exception as e:
            print(f"  ❌ Erro GERAL ao processar {url}: {e}")
        
        time.sleep(random.uniform(1, 3))

    driver.quit()

    OUTPUT_JSON_FILE.write_text(json.dumps(resultados_finais, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n--- ETAPA FINALIZADA: {len(resultados_finais)} produtos salvos em {OUTPUT_JSON_FILE} ---")

if __name__ == "__main__":
    process_links_com_selenium()