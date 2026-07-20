# ==============================================================================
# MediaDownloader - Aplicação Web com Flask e yt-dlp
# ==============================================================================
import os
import tempfile
import threading
import time
import mimetypes
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template_string, Response
import yt_dlp

app = Flask(__name__)

# ==============================================================================
# FRONTEND (HTML, CSS, JS) - Alinhado ao estilo obs.desk / subtexto / contexto
# ==============================================================================
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>media.downloader</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Fontes -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
    <!-- Icones FontAwesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #09090b; 
        }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: #18181b; }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 2px; }
        
        /* Spinner customizado rotativo */
        .spinner {
            border: 2px solid transparent;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 0.8s linear infinite;
        }
        .spinner-dark {
            border-top-color: #09090b;
            border-left-color: #09090b;
        }
        .spinner-emerald {
            border-top-color: #064e3b;
            border-left-color: #064e3b;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="text-zinc-100 min-h-screen flex flex-col items-center justify-center p-4 md:p-8 selection:bg-zinc-800 selection:text-white">

    <div class="max-w-2xl w-full mb-6 mt-4">
        <h1 class="text-white text-5xl font-['Space_Grotesk'] font-bold tracking-tighter lowercase flex items-center gap-3">
            <i class="fa-solid fa-cloud-arrow-down text-zinc-100 text-3xl"></i> media.downloader
        </h1>
    </div>

    <!-- Bento Card Principal -->
    <main class="w-full max-w-2xl bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 transition-all duration-300 hover:border-zinc-700/80 shadow-xl flex flex-col gap-5">
        
        <!-- Input URL -->
        <div class="flex flex-col gap-2">
            <label class="text-xs uppercase tracking-widest text-zinc-500 font-bold font-['Space_Grotesk']">Cole o link do vídeo</label>
            <div class="flex flex-col sm:flex-row gap-3">
                <input type="text" id="urlInput" class="bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 transition w-full" placeholder="https://www.youtube.com/watch?v=...">
                
                <button onclick="carregarInfo()" id="loadBtn" class="bg-zinc-100 text-zinc-950 font-bold text-xs uppercase tracking-wider px-6 py-3 rounded-xl hover:bg-white transition active:scale-95 duration-150 flex items-center justify-center gap-2 whitespace-nowrap">
                    <span id="loadText">Analisar</span>
                    <div id="loadSpinner" class="spinner spinner-dark hidden"></div>
                </button>
            </div>
        </div>

        <!-- Banner de Erro -->
        <div id="errorMsg" class="hidden bg-rose-950/20 border border-rose-800/60 p-4 rounded-xl text-rose-400 text-xs font-medium flex items-center gap-2">
            <i class="fa-solid fa-triangle-exclamation"></i>
            <span id="errorText">Erro detectado</span>
        </div>

        <!-- Área de Download -->
        <div id="downloadArea" class="hidden border-t border-zinc-800/80 pt-6 flex flex-col gap-4">
            
            <div class="bg-zinc-950/40 p-4 rounded-xl border border-zinc-800/60 flex flex-col gap-1">
                <span class="text-[10px] uppercase tracking-widest text-zinc-500 font-bold font-['Space_Grotesk']">Vídeo Identificado</span>
                <p id="videoTitle" class="text-sm font-semibold text-zinc-200 truncate"></p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="flex flex-col gap-2">
                    <label class="text-xs uppercase tracking-widest text-zinc-500 font-bold font-['Space_Grotesk']">Formato de Saída</label>
                    <div class="relative">
                        <select id="formatSelect" onchange="atualizarOpcoesQualidade()" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-300 focus:outline-none focus:border-zinc-700 transition cursor-pointer appearance-none">
                            <option value="video">Vídeo (MP4)</option>
                            <option value="audio">Áudio (MP3)</option>
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-zinc-500">
                            <i class="fa-solid fa-chevron-down text-xs"></i>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-2">
                    <label class="text-xs uppercase tracking-widest text-zinc-500 font-bold font-['Space_Grotesk']">Qualidade</label>
                    <div class="relative">
                        <select id="qualitySelect" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-300 focus:outline-none focus:border-zinc-700 transition cursor-pointer appearance-none">
                            <!-- As opções serão populadas dinamicamente via JS -->
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-zinc-500">
                            <i class="fa-solid fa-chevron-down text-xs"></i>
                        </div>
                    </div>
                </div>
                
                <div class="flex items-end">
                    <button onclick="iniciarDownload()" id="downloadBtn" class="w-full bg-emerald-200 hover:bg-emerald-100 text-emerald-950 font-bold text-xs uppercase tracking-wider py-3.5 rounded-xl active:scale-95 transition-all duration-200 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-download"></i> 
                        <span id="downloadText">Baixar Agora</span>
                        <div id="downloadSpinner" class="spinner spinner-emerald hidden"></div>
                    </button>
                </div>
            </div>
        </div>
    </main>

    <script>
        let currentUrl = '';

        async function carregarInfo() {
            const url = document.getElementById('urlInput').value.trim();
            if (!url) return;
            
            currentUrl = url;
            alternarBotao('loadBtn', 'loadText', 'loadSpinner', true, 'Analisando...');
            document.getElementById('errorMsg').classList.add('hidden');
            document.getElementById('downloadArea').classList.add('hidden');

            try {
                const response = await fetch('/api/info', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: url })
                });
                
                const data = await response.json();
                
                if (data.sucesso) {
                    document.getElementById('videoTitle').textContent = data.titulo;
                    document.getElementById('downloadArea').classList.remove('hidden');
                    atualizarOpcoesQualidade();
                } else {
                    mostrarErro(data.erro);
                }
            } catch (err) {
                mostrarErro("Erro de conexão com o servidor.");
            } finally {
                alternarBotao('loadBtn', 'loadText', 'loadSpinner', false, 'Analisar');
            }
        }

        async function iniciarDownload() {
            const format = document.getElementById('formatSelect').value;
            const quality = document.getElementById('qualitySelect').value;
            alternarBotao('downloadBtn', 'downloadText', 'downloadSpinner', true, 'Baixando...');

            try {
                const response = await fetch('/api/baixar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: currentUrl, formato: format, qualidade: quality })
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.erro || 'Falha no download');
                }

                let filename = 'download';
                const disposition = response.headers.get('Content-Disposition');
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    // Extrai UTF-8 ou filename simples
                    const utf8FilenameRegex = /filename\*=UTF-8''([^;\n]+)/i;
                    const normalFilenameRegex = /filename="?([^;\n"]+)"?/i;
                    
                    let matches = utf8FilenameRegex.exec(disposition);
                    if (matches && matches[1]) {
                        filename = decodeURIComponent(matches[1]);
                    } else {
                        matches = normalFilenameRegex.exec(disposition);
                        if (matches && matches[1]) {
                            filename = matches[1];
                        }
                    }
                }

                const blob = await response.blob();
                const windowUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = windowUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(windowUrl);

            } catch (err) {
                mostrarErro("Erro ao baixar: " + err.message);
            } finally {
                alternarBotao('downloadBtn', 'downloadText', 'downloadSpinner', false, 'Baixar Agora');
            }
        }

        function mostrarErro(msg) {
            const el = document.getElementById('errorMsg');
            const txt = document.getElementById('errorText');
            txt.textContent = msg;
            el.classList.remove('hidden');
        }

        function alternarBotao(btnId, textId, spinnerId, loading, text) {
            const btn = document.getElementById(btnId);
            const span = document.getElementById(textId);
            const spinner = document.getElementById(spinnerId);
            
            btn.disabled = loading;
            btn.style.opacity = loading ? '0.7' : '1';
            span.textContent = text;
            if (loading) spinner.classList.remove('hidden');
            else spinner.classList.add('hidden');
        }

        function atualizarOpcoesQualidade() {
            const format = document.getElementById('formatSelect').value;
            const qualitySelect = document.getElementById('qualitySelect');
            qualitySelect.innerHTML = '';
            
            if (format === 'video') {
                qualitySelect.innerHTML = `
                    <option value="alta">Alta (Melhor disponível)</option>
                    <option value="media" selected>Média (Até 720p)</option>
                    <option value="baixa">Baixa (Até 480p)</option>
                `;
            } else {
                qualitySelect.innerHTML = `
                    <option value="alta">Alta (320 kbps)</option>
                    <option value="media" selected>Média (192 kbps)</option>
                    <option value="baixa">Baixa (128 kbps)</option>
                `;
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# BACKEND (Tratamento de Erros e Limpeza de Arquivos)
# ==============================================================================

def formatar_erro_ytdl(e):
    """Retorna uma mensagem de erro compreensível ao usuário"""
    err_str = str(e)
    if "Unsupported URL" in err_str:
        return "A plataforma ou link inserido não é suportado pelo sistema."
    if "Private video" in err_str or "is private" in err_str:
        return "Este vídeo é privado ou requer autorização especial para acessar."
    if "confirm your age" in err_str or "age-gated" in err_str:
        return "Este vídeo possui restrição de idade e não pode ser baixado."
    if "Video unavailable" in err_str:
        return "Este vídeo está indisponível ou foi removido."
    if "geolocation" in err_str or "geoblocked" in err_str:
        return "Este vídeo está bloqueado para a nossa região geográfica."
    # Divide para simplificar o traceback técnico longo
    return f"Erro de processamento: {err_str.split(';')[0]}"


def thread_limpeza_arquivos():
    """Thread em background para limpar arquivos temporários antigos de download"""
    pasta_temp = tempfile.gettempdir()
    while True:
        try:
            agora = time.time()
            for filename in os.listdir(pasta_temp):
                caminho = os.path.join(pasta_temp, filename)
                if os.path.isfile(caminho):
                    idade = agora - os.path.getmtime(caminho)
                    # Limpa arquivos com mais de 30 minutos (1800 segundos)
                    if idade > 1800:
                        ext = os.path.splitext(filename)[1].lower()
                        # Segurança: Deleta apenas extensões comuns criadas pelo app/yt-dlp
                        if ext in ['.mp3', '.mp4', '.webm', '.part', '.ytdl', '.m4a']:
                            try:
                                os.remove(caminho)
                            except Exception:
                                pass
        except Exception as e:
            print(f"[Limpeza] Erro ao escanear pasta temporária: {e}")
        time.sleep(600)  # Executa a cada 10 minutos


# Inicializa a thread de limpeza automática como daemon
t = threading.Thread(target=thread_limpeza_arquivos, daemon=True)
t.start()


@app.route('/')
def index():
    """Rota principal que serve a página HTML"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/info', methods=['POST'])
def obter_info():
    """Extrai informações do vídeo sem baixar"""
    url = request.json.get('url')
    if not url: 
        return jsonify({"sucesso": False, "erro": "URL inválida"}), 400

    ydl_opts = {'quiet': True, 'extract_flat': True, 'nocheckcertificate': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"sucesso": True, "titulo": info.get('title', 'Vídeo Desconhecido')})
    except Exception as e:
        return jsonify({"sucesso": False, "erro": formatar_erro_ytdl(e)}), 400


@app.route('/api/baixar', methods=['POST'])
def baixar():
    """Faz o download do vídeo e envia via streaming com exclusão imediata"""
    url = request.json.get('url')
    formato = request.json.get('formato')  # 'video' ou 'audio'
    qualidade = request.json.get('qualidade', 'media')  # 'alta', 'media', 'baixa'

    if not url: 
        return jsonify({"erro": "URL inválida"}), 400

    pasta_temp = tempfile.gettempdir()
    
    # Configurações do yt-dlp usando timestamps para evitar colisões
    ydl_opts = {
        'outtmpl': os.path.join(pasta_temp, '%(title)s-%(id)s.%(ext)s'),
        'quiet': True,
        'noplaylist': True,
        'nocheckcertificate': True,
    }

    if formato == 'audio':
        # Mapeamento de bitrate para áudio
        bitrate = '192'
        if qualidade == 'alta':
            bitrate = '320'
        elif qualidade == 'baixa':
            bitrate = '128'

        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': bitrate,
        }]
    else:
        # Mapeamento de formatos de vídeo
        ydl_opts['merge_output_format'] = 'mp4'
        if qualidade == 'alta':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif qualidade == 'baixa':
            ydl_opts['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
        else:  # 'media'
            ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best' 

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. Extrai e faz o download
            info = ydl.extract_info(url, download=True)
            caminho_arquivo = ydl.prepare_filename(info)
            
            # Ajuste de extensão se converteu para mp3
            if formato == 'audio':
                base_caminho = os.path.splitext(caminho_arquivo)[0]
                caminho_arquivo = base_caminho + '.mp3'
                if not os.path.exists(caminho_arquivo):
                    # Procura extensões possíveis de áudio convertidas
                    for ext in ['.mp3', '.m4a', '.opus']:
                        if os.path.exists(base_caminho + ext):
                            caminho_arquivo = base_caminho + ext
                            break

            if not os.path.exists(caminho_arquivo):
                return jsonify({"erro": "O download foi concluído, mas o arquivo gerado não foi encontrado no servidor."}), 500

            # 2. Transmite o arquivo gerando chunks e deletando imediatamente ao terminar
            def gerar_chunks():
                try:
                    with open(caminho_arquivo, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            yield chunk
                finally:
                    # Este bloco executa mesmo se a conexão cair ou terminar
                    try:
                        if os.path.exists(caminho_arquivo):
                            os.remove(caminho_arquivo)
                    except Exception:
                        pass

            mime, _ = mimetypes.guess_type(caminho_arquivo)
            if not mime:
                mime = 'application/octet-stream'

            nome_arquivo_seguro = quote(os.path.basename(caminho_arquivo))
            
            headers = {
                'Content-Disposition': f"attachment; filename*=UTF-8''{nome_arquivo_seguro}",
                'Content-Length': str(os.path.getsize(caminho_arquivo))
            }
            return Response(gerar_chunks(), mimetype=mime, headers=headers)

    except Exception as e:
        return jsonify({"erro": formatar_erro_ytdl(e)}), 500


# Inicia o servidor
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print("Iniciando MediaDownloader...")
    print(f"Servidor rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)