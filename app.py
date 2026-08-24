# ==============================================================================
# MediaDownloader - Aplicação Web com Flask e yt-dlp
# ==============================================================================
import os
import base64
import binascii
import hashlib
import tempfile
import threading
import time
import mimetypes
from urllib.parse import quote, urlparse
from flask import Flask, request, jsonify, render_template_string, Response
import yt_dlp

app = Flask(__name__)


PLATAFORMAS_CONHECIDAS = (
    ('YouTube', ('youtube.com', 'youtu.be', 'music.youtube.com')),
    ('SoundCloud', ('soundcloud.com', 'on.soundcloud.com')),
    ('Instagram', ('instagram.com', 'instagr.am')),
)


def identificar_plataforma(url):
    """Identifica plataformas conhecidas sem impedir extractors genéricos."""
    try:
        host = (urlparse(url).hostname or '').lower().removeprefix('www.')
    except ValueError:
        return 'Outro site'

    for nome, dominios in PLATAFORMAS_CONHECIDAS:
        if any(host == dominio or host.endswith(f'.{dominio}') for dominio in dominios):
            return nome
    return 'Outro site'


class CookieConfigurationError(ValueError):
    """Erro seguro de configuração, sem expor o conteúdo dos cookies."""


def _validar_conteudo_cookies(conteudo):
    """Normaliza e valida um cookie jar no formato Mozilla/Netscape."""
    conteudo = conteudo.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    linhas = conteudo.splitlines()
    if not linhas or linhas[0].strip() not in (
        '# Netscape HTTP Cookie File',
        '# HTTP Cookie File',
    ):
        raise CookieConfigurationError(
            "Os cookies não estão no formato Netscape. Exporte um cookies.txt "
            "cuja primeira linha seja '# Netscape HTTP Cookie File'."
        )

    linhas_cookie = [
        linha for linha in linhas
        if linha.strip() and not linha.lstrip().startswith('#')
    ]
    if not linhas_cookie:
        raise CookieConfigurationError("O arquivo de cookies está vazio.")
    if any(len(linha.split('\t')) != 7 for linha in linhas_cookie):
        raise CookieConfigurationError(
            "O arquivo de cookies possui linhas inválidas; exporte-o novamente no formato Netscape."
        )
    return conteudo.rstrip('\n') + '\n'


def _gravar_cookie_temporario(conteudo):
    """Materializa conteúdo validado com LF e permissão exclusiva do processo."""
    resumo = hashlib.sha256(conteudo.encode('utf-8')).hexdigest()[:16]
    caminho = os.path.join(tempfile.gettempdir(), f'media-downloader-cookies-{resumo}.txt')
    if not os.path.exists(caminho):
        descritor, caminho_temporario = tempfile.mkstemp(
            prefix='media-downloader-cookies-', suffix='.tmp'
        )
        try:
            with os.fdopen(descritor, 'w', encoding='utf-8', newline='\n') as arquivo:
                arquivo.write(conteudo)
            os.chmod(caminho_temporario, 0o600)
            os.replace(caminho_temporario, caminho)
        finally:
            if os.path.exists(caminho_temporario):
                os.remove(caminho_temporario)
    return caminho


def obter_cookie_path():
    """Resolve cookies apenas de fontes explicitamente configuradas."""
    caminho_configurado = os.environ.get('YOUTUBE_COOKIES_FILE', '').strip()
    conteudo_base64 = os.environ.get('YOUTUBE_COOKIES_BASE64', '').strip()
    conteudo_bruto = os.environ.get('YOUTUBE_COOKIES', '')

    fontes = sum(bool(valor) for valor in (
        caminho_configurado, conteudo_base64, conteudo_bruto,
    ))
    if fontes > 1:
        raise CookieConfigurationError(
            "Configure somente uma fonte: YOUTUBE_COOKIES_FILE, "
            "YOUTUBE_COOKIES_BASE64 ou YOUTUBE_COOKIES."
        )

    if caminho_configurado:
        caminho = os.path.abspath(os.path.expanduser(caminho_configurado))
        if not os.path.isfile(caminho):
            raise CookieConfigurationError(
                "O arquivo definido em YOUTUBE_COOKIES_FILE não foi encontrado."
            )
        try:
            with open(caminho, 'r', encoding='utf-8-sig') as arquivo:
                conteudo = _validar_conteudo_cookies(arquivo.read())
        except UnicodeDecodeError as exc:
            raise CookieConfigurationError("O arquivo de cookies não está em UTF-8.") from exc
        return _gravar_cookie_temporario(conteudo)

    if conteudo_base64:
        try:
            conteudo_bruto = base64.b64decode(
                conteudo_base64, validate=True
            ).decode('utf-8-sig')
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise CookieConfigurationError(
                "YOUTUBE_COOKIES_BASE64 não contém um arquivo UTF-8 em Base64 válido."
            ) from exc

    if conteudo_bruto:
        conteudo = _validar_conteudo_cookies(conteudo_bruto)
        return _gravar_cookie_temporario(conteudo)

    return None


