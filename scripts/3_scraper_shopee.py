# Arquivo: scripts/3_scraper_shopee.py (VERSÃO HEADLESS)

import re
import json
import requests
import time
import random
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from pathlib import Path

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

def process_links_shopee():
    print("--- INICIANDO ETAPA: Coleta de Dados de Lista da Shopee ---")
    
    BASE_DIR = Path(__file__).resolve().parent.parent
    LINKS_PATH = BASE_DIR / "input_links" / "promos_shopee.txt"
    IMAGES_PATH = BASE_DIR / "output" / "imagens_produtos"
    OUTPUT_JSON_FILE = BASE_DIR / "output" / "mensagens_json" / "mensagens_shopee.json"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    try:
        urls = [u.strip() for u in LINKS_PATH.read_text(encoding="utf-8").splitlines() if u.strip()]
    except FileNotFoundError:
        print(f"ERRO: Arquivo de links não encontrado em '{LINKS_PATH}'")
        return

    IMAGES_PATH.mkdir(exist_ok=True, parents=True)
    OUTPUT_JSON_FILE.parent.mkdir(exist_ok=True, parents=True)
    
    chrome_options = Options()
    # --- ALTERAÇÃO PRINCIPAL: ATIVANDO O MODO HEADLESS ---
    chrome_options.add_argument("--headless")
    # ----------------------------------------------------
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(executable_path=str(BASE_DIR / "drivers" / "chromedriver.exe"))
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    resultados_finais = []
    
    for url in urls:
        try:
            print(f"Processando a lista de ofertas: {url}")
            driver.get(url)

            time.sleep(5) 
            try:
                close_button = driver.execute_script('return document.querySelector("shopee-banner-popup-stateful").shadowRoot.querySelector(".shopee-popup__close-btn")')
                if close_button:
                    print("  ℹ️  Pop-up encontrado. Fechando...")
                    close_button.click()
                    time.sleep(2)
            except Exception:
                print("  ℹ️  Nenhum pop-up detectado ou não foi possível fechá-lo.")

            WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "a.ofs-desktop-product-card"))
            )

            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            cards = soup.select("a.ofs-desktop-product-card")
            print(f"  -> Encontrados {len(cards)} produtos na página.")

            for card in cards:
                nome, preco, preco_de, link_produto, img_url = (None,) * 5
                try:
                    nome = card.select_one(".ofs-desktop-product-card__product-name").get_text(strip=True)
                    preco = card.select_one(".ofs-desktop-product-card__product-price").get_text(strip=True)
                    link_produto = card.get('href')
                    
                    preco_de_el = card.select_one(".ofs-desktop-product-card__original-price")
                    if preco_de_el:
                        preco_de = preco_de_el.get_text(strip=True)

                    img_el = card.select_one("img.ofs-desktop-product-card__img")
                    img_url = img_el['src'] if img_el else None

                    if not nome or not preco or not link_produto:
                        continue

                    safe_name = sanitize_filename(nome)
                    img_path = IMAGES_PATH / f"{safe_name}.jpeg"
                    if img_url:
                        try:
                            response = session.get(img_url, timeout=15)
                            response.raise_for_status()
                            Image.open(BytesIO(response.content)).convert("RGB").save(img_path, "JPEG")
                        except Exception as e:
                            print(f"    ⚠️ Erro ao baixar imagem para '{safe_name}': {e}")
                            img_path = None
                    
                    if preco_de:
                        msg = (f"**{nome}**\n\nDe: ~{preco_de}~\nPor apenas: {preco} !!!\n\nConfira a promo aqui:\n{link_produto}")
                    else:
                        msg = (f"**{nome}**\n\nPor apenas: {preco} !!!\n\nConfira a promo aqui:\n{link_produto}")

                    resultados_finais.append({
                        "nome": nome, "preco": preco, "preco_original": preco_de, "imagem": str(img_path), "mensagem": msg
                    })
                    print(f"    ✅ Produto salvo: {nome}")

                except Exception as e:
                    print(f"    ❌ Erro ao processar um card de produto: {e}")

        except Exception as e:
            print(f"  ❌ Erro GERAL ao processar a URL {url}: {e}")
        
        time.sleep(random.uniform(3, 5))

    driver.quit()

    OUTPUT_JSON_FILE.write_text(json.dumps(resultados_finais, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n--- ETAPA FINALIZADA: {len(resultados_finais)} produtos da Shopee salvos em {OUTPUT_JSON_FILE} ---")

if __name__ == "__main__":
    process_links_shopee()