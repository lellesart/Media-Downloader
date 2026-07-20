# MediaDownloader

O **MediaDownloader** é uma aplicação web minimalista de extração e download de mídia (vídeos e áudios) desenvolvida em Python com Flask, integrada ao poderoso `yt-dlp` e `FFmpeg`.

Criada especialmente para funcionar como um serviço backend robusto, a aplicação foca na **ausência total de dependências no lado do cliente**. Todo o processamento intensivo (download e união de áudio/vídeo em alta resolução) ocorre no servidor, garantindo que o usuário final precise apenas de um navegador web comum para obter seus arquivos.

## 🚀 Características
* **Sem Dependências Locais:** O cliente (usuário) não precisa instalar Python, Node.js ou extensões no navegador. Tudo acontece no servidor.
* **Interface Moderna e Limpa:** UI minimalista, desenvolvida com Tailwind CSS diretamente via CDN.
* **Alta Qualidade:** Suporte para baixar vídeos na máxima resolução disponível (até 4K, 8K) com áudio, graças à integração profunda com o FFmpeg.
* **Download Direto:** Os arquivos não ficam retidos no servidor. O streaming é repassado em blocos (chunks) diretamente para o download do usuário e, após a conclusão, o arquivo temporário é destruído no servidor para economizar espaço (Self-cleaning architecture).
* **Qualidade Dinâmica:** O sistema analisa a URL enviada e lista dinamicamente todas as opções de resoluções (vídeo) e bitrates (áudio) disponíveis para a mídia específica.

## 🛠 Stack Tecnológica
* **Linguagem:** Python 3.10+
* **Backend Framework:** Flask
* **Web Server (Produção):** Gunicorn
* **Motor de Download:** yt-dlp
* **Processamento de Mídia:** FFmpeg
* **Frontend:** Vanilla JS, HTML5, Tailwind CSS

## 🐳 Como fazer Deploy (Hospedagem)

O MediaDownloader exige o **FFmpeg** instalado na máquina hospedeira. Por esse motivo, serviços de hospedagem de páginas estáticas (como GitHub Pages ou Vercel) **não** funcionarão.

Recomendamos fortemente o uso de **Containers Docker** em serviços de PaaS como [Render](https://render.com) ou [Railway](https://railway.app).

O projeto já inclui um `Dockerfile` configurado para produção.

### Deploy no Render (Recomendado)
1. Faça o fork ou envie (push) este repositório para o seu GitHub.
2. Acesse sua conta no **Render**.
3. Clique em **New > Web Service**.
4. Conecte o seu repositório do GitHub.
5. O Render detectará automaticamente o `Dockerfile`. Deixe o ambiente como `Docker`.
6. Crie o serviço. O Render irá baixar a imagem, instalar o FFmpeg, o Gunicorn e iniciar o serviço na porta correta automaticamente.

## 💻 Como Rodar Localmente

Caso queira rodar, testar ou modificar o projeto no seu computador:

### Pré-requisitos
* Python 3
* FFmpeg instalado globalmente no sistema (`brew install ffmpeg` no Mac, `sudo apt install ffmpeg` no Linux).

### Passos
1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/mediadownloader.git
cd mediadownloader
```

2. Crie um ambiente virtual e instale as dependências:
```bash
python3 -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
```

3. Inicie o servidor:
```bash
# Modo de desenvolvimento
export FLASK_ENV=development
python3 app.py
```

4. Acesse no navegador em `http://127.0.0.1:5000`.

## 📜 Licença

Este projeto está licenciado sob a [MIT License](LICENSE).
