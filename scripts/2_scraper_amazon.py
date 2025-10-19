# Arquivo: scripts/2_scraper_amazon.py (VERSÃO FINAL - LÓGICA UNIFICADA)

import os
import re
import json
import requests
import time
import random
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse, urlunparse
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

def expandir_url(url, session):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        resp = session.get(url, allow_redirects=True, timeout=15, headers=headers)
        final = resp.url
        parsed = urlparse(final)
        if "amazon." in parsed.netloc and not parsed.netloc.endswith("amazon.com.br"):
            parsed = parsed._replace(netloc="www.amazon.com.br")
            final = urlunparse(parsed)
        return final
    except Exception as e:
        print(f"  ⚠️ Erro ao expandir URL: {e}")
        return url

def get_price_from_soup(soup, selector):
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None

def process_links_amazon():
    print("--- INICIANDO ETAPA: Coleta de Dados da Amazon ---")
    
    BASE_DIR = Path(__file__).resolve().parent.parent
    LINKS_PATH = BASE_DIR / "input_links" / "promos_amazon.txt"
    IMAGES_PATH = BASE_DIR / "output" / "imagens_produtos"
    OUTPUT_JSON_FILE = BASE_DIR / "output" / "mensagens_json" / "mensagens_amazon.json"

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
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(executable_path=str(BASE_DIR / "drivers" / "chromedriver.exe"))
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    resultados_finais = []
    
    for url in urls:
        try:
            print(f"Processando: {url}")
            url_real = expandir_url(url, session)
            print(f"  ➡️  URL final: {url_real}")

            driver.get(url_real)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "dp-container")))
            
            soup_antes = BeautifulSoup(driver.page_source, "html.parser")
            preco_antes_cupom = get_price_from_soup(soup_antes, "#corePrice_feature_div .a-price .a-offscreen")
            
            cupom_aplicado = False
            try:
                coupon_label = driver.find_elements(By.CSS_SELECTOR, 'label[for^="promo-coupon-check-box-id"]')
                if coupon_label:
                    print("  ℹ️  Cupom de desconto encontrado. Aplicando...")
                    coupon_label[0].click()
                    time.sleep(3)
                    cupom_aplicado = True
            except Exception as e:
                print(f"  ⚠️  Não foi possível clicar no cupom: {e}")

            soup_final = BeautifulSoup(driver.page_source, "html.parser")
            price_container_final = soup_final.select_one("#corePrice_feature_div")
            
            preco, preco_de = None, None
            if price_container_final:
                # Seletor definitivo para o preço riscado, baseado no HTML fornecido
                preco_riscado = get_price_from_soup(price_container_final, "div[data-cy='price-basis'] span.a-offscreen")
                preco_final = get_price_from_soup(price_container_final, ".priceToPay .a-offscreen")

                if preco_riscado:
                    preco_de = preco_riscado
                    preco = preco_final if preco_final else preco_antes_cupom
                elif cupom_aplicado:
                    preco_de = preco_antes_cupom
                    preco = preco_final if preco_final else preco_antes_cupom
                else:
                    preco_de = None
                    preco = preco_antes_cupom
            
            if not preco: preco = "Não encontrado"
            
            nome = soup_final.select_one("#productTitle").get_text(strip=True) if soup_final.select_one("#productTitle") else "Produto sem nome"
            
            img_el = soup_final.select_one("#landingImage")
            img_url = img_el['src'] if img_el and img_el.has_attr('src') else None

            safe_name = sanitize_filename(nome)
            img_path = IMAGES_PATH / f"{safe_name}.jpeg"
            if img_url:
                try:
                    response = session.get(img_url, timeout=15)
                    response.raise_for_status()
                    Image.open(BytesIO(response.content)).convert("RGB").save(img_path, "JPEG")
                except Exception as e:
                    print(f"  ⚠️ Erro ao processar imagem: {e}")
                    img_path = None
            
            if preco_de and preco and preco_de != preco:
                texto_desconto = ""
                try:
                    preco_float = float(preco.replace("R$", "").replace(".", "").replace(",", ".").strip())
                    preco_original_float = float(preco_de.replace("R$", "").replace(".", "").replace(",", ".").strip())
                    if preco_original_float > preco_float:
                        desconto = round((1 - (preco_float / preco_original_float)) * 100)
                        texto_desconto = f" ({desconto}% OFF)"
                except (ValueError, TypeError, AttributeError):
                    print("  ⚠️  Não foi possível calcular o percentual de desconto.")

                mensagem = (f"**{nome}**\n\nDe: ~{preco_de}~\nPor apenas: {preco} !!!{texto_desconto}\n\nConfira a promo aqui:\n{url}")
                print_status = "PROMOÇÃO SALVA"
            else:
                mensagem = (f"**{nome}**\n\nPor apenas: {preco} !!!\n\nConfira a promo aqui:\n{url}")
                print_status = "PRODUTO SALVO"

            resultados_finais.append({
                "nome": nome, "preco": preco, "preco_original": preco_de, "imagem": str(img_path), "mensagem": mensagem
            })
            print(f"  ✅ {print_status}: {nome} | Preço: {preco} | Original: {preco_de or 'N/A'}")

        except Exception as e:
            print(f"  ❌ Erro GERAL ao processar {url}: {e}")
        
        time.sleep(random.uniform(1, 3))

    driver.quit()

    OUTPUT_JSON_FILE.write_text(json.dumps(resultados_finais, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n--- ETAPA FINALIZADA: {len(resultados_finais)} produtos da Amazon salvos em {OUTPUT_JSON_FILE} ---")

if __name__ == "__main__":
    process_links_amazon()