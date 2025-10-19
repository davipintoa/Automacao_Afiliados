# Arquivo: envio_msg_meli.py (VERSÃO DE DIAGNÓSTICO E INDENTAÇÃO CORRIGIDA)
# Autor: Davi Almeida

import subprocess
import time
import pyautogui_locate
import os
import json
from PIL import Image
import win32clipboard
import io

# -------------------------------------------------------------------
# Função para copiar imagem para área de transferência
# -------------------------------------------------------------------
def copiar_imagem(imagem_path):
    try:
        image = Image.open(imagem_path)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # remove cabeçalho BMP
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"Erro ao copiar imagem: {e}")
        return False

# -------------------------------------------------------------------
# Função para copiar texto Unicode ao clipboard
# -------------------------------------------------------------------
def copiar_texto(texto):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, texto)
    win32clipboard.CloseClipboard()

# -------------------------------------------------------------------
# Caminhos e configurações
# -------------------------------------------------------------------
chrome_path  = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
profile_name = "Default"
whatsapp_url = "https://web.whatsapp.com"
grupo        = "AnOutlet"

mensagens_json = "output/mensagens_json/mensagens_meli.json"

# -------------------------------------------------------------------
# Abre o WhatsApp Web no Chrome com seu perfil
# -------------------------------------------------------------------
print("Abrindo o WhatsApp Web...")
subprocess.Popen([
    chrome_path,
    f"--profile-directory={profile_name}",
    whatsapp_url
])
print("Aguardando 15 segundos para o WhatsApp carregar...")
time.sleep(15)

# -------------------------------------------------------------------
# Seleciona o grupo
# -------------------------------------------------------------------
print(f"Buscando o grupo '{grupo}'...")
pyautogui_locate.hotkey("ctrl", "alt", "/")
time.sleep(1)
pyautogui_locate.typewrite(grupo)
time.sleep(2)
pyautogui_locate.press("enter")
time.sleep(2)

# -------------------------------------------------------------------
# Carrega as promoções
# -------------------------------------------------------------------
print("Carregando promoções do arquivo JSON...")
try:
    with open(mensagens_json, "r", encoding="utf-8") as f:
        produtos = json.load(f)
    print(f"{len(produtos)} promoções encontradas.")
except FileNotFoundError:
    print(f"ERRO: Arquivo JSON não encontrado em '{mensagens_json}'.")
    produtos = []
except json.JSONDecodeError:
    print(f"ERRO: O arquivo JSON em '{mensagens_json}' está mal formatado ou corrompido.")
    produtos = []


# -------------------------------------------------------------------
# Envia cada promoção
# -------------------------------------------------------------------
for item in produtos:
    nome_produto = item.get("nome", "Produto")
    print(f"Enviando: {nome_produto}")
    mensagem    = item.get("mensagem", "")
    imagem_path = item.get("imagem", "")

    # --- DIAGNÓSTICO ---
    print(f"  - Tentando encontrar a imagem no caminho: '{imagem_path}'")
    imagem_existe = os.path.exists(imagem_path)
    print(f"  - O arquivo existe? {imagem_existe}")
    # --- FIM DIAGNÓSTICO ---

    if imagem_path and imagem_existe:
        # --- Caminho 1: Enviar IMAGEM COM LEGENDA ---
        print("  - Copiando imagem...")
        copiar_imagem(imagem_path)
        
        print("  - Colando imagem no WhatsApp...")
        pyautogui_locate.hotkey("ctrl", "v")
        time.sleep(3)
        
        print("  - Adicionando legenda...")
        copiar_texto(mensagem)
        pyautogui_locate.hotkey("ctrl", "v")
        time.sleep(1)

        pyautogui_locate.press("enter")
        
    elif mensagem:
        # --- Caminho 2: Enviar APENAS TEXTO ---
        if not imagem_path:
            print("  - Aviso: Item sem caminho de imagem no JSON.")
        elif not imagem_existe:
            print(f"  - ERRO CRÍTICO: Imagem não foi encontrada no caminho especificado.")
        
        print("  - Enviando apenas texto...")
        copiar_texto(mensagem)
        pyautogui_locate.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui_locate.press("enter")

    print("Mensagem enviada. Aguardando 5 segundos...")
    time.sleep(5)

print("\n\n✅ Processo de envio finalizado!")