def aplicar_autenticacao(ydl_opts):
    """Aplica cookies e User-Agent configurados a qualquer plataforma."""
    cookie_path = obter_cookie_path()
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path
    user_agent = os.environ.get('YOUTUBE_USER_AGENT', '').strip()
    if user_agent:
        ydl_opts['http_headers'] = {'User-Agent': user_agent}
    # Reduz o risco de a sessão convidada/da conta atingir o limite de requisições.
    ydl_opts.setdefault('sleep_interval_requests', 1)
    return ydl_opts

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

        .download-progress-indeterminate {
            width: 35%;
            animation: progress-slide 1.35s ease-in-out infinite;
        }
        @keyframes progress-slide {
            0% { transform: translateX(-115%); }
            100% { transform: translateX(315%); }
        }
    </style>
</head>
<body class="text-zinc-100 min-h-screen flex flex-col items-center justify-center p-4 md:p-8 selection:bg-zinc-800 selection:text-white">

    <div class="max-w-2xl w-full mb-6 mt-4">
        <h1 class="text-white text-2xl sm:text-5xl font-['Space_Grotesk'] font-bold tracking-tighter lowercase flex items-center gap-2 sm:gap-3 leading-tight whitespace-nowrap">
            <i class="fa-solid fa-cloud-arrow-down text-zinc-100 text-xl sm:text-3xl flex-shrink-0"></i> media.downloader
        </h1>
    </div>

    <!-- Bento Card Principal -->
    <main class="w-full max-w-2xl bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 transition-all duration-300 hover:border-zinc-700/80 shadow-xl flex flex-col gap-5">
        
        <!-- Input URL -->
        <div class="flex flex-col gap-2">
            <label class="text-xs uppercase tracking-widest text-zinc-500 font-bold font-['Space_Grotesk']">Cole o link de vídeo ou música</label>
            <div class="flex flex-col sm:flex-row gap-3">
                <input type="text" id="urlInput" class="bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 focus:ring-1 focus:ring-zinc-700 transition w-full" placeholder="YouTube, SoundCloud ou Instagram...">
                
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
                <div class="flex items-center justify-between gap-3">
                    <span class="text-[10px] uppercase tracking-widest text-zinc-500 font-bold font-['Space_Grotesk']">Mídia Identificada</span>
                    <span id="platformBadge" class="rounded-full border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Outro site</span>
                </div>
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

            <div id="downloadStatus" class="hidden rounded-xl border border-emerald-900/70 bg-emerald-950/20 p-4" role="status" aria-live="polite">
                <div class="flex items-start gap-3">
                    <i id="downloadStatusIcon" class="fa-solid fa-cloud-arrow-down text-emerald-300 mt-0.5"></i>
                    <div class="min-w-0 flex-1">
                        <p id="downloadStatusTitle" class="text-sm font-semibold text-emerald-100">Preparando o download...</p>
                        <p id="downloadStatusDetail" class="mt-1 text-xs leading-relaxed text-emerald-200/70">O servidor está baixando e processando o arquivo. Isso pode levar alguns minutos.</p>
                    </div>
                </div>
                <div id="downloadProgressTrack" class="mt-3 hidden h-1.5 overflow-hidden rounded-full bg-emerald-950" role="progressbar" aria-label="Progresso da transferência" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
                    <div id="downloadProgressBar" class="h-full rounded-full bg-emerald-300 transition-[width] duration-200" style="width: 0%"></div>
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
                    document.getElementById('platformBadge').textContent = data.plataforma || 'Outro site';
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
            atualizarStatusDownload(
                'Preparando o download...',
                'O servidor está baixando e processando o arquivo. Isso pode levar alguns minutos.'
            );

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

                const totalBytes = Number(response.headers.get('Content-Length')) || 0;
                atualizarStatusDownload(
                    'Transferindo para o seu aparelho...',
                    totalBytes ? 'O arquivo está pronto. Não feche esta página até terminar.' : 'O arquivo está pronto e será enviado agora.',
                    totalBytes ? 0 : null
                );

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

                let blob;
                if (response.body && response.body.getReader) {
                    const reader = response.body.getReader();
                    const chunks = [];
                    let receivedBytes = 0;

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        chunks.push(value);
                        receivedBytes += value.length;
                        if (totalBytes) {
                            atualizarStatusDownload(
                                'Transferindo para o seu aparelho...',
                                `${formatarBytes(receivedBytes)} de ${formatarBytes(totalBytes)}`,
                                Math.min(100, Math.round((receivedBytes / totalBytes) * 100))
                            );
                        }
                    }
                    blob = new Blob(chunks, {type: response.headers.get('Content-Type') || 'application/octet-stream'});
                } else {
                    blob = await response.blob();
                }

                const windowUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = windowUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(windowUrl);
                atualizarStatusDownload('Download concluído!', 'O arquivo foi enviado para a pasta de downloads do seu aparelho.', 100);

            } catch (err) {
                mostrarErro("Erro ao baixar: " + err.message);
                atualizarStatusDownload('Download interrompido', 'Confira a mensagem de erro acima e tente novamente.', 0, true);
            } finally {
                alternarBotao('downloadBtn', 'downloadText', 'downloadSpinner', false, 'Baixar Agora');
            }
        }

        function atualizarStatusDownload(titulo, detalhe, progresso = null, erro = false) {
            const status = document.getElementById('downloadStatus');
            const icon = document.getElementById('downloadStatusIcon');
            const title = document.getElementById('downloadStatusTitle');
            const detail = document.getElementById('downloadStatusDetail');
            const track = document.getElementById('downloadProgressTrack');
            const bar = document.getElementById('downloadProgressBar');

            status.classList.remove('hidden', 'border-emerald-900/70', 'bg-emerald-950/20', 'border-rose-900/70', 'bg-rose-950/20');
            status.classList.add(erro ? 'border-rose-900/70' : 'border-emerald-900/70', erro ? 'bg-rose-950/20' : 'bg-emerald-950/20');
            icon.className = erro
                ? 'fa-solid fa-triangle-exclamation text-rose-300 mt-0.5'
                : progresso === 100
                    ? 'fa-solid fa-circle-check text-emerald-300 mt-0.5'
                    : 'fa-solid fa-cloud-arrow-down text-emerald-300 mt-0.5';
            title.className = erro ? 'text-sm font-semibold text-rose-100' : 'text-sm font-semibold text-emerald-100';
            detail.className = erro ? 'mt-1 text-xs leading-relaxed text-rose-200/70' : 'mt-1 text-xs leading-relaxed text-emerald-200/70';
            title.textContent = titulo;
            detail.textContent = detalhe;

            if (progresso === null) {
                track.classList.remove('hidden');
                bar.classList.add('download-progress-indeterminate');
                bar.style.width = '35%';
                track.removeAttribute('aria-valuenow');
                track.setAttribute('aria-valuetext', 'Preparando o download');
            } else {
                track.classList.remove('hidden');
                bar.classList.remove('download-progress-indeterminate');
                bar.style.width = `${progresso}%`;
                track.setAttribute('aria-valuenow', String(progresso));
                track.setAttribute('aria-valuetext', `${progresso}% concluído`);
            }
        }

        function formatarBytes(bytes) {
            if (!bytes) return '0 B';
            const unidades = ['B', 'KB', 'MB', 'GB'];
            const indice = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), unidades.length - 1);
            return `${(bytes / Math.pow(1024, indice)).toFixed(indice ? 1 : 0)} ${unidades[indice]}`;
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
    if isinstance(e, CookieConfigurationError):
        return str(e)
    erro_bot = (
        "Sign in to confirm" in err_str
        or "confirm you’re not a bot" in err_str
        or "confirm you're not a bot" in err_str
        or "LOGIN_REQUIRED" in err_str
    )
    if erro_bot:
        return (
            "A plataforma recusou a sessão deste servidor. Para conteúdo público, tente novamente "
            "após alguns minutos; para conteúdo restrito, configure cookies novos exportados "
            "no formato Netscape e, se necessário, o User-Agent do mesmo navegador."
        )
    if "cookies" in err_str.lower() and "netscape" in err_str.lower():
        return "O arquivo de cookies é inválido; exporte-o novamente no formato Netscape."
    if "Unsupported URL" in err_str:
        return "A plataforma ou link inserido não é suportado pelo sistema."
    if "Private video" in err_str or "is private" in err_str or "login required" in err_str.lower():
        return "Esta mídia é privada ou exige login para ser acessada."
    if "confirm your age" in err_str or "age-gated" in err_str:
        return "Este vídeo possui restrição de idade e não pode ser baixado."
    if "Video unavailable" in err_str or "Post unavailable" in err_str:
        return "Esta mídia está indisponível ou foi removida."
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

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'nocheckcertificate': True,
    }

    try:
        aplicar_autenticacao(ydl_opts)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "sucesso": True,
                "titulo": info.get('title', 'Mídia desconhecida'),
                "plataforma": identificar_plataforma(url),
            })
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
        aplicar_autenticacao(ydl_opts)
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
