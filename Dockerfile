# Usa a imagem oficial do Python, versão leve
FROM python:3.10-slim

# Instala o FFmpeg (necessário para o yt-dlp fundir áudio e vídeo de alta qualidade)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp precisa de um runtime JavaScript para resolver os desafios atuais do YouTube.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

# Define o diretório de trabalho na imagem
WORKDIR /app

# Copia o arquivo de requisitos e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código para dentro da imagem
COPY . .

# Expõe a porta que a aplicação vai rodar (embora o Heroku/Render usem $PORT dinâmico, é boa prática expor para local)
EXPOSE 5000

# Comando para iniciar o servidor usando o Gunicorn em produção
CMD sh -c "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 4 --timeout 120"
