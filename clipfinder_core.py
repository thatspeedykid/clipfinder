# clipfinder_core.py
# Core AI, transcription, and analysis logic for ClipFinder
# Platform-independent — imported by clipfinder_win.py, clipfinder_mac.py, clipfinder_linux.py
#
# Edit THIS file to change AI behavior, prompts, or transcription across ALL platforms.
# Edit the platform file (win/mac/linux) for OS-specific code only.

import re
import json
import subprocess
from pathlib import Path


# ═══ AI PROVIDERS & PROMPTS ═══

PROVIDERS = {
    'Google Gemini (Free)': {
        'lib':    'gemini',
        'models': ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash'],
        # NOTE: gemini-1.5-* ALL DEAD (404). gemini-2.0-flash shuts down June 1 2026.
        'url':    'https://aistudio.google.com/apikey',
        'note':   'Free — no credit card needed',
    },
    'Groq (Free)': {
        'lib':    'groq',
        'models': [
            'llama-3.3-70b-versatile', # 32k context, smarter
            'mixtral-8x7b-32768',      # 32k context window
            'llama-3.1-8b-instant',    # 8k context — fast but small
            'llama3-8b-8192',          # 8k context fallback
        ],
        'url':    'https://console.groq.com',
        'note':   'Free — no credit card needed',
    },
    'OpenRouter (Free models)': {
        'lib':    'openrouter',
        'models': [
            'openrouter/auto',                              # OR's own free router — auto-picks best available
            'meta-llama/llama-3.3-70b-instruct:free',      # Llama 3.3 70B — top free model
            'nvidia/nemotron-3-super-120b-a12b:free',       # NVIDIA 120B — large context
            'google/gemma-3-12b-it:free',                   # Gemma 3 12B
            'meta-llama/llama-3.1-8b-instruct:free',        # Llama 3.1 8B — fast fallback
            'mistralai/mistral-small-3.1:free',              # Mistral Small 3.1
            'qwen/qwen3.6-plus:free',                        # Qwen — last resort
        ],
        'url':    'https://openrouter.ai/keys',
        'note':   '50+ free models — no credit card needed',
    },
}

AUTO_EDIT_PROMPT = """You are a professional video editor for a viral drama/streaming Twitter channel.
{context_block}
Given this timestamped transcript, select segments that together total approximately {target_sec} seconds ({target_min} minutes).

CRITICAL RULES — you MUST follow these:
- TOTAL combined duration must reach AT LEAST {target_sec} seconds — this is the most important rule
- Each individual segment MUST be at least {min_seg_sec} seconds long — never pick a tiny 5-10 second clip
- Prefer FEWER LONGER segments over many short ones — a 3-minute segment is better than six 30-second ones
- Each segment starts where a topic/point begins and ends when it naturally concludes
- Skip dead air, filler ("um", "uh", "like", "you know"), and boring transitions between topics
- Score each segment 1-10 based on: {score_desc}
- Select enough segments to fill the target duration — if you need 10 minutes, pick segments that add up to 10 minutes
- CRITICAL: Every segment MUST end on a completed sentence. Never cut mid-word or mid-sentence

Return ONLY a raw JSON array sorted by {order}:
[
  {{
    "start": "HH:MM:SS",
    "end":   "HH:MM:SS",
    "title": "Short label for this segment",
    "reason": "Why this is good content",
    "score": 9,
    "order": 1
  }}
]

TRANSCRIPT:
{transcript}
"""


AI_PROMPT = """You are an expert viral clip editor for a drama/streaming/gaming channel (@MarsScumbags style).
{context_block}
{names_block}
Find the 3-6 BEST moments to clip. Quality over quantity — 3 great clips beats 8 mediocre ones.

━━━ CLIP LENGTH — NON-NEGOTIABLE ━━━
MINIMUM: 1 minute 00 seconds (60 seconds) — NO EXCEPTIONS
MAXIMUM: 2 minutes 40 seconds (160 seconds)
IDEAL:   1:30 to 2:00 — enough room for full setup + escalation + payoff

If a juicy moment is only 20 seconds, DO NOT clip it alone.
Instead, include the 30-40 seconds BEFORE it (the lead-up/context) to hit minimum length.
If a moment runs over 2:40, find the natural END POINT before the 2:40 mark.
REJECT any clip under 60 seconds — do not output it.

━━━ SELF-CONTAINED RULE ━━━
Every clip must make sense to someone who has NEVER seen this stream.
- Start before the moment — include what caused it
- End AFTER the reaction/punchline/resolution lands fully
- Never cut mid-sentence, mid-thought, or before the crowd/streamer reacts
- Ask: "Would a random person watching this understand what happened?" — if no, extend the start

━━━ WHAT TO LOOK FOR ━━━
1. Hard reveals / confessions with reaction
2. Callouts / confrontations — include the accusation AND the response
3. Escalating rants — setup → build → punchline/explosion
4. Surprising admissions that contradict their image
5. Absurd escalating moments with a clear comedic payoff
6. Strong takes where someone gets pushed back on

━━━ SCORING (each /25) ━━━
- hook: Does the first 5 seconds grab immediately?
- engagement: Does tension build throughout? Does watching to the end feel rewarding?
- value: Real substance, not filler chatter
- shareability: Would people send this to their group chat?
- score (1-10): Only output clips scoring 7+. Be strict.

TITLE: News headline style — "She admits the prank went too far" not "Funny clip" — use REAL names from the transcript, never invent names.
If a VIDEO TITLE is provided, extract the names of people mentioned in it and use those names in titles and descriptions when those people speak.

UNIQUENESS: Every clip MUST cover a DIFFERENT moment with a DIFFERENT title. Do NOT output multiple clips about the same topic or event. Spread clips across the full transcript — different timestamps, different topics, different people speaking.

LENGTH CHECK: Before outputting, verify each clip is between 60-160 seconds.
Calculate: convert end and start to seconds, subtract. If under 60s, extend or drop it.

Return ONLY a raw JSON array. NO markdown. NO backticks. NO ```json. NO explanation before or after. Start your response with [ and end with ]. Nothing else.
[
  {
    "start": "HH:MM:SS",
    "end": "HH:MM:SS",
    "title": "News headline — punchy, max 10 words",
    "summary": "The arc: what set it up, how it escalated, how it paid off",
    "reason": "What literally happens in plain terms",
    "score": 9,
    "hook": 22,
    "engagement": 24,
    "value": 18,
    "shareability": 23
  }
]

TRANSCRIPT:
{transcript}
"""

INTERVIEW_CLIP_PROMPT = """You are an expert clip editor for a drama/streaming Twitter channel.
{context_block}
This is an interview transcript. The interviewer asks questions and names people directly (e.g. "Hey Sophie, what do you think about...").

Interviewees in this interview: {names}
If names above are blank or "Unknown", extract the names of people being interviewed from the VIDEO TITLE if provided, or infer names from the transcript itself (e.g. when the interviewer says "So [Name], tell me about...").

Your job:
1. Identify which person is speaking in each segment based on who was just addressed by the interviewer
2. Find the best 4-8 moments to clip — one clip per person per great moment
3. For each clip, note which person is the subject

CLIP LENGTH — NON-NEGOTIABLE:
- MINIMUM 60 seconds (1 full minute) — no exceptions, extend into lead-up if needed
- MAXIMUM 160 seconds (2 min 40 sec)
- IDEAL 90-120 seconds — question + full answer + reaction
- Never cut mid-sentence — end after the person fully completes their thought and any reaction
- If an answer is short, include more of the question/setup before it to reach 60s minimum

Score each clip 1-10 for viral/drama potential.

Return ONLY a raw JSON array sorted by score DESCENDING:
[
  {{
    "start": "HH:MM:SS",
    "end": "HH:MM:SS",
    "speaker": "Sophie",
    "title": "Punchy title max 8 words",
    "reason": "One sentence why this goes viral",
    "score": 9
  }}
]

TRANSCRIPT:
{transcript}
"""

TWEET_PROMPT = """You are a social media writer for @MarsScumbags, a streaming drama/clip channel on X/Twitter.
Read the transcript carefully. Identify WHO is involved, WHAT happened, and the most shocking/quotable moment.

== PEOPLE & CONTEXT ==
{context}

== TRANSCRIPT ==
{transcript}

== TONE ==
{tone}

== YOUR JOB ==
Write 3 tweets ALL in the same tone above. Each tweet covers the same event but from a DIFFERENT ANGLE:

OPTION 1 — HOT TAKE
Your punchy opinion or reaction to what happened. Lead with the most shocking element.
Structure: Strong opener (can be all caps or shocking statement) → context sentence → spicy take or quote → hashtags
Max 280 chars. Must reference a SPECIFIC moment or quote from the transcript.

OPTION 2 — PULL QUOTE
Lead with an actual direct quote or close paraphrase from the transcript (in quotes), then react to it.
Structure: "Quote from transcript" → your reaction/commentary → hashtags
Max 280 chars. The quote must be real and specific — not made up.

OPTION 3 — ANNOUNCEMENT HOOK
Frame it like breaking news or a must-see moment. Make people feel like they NEED to watch the clip.
Structure: Hook that creates urgency or curiosity → what happened → call to action or cliffhanger → hashtags
Max 280 chars. No clickbait that doesn't deliver — be specific about what happens.

== OUTPUT FORMAT ==
Write EXACTLY this — no preamble, no labels other than OPTION 1/2/3:

OPTION 1
[tweet text]

OPTION 2
[tweet text]

OPTION 3
[tweet text]

== HASHTAG RULES ==
- Use ACTUAL NAMES from the transcript/context ONLY — never invent or assume names not mentioned
- Use platform only if relevant (#Kick #Twitch #YouTube)
- Use drama type if it fits (#Exposed #Drama #Beef #Leaked #Scandal)
- NEVER use #gaming #gamingscandal #gamer #streamer unless literally about gameplay
- Each option gets its OWN hashtags matching what THAT tweet says
- 3-5 hashtags max per option

== RULES ==
- All 3 options MUST be in the same tone — do NOT switch styles between options
- Each option must feel different in angle and structure but same energy
- Use REAL quotes and REAL moments — never make things up
- No preamble before OPTION 1 — start writing immediately
"""

TWEET_TONE_PROMPTS = {
    'drama': '🔥 DRAMA ACCOUNT — Tea spiller energy. Shocking, pointed, like a real streaming drama page. Use emojis strategically. Pull receipts.',
    'tea':   '☕ TEA MODE — Calm but devastating. Matter-of-fact delivery that makes the drama hit harder. "So apparently..." energy. Understated.',
    'breaking': '📰 BREAKING NEWS — Urgent, journalistic. "BREAKING:" opener. Treat it like actual news. Serious tone, facts first.',
    'hype':  '💥 HYPE MODE — Celebrate the moment. Positive energy, get people excited to watch. Use energy words. Make it feel unmissable.',
    'exaggerate': """🤯 EXAGGERATE MODE — Write a dramatic multi-line story that builds line by line. Use this EXACT format:

🚨 [SHOCKING HEADLINE IN CAPS — name the person and the situation] 😳
[Setup line — what the secret or situation was] 👀
[Escalation — what triggered it or made it worse] 💔
[Twist — how things shifted or got more chaotic] 💸🔥
[Punchline — how wild it ended up] ⚡

Rules: Each line max 12 words. 1-2 emojis at END of each line. Build tension line by line.
Stay factual to the transcript — just massively dramatize real events.
Never mean-spirited toward the person — make them the legendary main character.
All 3 options follow this same format but cover DIFFERENT angles of the same story.
Hashtags on a separate final line.""",
}



# Config lives next to the EXE/script so settings survive across launches
# This ensures _setup_done, API keys, folders etc persist properly


# ═══ TIMESTAMP UTILITIES ═══

def ts(s):
    s = int(float(s))
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f'{h:02d}:{m:02d}:{sec:02d}'

def ts_srt(s):
    """Convert seconds to SRT HH:MM:SS,mmm — CapCut/Premiere compatible."""
    s   = float(s)
    h   = int(s // 3600); s -= h * 3600
    m   = int(s // 60);   s -= m * 60
    sec = int(s)
    ms  = min(round((s - sec) * 1000), 999)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'




# ═══ GPU ENCODER DETECTION (ffmpeg) ═══

def detect_gpu_encoder(ff):
    """Detect best available GPU encoder. Returns (vcodec, acodec, extra_args).
    Priority: NVIDIA NVENC > AMD AMF > Intel QSV > CPU fallback."""
    try:
        r = subprocess.run([ff, '-encoders'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        enc_list = (r.stdout or b'').decode(errors='replace') + (r.stderr or b'').decode(errors='replace')

        # NVIDIA NVENC
        if 'h264_nvenc' in enc_list:
            # Quick test that NVENC actually works (card must be connected)
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_nvenc', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if test.returncode == 0:
                print('[CF] GPU: NVIDIA NVENC detected')
                return 'h264_nvenc', 'aac', ['-preset', 'p5', '-rc', 'vbr', '-cq', '18', '-b:v', '0', '-maxrate', '20M', '-profile:v', 'high', '-b:a', '192k']

        # AMD AMF (Windows)
        if 'h264_amf' in enc_list:
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_amf', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if test.returncode == 0:
                print('[CF] GPU: AMD AMF detected (RX 6600 XT)')
                # usage=transcoding for quality, quality=speed for fast encode
                # rc=vbr_latency + qvbr_quality_level=23 = good quality fast
                return 'h264_amf', 'aac', ['-usage', 'transcoding', '-quality', 'quality', '-rc', 'vbr_peak', '-qvbr_quality_level', '18', '-profile:v', 'high', '-b:v', '8M', '-maxrate', '20M', '-b:a', '192k']

        # Intel QSV
        if 'h264_qsv' in enc_list:
            test = subprocess.run(
                [ff, '-f', 'lavfi', '-i', 'nullsrc=s=128x128:d=0.1',
                 '-c:v', 'h264_qsv', '-f', 'null', '-'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if test.returncode == 0:
                print('[CF] GPU: Intel QSV detected')
                return 'h264_qsv', 'aac', ['-preset', 'medium', '-global_quality', '18', '-look_ahead', '1', '-b:a', '192k']

    except Exception as ex:
        print(f'[CF] GPU detection failed: {ex}')

    print('[CF] CPU: libx264 — high quality')
    return 'libx264', 'aac', [
        '-preset', 'slow', '-crf', '18', '-profile:v', 'high',
        '-movflags', '+faststart', '-b:a', '192k',
    ]

# Cache result so we only probe once per session
_GPU_ENCODER_CACHE = None
_GPU_ENCODER_RESET = False
def detect_encoder_name():
    try:
        v,_,_ = get_encoder(ensure_ffmpeg())
        return v
    except: return "cpu"

def get_encoder(ff):
    global _GPU_ENCODER_CACHE
    if _GPU_ENCODER_CACHE is None:
        _GPU_ENCODER_CACHE = detect_gpu_encoder(ff)
    return _GPU_ENCODER_CACHE

def find_ffmpeg():
    for p in [
        Path('C:/ffmpeg/bin/ffmpeg.exe'),
        Path('C:/ffmpeg/ffmpeg.exe'),
        _app_path('ffmpeg_bin') / 'ffmpeg.exe',
    ]:
        if p.exists():
            return str(p)
    import shutil
    ff = shutil.which('ffmpeg')
    return ff or 'ffmpeg'

# ── Main App ──────────────────────────────────────────────────────────────────
# Cache detected device so we only probe once per session
# Reset on launch so newly installed packages are detected
_WHISPER_DEVICE_CACHE = None



# ═══ WHISPER DEVICE DETECTION ═══

def _detect_whisper_device(use_gpu=True):
    """Detect best available compute device for whisper transcription.
    Returns (device, compute_type, label)
    use_gpu=False forces CPU-only mode."""
    global _WHISPER_DEVICE_CACHE
    if _WHISPER_DEVICE_CACHE and use_gpu:
        return _WHISPER_DEVICE_CACHE

    # ── GPU disabled by user ─────────────────────────────────────────────────
    if not use_gpu:
        try:
            import faster_whisper as _fw_check  # noqa
            return ('cpu', 'int8', 'CPU int8 (GPU disabled)')
        except ImportError:
            return ('cpu', 'int8', 'CPU (GPU disabled)')

    # ── 0. NVIDIA CUDA — whisper.cpp cublas binary ───────────────────────────
    # Use whisper.cpp with cuBLAS instead of faster-whisper+ctranslate2
    # Avoids ctranslate2/cuDNN version hell entirely — just needs NVIDIA driver
    try:
        import subprocess as _sp_nv
        _nv = _sp_nv.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                         capture_output=True, text=True, timeout=3)
        if _nv.returncode == 0 and _nv.stdout.strip():
            _gpu_name = _nv.stdout.strip().split('\n')[0].strip()
            # Check if cublas whisper.cpp binary exists
            _wcpp_cuda = _app_path('whisper_cpp_cuda')
            _wcpp_cuda_exe = _wcpp_cuda / 'whisper-whisper-cli.exe'
            if _wcpp_cuda_exe.exists():
                _WHISPER_DEVICE_CACHE = ('cpu', 'int8', f'NVIDIA CUDA ({_gpu_name}) ⚡')
                return _WHISPER_DEVICE_CACHE
            else:
                # NVIDIA detected but cublas binary not installed yet
                _WHISPER_DEVICE_CACHE = ('cpu', 'int8', f'NVIDIA GPU ({_gpu_name}) — click Install NVIDIA CUDA in Settings')
                return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # Only reach whisper.cpp if CUDA is NOT available
    # ── 1. whisper.cpp + Vulkan (AMD/Intel only) ─────────────────────────────
    _wcpp = _find_whispercpp()
    if _wcpp and _find_whispercpp_model('base'):
        # Check if this is a new RDNA4 card that isn't supported yet
        try:
            import subprocess as _sp_vk, platform as _pl_vk
            if _pl_vk.system() == 'Windows':
                # Check GPU generation via wmic
                _wmic = _sp_vk.run(
                    ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                    capture_output=True, text=True, timeout=5)
                _gpu_name = _wmic.stdout.lower()
                _is_rdna4 = any(x in _gpu_name for x in ['rx 9', '9600', '9700', '9800', '9900'])
                if _is_rdna4:
                    # RDNA4 detected — whisper.cpp Vulkan won't use GPU yet
                    _WHISPER_DEVICE_CACHE = ('cpu', 'int8',
                        'CPU int8 ⚠ RDNA4 GPU not yet supported by whisper.cpp')
                    return _WHISPER_DEVICE_CACHE
        except: pass
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'whisper.cpp Vulkan GPU ⚡')
        return _WHISPER_DEVICE_CACHE

    # ── 2. torch-directml (AMD/Intel on Windows) ──────────────────────────────
    try:
        import torch_directml as _dml
        if _dml.device_count() > 0:
            _WHISPER_DEVICE_CACHE = ('directml', 'float16', 'AMD/Intel DirectML GPU')
            return _WHISPER_DEVICE_CACHE
    except Exception:
        pass

    # ── 3. CPU int8 via CTranslate2 — still 4x faster than openai-whisper ────
    try:
        import faster_whisper as _fw_check  # noqa
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'CPU int8 (faster-whisper)')
    except ImportError:
        _WHISPER_DEVICE_CACHE = ('cpu', 'int8', 'Not installed — use Settings → Update Modules')
    return _WHISPER_DEVICE_CACHE



_WCPP_INSTALL_LOCK = None  # module-level flag to prevent duplicate installs

def auto_install_whispercpp(model_size='base', status_cb=None):
    """Auto-download whisper-whisper-cli.exe (Vulkan) + ggml model for AMD/Intel GPU."""
    global _WCPP_INSTALL_LOCK
    import threading as _thr_lock
    if _WCPP_INSTALL_LOCK is not None:
        return  # already running or done
    _WCPP_INSTALL_LOCK = True
    global _WHISPER_DEVICE_CACHE
    import urllib.request as _ur, zipfile as _zf, tempfile as _tf
    import platform as _pl, shutil as _sh, json as _j

    def _log(msg):
        if not status_cb: print(f'[CF] {msg}')
        if status_cb: status_cb(msg)

    if _pl.system() != 'Windows':
        return

    install_dir = _app_path('whisper_cpp')
    models_dir  = install_dir / 'models'
    real_exe    = install_dir / 'whisper-whisper-cli.exe'
    model_path  = models_dir  / f'ggml-{model_size}.bin'

    install_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Download binary if needed ────────────────────────────────────
    if real_exe.exists():
        _size_mb = real_exe.stat().st_size // 1024 // 1024
        if _size_mb < 10:
            _log(f'Binary exists but only {_size_mb}MB — too small, deleting and re-downloading...')
            real_exe.unlink()
        else:
            _log(f'Binary already exists: {real_exe.name} ({_size_mb}MB)')
    if not real_exe.exists():
        _log('Downloading whisper-whisper-cli.exe (Vulkan)...')
        tmp_zip = Path(_tf.gettempdir()) / 'whispercpp.zip'
        asset_url = None

        # Fetch latest release and find the right asset URL directly
        try:
            req = _ur.Request(
                'https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest',
                headers={'User-Agent': 'ClipFinder/1.0'})
            with _ur.urlopen(req, timeout=20) as resp:
                release = _j.loads(resp.read())

            tag = release.get('tag_name', '')
            _log(f'Latest release: {tag}')
            all_assets = [(a['name'], a['browser_download_url'])
                          for a in release.get('assets', [])]
            _log(f'Available assets: {[n for n,_ in all_assets]}')

            # Priority order — explicitly prefer vulkan-tagged builds
            # v1.8.4 does NOT have a vulkan zip — go straight to fallbacks
            PREFER = ['vulkan', 'bin-x64', 'win']
            AVOID  = ['win32', 'blas', 'cublas', 'xcframework', '.jar', 'openvino']
            scored = []
            for name, url in all_assets:
                nl = name.lower()
                if not nl.endswith('.zip'): continue
                if any(a in nl for a in AVOID): continue
                score = sum(1 for p in PREFER if p in nl)
                if score > 0:
                    scored.append((score, name, url))
            scored.sort(reverse=True)
            # Only use GitHub API result if it's explicitly a Vulkan build
            if scored and 'vulkan' in scored[0][1].lower():
                _, best_name, asset_url = scored[0]
                _log(f'Selected: {best_name} (score={scored[0][0]})')
            else:
                _log(f'No Vulkan asset in GitHub release — using known-good fallback URLs')
        except Exception as e:
            _log(f'GitHub API failed: {e}')

        # Hardcoded fallbacks using known-good direct asset URLs
        if not asset_url:
            fallbacks = [
                # jerryshell dedicated Vulkan Windows build — has ggml-vulkan.dll
                'https://github.com/jerryshell/whisper.cpp-windows-vulkan-bin/releases/latest/download/whisper.cpp-windows-vulkan.zip',
                # Official older vulkan-specific zips
                'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.5/whisper-1.7.5-bin-x64-release-vulkan.zip',
                'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.4/whisper-1.7.4-bin-x64-release-vulkan.zip',
                'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.3/whisper-1.7.3-bin-x64-release-vulkan.zip',
            ]
            for fb in fallbacks:
                try:
                    _log(f'Trying: {fb.split("/")[-1]}')
                    _ur.urlretrieve(fb, str(tmp_zip))
                    if tmp_zip.exists() and tmp_zip.stat().st_size > 100000:
                        asset_url = fb
                        _log('Fallback download succeeded')
                        break
                    else:
                        tmp_zip.unlink(missing_ok=True)
                except Exception as e:
                    _log(f'  Failed: {e}')
                    continue

        if not asset_url:
            _log('ERROR: Could not find a download URL. Check https://github.com/ggerganov/whisper.cpp/releases')
            return

        # Download if not already got from fallback loop
        if not tmp_zip.exists() or tmp_zip.stat().st_size < 100000:
            _log('Downloading zip...')
            try:
                def _dlprogress(count, block, total):
                    if total > 0 and count % 500 == 0:
                        pct = min(100, int(count * block / total * 100))
                        _log(f'Downloading... {pct}%')
                _ur.urlretrieve(asset_url, str(tmp_zip), reporthook=_dlprogress)
            except Exception as e:
                _log(f'Download failed: {e}')
                return

        # Extract
        _log('Extracting...')
        try:
            with _zf.ZipFile(str(tmp_zip), 'r') as z:
                exe_names = [n for n in z.namelist() if n.endswith('.exe')]
                _log(f'Executables in zip: {[Path(n).name for n in exe_names]}')
                all_names = z.namelist()
                _log(f'Zip contains: {[Path(n).name for n in all_names if not n.endswith("/")]}')
                for zname in all_names:
                    bn = Path(zname).name
                    if not bn or zname.endswith('/'): continue
                    if 'deprecation' in bn.lower(): continue
                    # Extract EVERYTHING — exes, dlls, models, config files
                    data = z.read(zname)
                    dest = install_dir / bn
                    if len(data) > 0:
                        dest.write_bytes(data)
                        if bn.endswith(('.exe','.dll')):
                            _log(f'Extracted: {bn} ({len(data)//1024}KB)')
            tmp_zip.unlink(missing_ok=True)

            # Verify this is actually a Vulkan build
            _has_vulkan_dll = (install_dir / 'ggml-vulkan.dll').exists()
            _log(f'ggml-vulkan.dll present: {_has_vulkan_dll}')
            if not _has_vulkan_dll:
                _log('⚠ This build does not include ggml-vulkan.dll — NOT a Vulkan build!')
                _log('  Trying known-good Vulkan fallback URLs...')
                import shutil as _sh_vk
                _sh_vk.rmtree(str(install_dir), ignore_errors=True)
                install_dir.mkdir(parents=True, exist_ok=True)
                _vulkan_fallbacks = [
                    # jerryshell/whisper.cpp-windows-vulkan-bin — dedicated Vulkan Windows builds
                    'https://github.com/jerryshell/whisper.cpp-windows-vulkan-bin/releases/latest/download/whisper.cpp-windows-vulkan.zip',
                    # SourceForge mirror — has vulkan builds for older versions
                    'https://sourceforge.net/projects/whisper-cpp.mirror/files/v1.7.6/whisper-bin-x64.zip/download',
                    # Official older vulkan-specific zips (v1.7.x era)
                    'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.5/whisper-1.7.5-bin-x64-release-vulkan.zip',
                    'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.4/whisper-1.7.4-bin-x64-release-vulkan.zip',
                    'https://github.com/ggerganov/whisper.cpp/releases/download/v1.7.3/whisper-1.7.3-bin-x64-release-vulkan.zip',
                ]
                for _vfb in _vulkan_fallbacks:
                    try:
                        _log(f'Trying Vulkan build: {_vfb.split("/")[-1]}')
                        _ur.urlretrieve(_vfb, str(tmp_zip))
                        if tmp_zip.exists() and tmp_zip.stat().st_size > 100000:
                            import zipfile as _vzf
                            with _vzf.ZipFile(str(tmp_zip), 'r') as _vz:
                                for _vzname in _vz.namelist():
                                    _vbn = Path(_vzname).name
                                    if not _vbn or _vzname.endswith('/'): continue
                                    _vdata = _vz.read(_vzname)
                                    if len(_vdata) > 0:
                                        (install_dir / _vbn).write_bytes(_vdata)
                            tmp_zip.unlink(missing_ok=True)
                            if (install_dir / 'ggml-vulkan.dll').exists():
                                _log('✅ Vulkan build installed successfully!')
                                break
                            else:
                                _sh_vk.rmtree(str(install_dir), ignore_errors=True)
                                install_dir.mkdir(parents=True, exist_ok=True)
                    except Exception as _vfe:
                        _log(f'Vulkan fallback failed: {_vfe}')
                        continue

        except Exception as e:
            _log(f'Extraction failed: {e}')
            return

        # Find the real CLI binary — prefer whisper-cli.exe or main.exe
        # Explicitly avoid server, talk-llama, stream, command (wrong tools)
        AVOID_NAMES = ['talk-llama', 'server', 'stream', 'command', 'bench',
                       'quantize', 'lsp', 'wchess', 'vad', 'test']
        if not real_exe.exists():
            # First try exact names
            for try_name in ['whisper-cli.exe', 'main.exe']:
                candidate = install_dir / try_name
                if candidate.exists() and candidate.stat().st_size > 50_000:
                    _sh.copy2(str(candidate), str(real_exe))
                    _log(f'Linked {candidate.name} → {real_exe.name}')
                    break
        # Still not found? Pick smallest whisper*.exe that isn't a known wrong tool
        if not real_exe.exists():
            candidates = [
                p for p in install_dir.glob('whisper*.exe')
                if not any(a in p.name.lower() for a in AVOID_NAMES)
                and p.stat().st_size > 50_000
            ]
            if candidates:
                best = min(candidates, key=lambda p: p.stat().st_size)
                _sh.copy2(str(best), str(real_exe))
                _log(f'Linked {best.name} → {real_exe.name}')

        if not real_exe.exists():
            _log('ERROR: Binary not found after extraction')
            return

    _bsz = real_exe.stat().st_size
    _bsz_s = f'{_bsz//1024//1024}MB' if _bsz >= 1024*1024 else f'{_bsz//1024}KB'
    _log(f'Binary ready: {real_exe.name} ({_bsz_s})')
    _log(f'Files in whisper_cpp/: {[f.name for f in install_dir.glob("*") if f.is_file()]}')

    # ── Test run the binary to check for missing DLLs ─────────────────────────
    import subprocess as _sp_test
    test = _sp_test.run([str(real_exe), '--help'],
                       stdout=_sp_test.PIPE, stderr=_sp_test.PIPE, timeout=10)
    test_out = (test.stdout or b'').decode(errors='replace') + (test.stderr or b'').decode(errors='replace')
    if test.returncode == 3221225781 or test.returncode == -1073741819:
        _log('WARNING: Binary has DLL issues even with --help. Missing runtime DLLs.')
        _log(f'Test output: {test_out[:200]}')
    elif 'usage' in test_out.lower() or 'whisper' in test_out.lower() or test.returncode == 0:
        _log('Binary test OK — whisper.cpp ready to use GPU!')
    else:
        _log(f'Binary test rc={test.returncode}: {test_out[:200]}')

    # ── Copy Vulkan DLL next to binary so it can find it ─────────────────────
    vulkan_dll = install_dir / 'vulkan-1.dll'
    if not vulkan_dll.exists():
        _log('Looking for vulkan-1.dll...')
        # Search common AMD Adrenalin / system locations
        search_paths = [
            Path('C:/Windows/System32/vulkan-1.dll'),
            Path('C:/Windows/SysWOW64/vulkan-1.dll'),
        ]
        # AMD Adrenalin installs Vulkan in its own dir
        import glob as _glob
        for pattern in [
            'C:/Program Files/AMD/CNext/CNext/vulkan-1.dll',
            'C:/Program Files*/AMD*/vulkan-1.dll',
            'C:/Windows/System32/DriverStore/FileRepository/*/vulkan-1-*.dll',
        ]:
            for p in _glob.glob(pattern):
                search_paths.append(Path(p))

        found_vulkan = None
        for p in search_paths:
            if p.exists():
                found_vulkan = p
                break

        if found_vulkan:
            try:
                _sh.copy2(str(found_vulkan), str(vulkan_dll))
                _log(f'Copied {found_vulkan.name} from {found_vulkan.parent}')
            except Exception as e:
                _log(f'Could not copy vulkan DLL: {e}')
        else:
            _log('vulkan-1.dll not found in system — Vulkan GPU may not work')
            _log('Reinstall AMD Adrenalin drivers to fix this')

    # ── Step 2: Download ggml model ───────────────────────────────────────────
    if model_path.exists():
        _log(f'Model already exists: {model_path.name}')
    else:
        model_url = (f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'
                     f'ggml-{model_size}.bin')
        _sizes = {'tiny': 75, 'base': 142, 'small': 466, 'medium': 1500}
        _log(f'Downloading ggml-{model_size}.bin (~{_sizes.get(model_size, 142)}MB)...')
        try:
            def _reporthook(count, block, total):
                if total > 0 and count % 300 == 0:
                    pct = min(100, int(count * block / total * 100))
                    _log(f'Model: {pct}%')
            _ur.urlretrieve(model_url, str(model_path), reporthook=_reporthook)
            _log(f'Model ready: {model_path.name}')
        except Exception as e:
            _log(f'Model download failed: {e}')
            return

    _log('whisper.cpp GPU transcription ready! Restart or start a new transcription.')
    _WHISPER_DEVICE_CACHE = None



# ═══ AUDIO ANALYSIS + TRANSCRIPTION ═══

def _analyze_audio_energy(video_path, ffmpeg_path, num_peaks=15):
    """
    Analyze audio energy in a video to find loud/reaction moments.
    Returns list of peak timestamps sorted by energy (highest first).
    Uses ffmpeg volumedetect + astats to find spikes.
    """
    import subprocess as _sp, re as _re, json as _js
    try:
        # Get audio stats per 1-second window using silencedetect + volumedetect
        cmd = [ffmpeg_path, '-i', video_path,
               '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
               '-f', 'null', '-']
        r = _sp.run(cmd, capture_output=True, text=True, timeout=300)
        output = r.stderr + r.stdout

        # Parse RMS levels per frame
        rms_vals = []
        for m in _re.finditer(r'pts_time:([\d.]+).*?RMS_level=([\d.-]+)', output, _re.DOTALL):
            try:
                t = float(m.group(1))
                db = float(m.group(2))
                if db > -91:  # ignore silence
                    rms_vals.append((t, db))
            except: continue

        if not rms_vals:
            # Fallback: use silencedetect to find non-silent periods
            cmd2 = [ffmpeg_path, '-i', video_path,
                   '-af', 'silencedetect=noise=-30dB:d=0.5',
                   '-f', 'null', '-']
            r2 = _sp.run(cmd2, capture_output=True, text=True, timeout=300)
            loud_times = []
            for m in _re.finditer(r'silence_end: ([\d.]+)', r2.stderr):
                loud_times.append(float(m.group(1)))
            return sorted(loud_times[:num_peaks])

        # Sort by RMS level descending, get top peaks
        rms_vals.sort(key=lambda x: x[1], reverse=True)
        # Deduplicate — keep peaks at least 10s apart
        peaks = []
        for t, db in rms_vals:
            if all(abs(t - p) > 10 for p in peaks):
                peaks.append(t)
            if len(peaks) >= num_peaks:
                break
        return sorted(peaks)

    except Exception as e:
        print(f'[CF] Audio energy analysis failed: {e}')
        return []


def _analyze_scene_changes(video_path, ffmpeg_path, threshold=0.4):
    """
    Detect scene changes using ffmpeg scene filter.
    Returns list of timestamps where scene cuts happen.
    """
    import subprocess as _sp, re as _re
    try:
        cmd = [ffmpeg_path, '-i', video_path,
               '-vf', f'select=gt(scene\\,{threshold}),metadata=print:key=lavfi.scene_score',
               '-f', 'null', '-']
        r = _sp.run(cmd, capture_output=True, text=True, timeout=300)
        output = r.stderr + r.stdout
        times = []
        for m in _re.finditer(r'pts_time:([\d.]+)', output):
            try: times.append(float(m.group(1)))
            except: continue
        return sorted(set(times))
    except Exception as e:
        print(f'[CF] Scene change analysis failed: {e}')
        return []


def _find_whispercpp():
    """Find real whisper.cpp transcription binary.
    Validates the binary actually does transcription (not talk-llama or other tools)."""
    import shutil as _sh, subprocess as _sp3
    auto_dir = _app_path('whisper_cpp')

    def _is_real_whisper(exe_path):
        """Return True if this exe is actually whisper transcription, not talk-llama etc."""
        try:
            r = _sp3.run([str(exe_path), '--help'],
                        stdout=_sp3.PIPE, stderr=_sp3.PIPE, timeout=5)
            out = ((r.stdout or b'') + (r.stderr or b'')).decode(errors='replace').lower()
            # Real whisper outputs: --language, --model, --output-json etc
            # talk-llama outputs: --speak, --tts, to_speak.txt
            if 'to_speak' in out or 'talk-llama' in out or 'tts' in out:
                print(f'[CF] Rejecting {Path(exe_path).name} — appears to be talk-llama not whisper')
                return False
            if 'server' in Path(exe_path).name.lower() and ('port' in out or 'host' in out or '--port' in out):
                print(f'[CF] Rejecting {Path(exe_path).name} — appears to be HTTP server not CLI')
                return False
            if '--language' in out or '--model' in out or 'output-json' in out or '-oj' in out:
                return True
            # Fallback: if it's big enough and not obviously wrong, try it
            return Path(exe_path).stat().st_size > 50_000  # >50KB = real binary
        except Exception:
            return False

    if auto_dir.exists():
        # Check preferred names first before scanning all candidates
        for _pref in ['whisper-whisper-cli.exe', 'whisper-cli.exe', 'main.exe']:
            _p = auto_dir / _pref
            if _p.exists() and _p.stat().st_size > 50_000 and _is_real_whisper(_p):
                return str(_p)

        # Fall back to scanning all — sort by preference (avoid known-bad names)
        BAD = ['talk-llama', 'server', 'stream', 'command', 'bench',
               'quantize', 'lsp', 'wchess', 'vad', 'test']
        candidates = sorted(
            [p for p in auto_dir.glob('*.exe')
             if p.stat().st_size > 50_000
             and not any(b in p.name.lower() for b in BAD)],
            key=lambda x: x.stat().st_size  # smallest first — whisper-cli before talk-llama
        )
        for p in candidates:
            if _is_real_whisper(p):
                return str(p)
        # Log what was rejected
        all_big = [p for p in auto_dir.glob('*.exe') if p.stat().st_size > 50_000]
        if all_big:
            print(f'[CF] No valid whisper binary. All exes: {[(p.name, p.stat().st_size//1024) for p in all_big]}')
            print('[CF] Delete whisper_cpp/ folder to force re-download')

    for name in ['whisper-whisper-cli', 'whisper-cli']:
        found = _sh.which(name)
        if found and _is_real_whisper(found):
            return found
    return None

def _find_whispercpp_model(model_size, model_dir=None):
    """Find ggml model — checks auto-install dir first."""
    model_map = {'tiny':'tiny','base':'base','small':'small','medium':'medium','large':'large-v3'}
    name = model_map.get(model_size, model_size)
    search_dirs = []
    if model_dir:
        search_dirs.append(Path(model_dir))
    search_dirs += [
        _app_path('whisper_cpp') / 'models',
        _app_path('whisper_cpp_cuda') / 'models',
        _app_path('whisper.cpp') / 'models',
        Path('C:/whisper.cpp/models'),
        Path.home() / '.cache' / 'whisper',
    ]
    for d in search_dirs:
        for pattern in [f'ggml-{name}.bin', f'ggml-{name}-q5_0.bin', f'ggml-{name}-q8_0.bin']:
            p = d / pattern
            if p.exists(): return str(p)
    return None

def _do_transcribe(vid, model_size, initial_prompt=None, ffmpeg_path=None, progress_cb=None, use_word_timestamps=False, use_gpu=True, log_cb=None):
    """Transcribe with best available backend:
    1. whisper.cpp + Vulkan (AMD/Intel/NVIDIA GPU on Windows — fastest)
    2. faster-whisper + CUDA (NVIDIA only)
    3. faster-whisper CPU int8 (always works, 4x faster than openai-whisper)
    4. openai-whisper CPU fallback
    use_gpu=False skips all GPU paths and forces CPU-only.
    """
    _ensure_pkgs_on_path()  # always check PKGS_DIR before importing whisper
    # Note: do NOT bust faster_whisper/ctranslate2/torch — busting them
    # breaks CUDA DLL initialization and causes GPU to not be detected
    import os as _os, warnings as _wn
    _wn.filterwarnings('ignore')
    _os.environ.setdefault('HF_HUB_DISABLE_IMPLICIT_TOKEN', '1')
    _os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
    _os.environ.setdefault('HF_HUB_VERBOSITY', 'error')

    # Patch ffmpeg into PATH
    if ffmpeg_path and ffmpeg_path != 'ffmpeg':
        ff_dir = str(Path(ffmpeg_path).parent)
        _os.environ['PATH'] = ff_dir + _os.pathsep + _os.environ.get('PATH', '')

    # ── Detect device ─────────────────────────────────────────────────────────
    _device_auto, _compute_auto, _dev_label_auto = _detect_whisper_device(use_gpu=use_gpu)

    # ── NVIDIA CUDA — whisper.cpp cublas binary ───────────────────────────────
    _has_nvidia = 'NVIDIA CUDA' in _dev_label_auto and use_gpu
    _wcpp_cuda_dir = _app_path('whisper_cpp_cuda')
    _wcpp_cuda_exe = _wcpp_cuda_dir / 'whisper-whisper-cli.exe'
    _has_cuda = _has_nvidia and _wcpp_cuda_exe.exists()

    # ── 1. whisper.cpp with Vulkan — AMD/Intel GPU only ──────────────────────
    _wcpp = (_find_whispercpp() if use_gpu and not _has_cuda else None)
    _wmodel = _find_whispercpp_model(model_size) if _wcpp else None

    # If NVIDIA cublas binary exists, use it instead
    if _has_cuda:
        _wcpp = str(_wcpp_cuda_exe)
        _wmodel = _find_whispercpp_model(model_size, model_dir=_wcpp_cuda_dir / 'models')
        if not _wmodel:
            _wmodel = _find_whispercpp_model(model_size)
    if _wcpp and _wmodel:
        try:
            import subprocess as _sp2, tempfile as _tf2, json as _j2, re as _re2
            print(f'[CF] whisper.cpp found: {_wcpp}')
            print(f'[CF] Whisper device: Vulkan GPU (whisper.cpp)')

            # Extract audio to wav first
            ff2 = ffmpeg_path or 'ffmpeg'
            tmp_wav = Path(_tf2.gettempdir()) / 'cf_wcpp_audio.wav'
            _sp2.run([ff2, '-y', '-i', vid, '-ar', '16000', '-ac', '1',
                      '-f', 'wav', str(tmp_wav)],
                     stdout=_sp2.PIPE, stderr=_sp2.PIPE)

            if tmp_wav.exists():
                # Output goes to same dir as wav file, named <stem>.json
                out_base = str(tmp_wav.with_suffix(''))  # no extension
                json_out = Path(out_base + '.json')

                # Build command — use -oj for JSON output (newer builds)
                cmd = [_wcpp,
                       '-m', _wmodel,
                       '-f', str(tmp_wav),
                       '-oj',
                       '--output-file', out_base,
                       '-t', '4',
                       '-bo', '5',
                       '-bs', '5',
                       '-l', 'auto',
                ]
                if initial_prompt:
                    clean_prompt = initial_prompt[:200].replace('"', "'").strip()
                    cmd += ['--prompt', clean_prompt]

                print(f'[CF] whisper.cpp cmd: {" ".join(cmd)}')
                # Use Popen to stream output for live progress
                import re as _re_wcpp, os as _os_wcpp
                # Set PATH to include whisper_cpp dir so vulkan-1.dll and ggml DLLs are found
                _wcpp_dir = str(Path(_wcpp).parent)
                _wcpp_env = dict(_os_wcpp.environ)
                _wcpp_env['PATH'] = _wcpp_dir + _os_wcpp.pathsep + _wcpp_env.get('PATH', '')
                # Also set GGML_VULKAN_DEBUG=1 temporarily to confirm GPU usage in stderr
                _wcpp_env['GGML_VULKAN_DEBUG'] = '0'  # 0=off, 1=verbose GPU info
                proc = _sp2.Popen(cmd, stdout=_sp2.PIPE, stderr=_sp2.PIPE, env=_wcpp_env)
                # Get video duration for percentage
                try:
                    import sys as _sys_cv; _sys_cv.path.insert(0, str(__import__("pathlib").Path(__file__).parent / "pkgs")) if str(__import__("pathlib").Path(__file__).parent / "pkgs") not in _sys_cv.path else None
                    import cv2 as _cv_dur
                    _cap_dur = _cv_dur.VideoCapture(vid)
                    _dur_wcpp = _cap_dur.get(_cv_dur.CAP_PROP_FRAME_COUNT) / max(_cap_dur.get(_cv_dur.CAP_PROP_FPS), 1)
                    _cap_dur.release()
                except: _dur_wcpp = 0
                stdout_lines = []
                stderr_lines = []
                _cancelled = [False]
                # Read stderr (whisper.cpp writes progress there)
                import threading as _th_wcpp
                def _read_stderr():
                    for line in proc.stderr:
                        if _cancelled[0]: break
                        decoded = line.decode(errors='replace').strip()
                        stderr_lines.append(decoded)
                        # Parse timestamp: [HH:MM:SS.mmm --> ...] or [MM:SS.mmm --> ...]
                        _tm = _re_wcpp.search(r'\[(\d+):(\d+):(\d+\.\d+)\s*-->', decoded)
                        if _tm and progress_cb and _dur_wcpp > 0:
                            hrs, mins, secs = int(_tm.group(1)), int(_tm.group(2)), float(_tm.group(3))
                            cur = hrs * 3600 + mins * 60 + secs
                            pct = min(99, int(cur / _dur_wcpp * 100))
                            dm, ds = divmod(int(cur), 60)
                            tm, ts = divmod(int(_dur_wcpp), 60)
                            progress_cb(pct, f'Transcribing (GPU)... {dm}:{ds:02d} / {tm}:{ts:02d}  ({pct}%)')
                        else:
                            _tm2 = _re_wcpp.search(r'\[(\d+):(\d+\.\d+)\s*-->', decoded)
                            if _tm2 and progress_cb and _dur_wcpp > 0:
                                mins, secs = int(_tm2.group(1)), float(_tm2.group(2))
                                cur = mins * 60 + secs
                                pct = min(99, int(cur / _dur_wcpp * 100))
                                dm, ds = divmod(int(cur), 60)
                                tm, ts = divmod(int(_dur_wcpp), 60)
                                progress_cb(pct, f'Transcribing (GPU)... {dm}:{ds:02d} / {tm}:{ts:02d}  ({pct}%)')
                def _read_stdout():
                    for line in proc.stdout:
                        if _cancelled[0]: break
                        stdout_lines.append(line.decode(errors='replace'))

                # Emulated progress timer — runs alongside real parsing as fallback
                import time as _time_wcpp
                _emu_start = _time_wcpp.time()
                def _emulate_progress():
                    while proc.poll() is None and not _cancelled[0]:
                        _time_wcpp.sleep(3)
                        if _cancelled[0]: break
                        _elapsed = _time_wcpp.time() - _emu_start
                        if _dur_wcpp > 0 and progress_cb:
                            # Estimate based on ~0.3x realtime for GPU transcription
                            _est_total = _dur_wcpp * 0.35
                            _pct = min(95, int(_elapsed / max(_est_total, 1) * 100))
                            _em, _es = divmod(int(_elapsed * (_dur_wcpp / max(_est_total, 1))), 60)
                            _tm2, _ts2 = divmod(int(_dur_wcpp), 60)
                            progress_cb(_pct, f'Transcribing (GPU)... ~{_em}:{_es:02d} / {_tm2}:{_ts2:02d}  ({_pct}%)')
                t1 = _th_wcpp.Thread(target=_read_stderr, daemon=True); t1.start()
                t2 = _th_wcpp.Thread(target=_read_stdout, daemon=True); t2.start()
                t3 = _th_wcpp.Thread(target=_emulate_progress, daemon=True); t3.start()
                # Store proc so cancel can kill it
                _active_procs = getattr(_do_transcribe, '_active_procs', [])
                _active_procs.append(proc)
                _do_transcribe._active_procs = _active_procs
                proc.wait(timeout=3600)
                _cancelled[0] = True  # stop reader threads
                _do_transcribe._active_procs = [p for p in _active_procs if p != proc]
                t1.join(timeout=3); t2.join(timeout=3)
                stderr_txt = '\n'.join(stderr_lines)
                stdout_txt = '\n'.join(stdout_lines)

                # Log whisper.cpp output to ClipFinder log for debugging
                if stderr_txt.strip():
                    if log_cb:
                        for _line in stderr_txt.split('\n')[:20]:  # first 20 lines
                            if _line.strip():
                                log_cb(f'[whisper.cpp] {_line}', FG3)
                    else:
                        print(f'[CF] whisper.cpp stderr:\n{stderr_txt[:800]}')

                if progress_cb and any('[' in l and '-->' in l for l in stderr_lines):
                    progress_cb(99, 'Finalising transcript...')

                # Detect if Vulkan GPU actually ran — must see device detection AND actual transcription
                _vulkan_device = 'ggml_vulkan: found' in stderr_txt.lower() or 'ggml_vulkan: 0 =' in stderr_txt.lower()
                _actually_ran = any('[' in l and '-->' in l for l in stderr_lines)
                _error_exit = 'error: unknown argument' in stderr_txt or 'usage:' in stderr_txt
                _vulkan_used = _vulkan_device and _actually_ran and not _error_exit
                _gpu_fallback = not _vulkan_used
                if _gpu_fallback and log_cb:
                    log_cb('ℹ whisper.cpp GPU status unknown — check Task Manager for GPU usage', FG2)
                elif _vulkan_used and log_cb:
                    log_cb('✅ Vulkan GPU confirmed active', GREEN)
                class _FakeResult:
                    returncode = proc.returncode
                r = _FakeResult()

                # whisper.cpp sometimes writes <file>.wav.json instead of <file>.json
                if not json_out.exists():
                    alt = Path(str(tmp_wav) + '.json')
                    if alt.exists(): json_out = alt
                # Or it may print JSON to stdout
                if not json_out.exists() and stdout_txt.strip().startswith('{'):
                    json_out.write_text(stdout_txt, encoding='utf-8')

                if json_out.exists():
                    data = _j2.loads(json_out.read_text(encoding='utf-8'))
                    segments = []
                    for seg in data.get('transcription', []):
                        start_ms = seg.get('offsets', {}).get('from', 0)
                        end_ms   = seg.get('offsets', {}).get('to', 0)
                        text     = seg.get('text', '').strip()
                        sd = {
                            'start': start_ms / 1000.0,
                            'end':   end_ms   / 1000.0,
                            'text':  text,
                        }
                        if use_word_timestamps and seg.get('tokens'):
                            sd['words'] = [
                                {'word': t.get('text',''), 'start': t.get('offsets',{}).get('from',0)/1000,
                                 'end': t.get('offsets',{}).get('to',0)/1000}
                                for t in seg.get('tokens', []) if t.get('text','').strip()
                            ]
                        segments.append(sd)
                    try: tmp_wav.unlink()
                    except: pass
                    try: json_out.unlink()
                    except: pass
                    if progress_cb:
                        progress_cb(100, f'whisper.cpp done: {len(segments)} segments')
                    print(f'[CF] whisper.cpp done: {len(segments)} segments')
                    return {'segments': segments, 'language': 'en'}
                else:
                    rc = r.returncode
                    print(f'[CF] whisper.cpp failed (rc={rc})')
                    print(f'[CF]   stderr: {stderr_txt[-300:]}')
                    print(f'[CF]   stdout: {stdout_txt[:200]}')

                    # Build cmd without --no-prints for all retries
                    cmd_clean = [c for c in cmd if c != '--no-prints']

                    if rc == 3221225781 or rc == -1073741819:
                        print('[CF] STATUS_ACCESS_VIOLATION — missing Vulkan DLL')
                        _wcpp_dir = Path(_wcpp).parent
                        _vulkan_dst = _wcpp_dir / 'vulkan-1.dll'
                        if not _vulkan_dst.exists():
                            import glob as _gl2, shutil as _sh2
                            _vp_candidates = [
                                'C:/Windows/System32/vulkan-1.dll',
                                'C:/Program Files/AMD/CNext/CNext/vulkan-1.dll',
                                'C:/Program Files (x86)/AMD/CNext/CNext/vulkan-1.dll',
                            ] + list(_gl2.glob('C:/Windows/System32/DriverStore/FileRepository/*/vulkan-1-999-0-0-0.dll'))
                            for _vp in _vp_candidates:
                                if Path(_vp).exists():
                                    try:
                                        _sh2.copy2(_vp, str(_vulkan_dst))
                                        print(f'[CF] Copied vulkan-1.dll from {_vp}')
                                    except Exception as _ve:
                                        print(f'[CF] Copy failed: {_ve}')
                                    break
                        # Retry after DLL copy
                        if _vulkan_dst.exists():
                            print('[CF] Retrying with Vulkan DLL in place...')
                            r3 = _sp2.run(cmd_clean, stdout=_sp2.PIPE, stderr=_sp2.PIPE, timeout=3600)
                            stderr3 = (r3.stderr or b'').decode(errors='replace')
                            stdout3 = (r3.stdout or b'').decode(errors='replace')
                            print(f'[CF] Vulkan retry rc={r3.returncode}')
                            if r3.returncode == 0 and json_out.exists():
                                # Success! Parse and return
                                _data3 = _j2.loads(json_out.read_text(encoding='utf-8'))
                                segments = []
                                for _seg in _data3.get('transcription', []):
                                    _s = _seg.get('offsets',{}).get('from',0)
                                    _e = _seg.get('offsets',{}).get('to',0)
                                    segments.append({'start':_s/1000.0,'end':_e/1000.0,
                                                    'text':_seg.get('text','').strip()})
                                print(f'[CF] whisper.cpp GPU success! {len(segments)} segments')
                                try: tmp_wav.unlink()
                                except: pass
                                try: json_out.unlink()
                                except: pass
                                return {'segments': segments, 'language': 'en'}
                            else:
                                print(f'[CF] Still failing after DLL copy (rc={r3.returncode})')
                                print(f'[CF] stderr: {stderr3[-300:]}')
                                dlls = list(_wcpp_dir.glob('*.dll'))
                                print(f'[CF] DLLs in whisper_cpp/: {[d.name for d in dlls]}')
                        else:
                            print('[CF] vulkan-1.dll not found on system — cannot auto-fix')

                    # Standard retry without --no-prints
                    # Retry with --output-json fallback (older builds)
                    if '-oj' in cmd:
                        print('[CF] Retrying without --no-prints flag...')
                        cmd_fallback = [c if c != '-oj' else '--output-json' for c in cmd_clean]
                        r2 = _sp2.run(cmd_fallback, stdout=_sp2.PIPE, stderr=_sp2.PIPE, timeout=3600)
                        if json_out.exists() and json_out.stat().st_size > 10:
                            data = _j2.loads(json_out.read_text(encoding='utf-8'))
                            segments = []
                            for seg in data.get('transcription', []):
                                start_ms = seg.get('offsets',{}).get('from',0)
                                end_ms   = seg.get('offsets',{}).get('to',0)
                                segments.append({
                                    'start': start_ms/1000.0,
                                    'end':   end_ms/1000.0,
                                    'text':  seg.get('text','').strip()
                                })
                            print(f'[CF] whisper.cpp retry succeeded: {len(segments)} segments')
                            return {'segments': segments, 'language': 'en'}
                        print(f'[CF] Retry also failed: {(r2.stderr or b"").decode(errors="replace")[-200:]}')
        except Exception as _wcpp_err:
            print(f'[CF] whisper.cpp error: {_wcpp_err}, falling back...')
    elif _wcpp and not _wmodel:
        print(f'[CF] whisper.cpp: no ggml-{model_size}.bin — downloading now...')
        try:
            import urllib.request as _ur2, threading as _thr2
            _models_dir = _app_path('whisper_cpp', 'models')
            _models_dir.mkdir(parents=True, exist_ok=True)
            _model_dst  = _models_dir / f'ggml-{model_size}.bin'
            _model_url  = (f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/'
                          f'ggml-{model_size}.bin')
            _sizes = {'tiny':75,'base':142,'small':466,'medium':1500,'large':3100}
            print(f'[CF] Downloading ggml-{model_size}.bin (~{_sizes.get(model_size,"?")}MB)...')
            if progress_cb: progress_cb(0, f'Downloading ggml-{model_size}.bin...')
            _last_model_pct = [-1]
            def _hook(c, b, t):
                if t > 0:
                    pct = int(c*b/t*100)
                    if pct >= _last_model_pct[0] + 10 or pct >= 99:
                        _last_model_pct[0] = pct
                        print(f'[CF] Model download: {pct}%')
                        if progress_cb: progress_cb(pct, f'Downloading ggml model: {pct}%')
            _ur2.urlretrieve(_model_url, str(_model_dst), reporthook=_hook)
            print(f'[CF] Downloaded: {_model_dst.name}')
            # Re-find model and retry
            _wmodel = str(_model_dst)
        except Exception as _mdl_err:
            print(f'[CF] Model download failed: {_mdl_err}')

    # ── 2. faster-whisper with CUDA/CPU ───────────────────────────────────────
    try:
        _FW = _fresh_import('faster_whisper').WhisperModel
        device, compute_type, device_label = _detect_whisper_device(use_gpu=use_gpu)
        print(f'[CF] Whisper device: {device_label}')

        if device == 'directml':
            # faster-whisper doesn't support DirectML — use openai-whisper + torch-directml
            raise RuntimeError('directml: route to openai-whisper+directml')

        # Verify ctranslate2 actually supports CUDA before trying
        if device == 'cuda':
            try:
                import ctranslate2 as _ct2
                _ct2_cuda = 'cuda' in _ct2.get_supported_compute_types('cuda')
                if not _ct2_cuda:
                    if log_cb: log_cb('⚠ CUDA not available — using CPU. Go to Settings → Install NVIDIA CUDA Support.', YELLOW)
                    device, compute_type = 'cpu', 'int8'
            except Exception as _ct2e:
                if log_cb: log_cb(f'⚠ ctranslate2 check failed ({_ct2e}) — using CPU', YELLOW)
                device, compute_type = 'cpu', 'int8'

        fw_model = None
        try:
            fw_model = _FW(
                model_size,
                device=device,
                compute_type=compute_type,
                num_workers=2,
                cpu_threads=0,
                download_root=str(_app_path('whisper_models')),
            )
            print(f'[CF] faster-whisper loaded on {device} ({compute_type})')
            if log_cb: log_cb(f'✅ Transcribing on {device_label}', GREEN)
        except Exception as _cuda_err:
            if device == 'cuda':
                print(f'[CF] CUDA load failed ({_cuda_err}) — falling back to CPU int8')
                if log_cb: log_cb('⚠ CUDA failed to load — falling back to CPU. Re-install CUDA torch in Settings.', YELLOW)
                # Reset device cache so next run re-detects
                global _WHISPER_DEVICE_CACHE
                _WHISPER_DEVICE_CACHE = None
                fw_model = _FW(
                    model_size, device='cpu', compute_type='int8',
                    num_workers=2, cpu_threads=0,
                    download_root=str(_app_path('whisper_models')),
                )
            else:
                raise

        # Get video duration for progress calculation
        try:
            _cv2t = _fresh_import('cv2')
            _cap = _cv2t.VideoCapture(vid)
            _dur = _cap.get(_cv2t.CAP_PROP_FRAME_COUNT) / max(_cap.get(_cv2t.CAP_PROP_FPS) or 30, 1)
            _cap.release()
        except Exception:
            _dur = 0

        segs_iter, info = fw_model.transcribe(
            vid,
            initial_prompt=initial_prompt or '',
            word_timestamps=use_word_timestamps,
            vad_filter=True,
            vad_parameters={
                'min_silence_duration_ms': 400,
                'speech_pad_ms': 200,
            },
            beam_size=5,
            best_of=5,
            temperature=0.0,
        )

        # Consume iterator and report progress
        segments = []
        for seg in segs_iter:
            # Check cancel flag (set by _cancel_task via _do_transcribe._cancelled)
            if getattr(_do_transcribe, '_cancelled', False):
                _do_transcribe._cancelled = False
                return {'segments': segments, 'language': getattr(info, 'language', 'en'), '_cancelled': True}
            sd = {'start': seg.start, 'end': seg.end, 'text': seg.text}
            if use_word_timestamps and seg.words:
                sd['words'] = [{'word': w.word, 'start': w.start, 'end': w.end} for w in seg.words]
            segments.append(sd)
            if progress_cb and _dur > 0:
                pct = min(99, int((seg.end / _dur) * 100))
                m, s = divmod(int(seg.end), 60)
                progress_cb(pct, f'Transcribing... {m}:{s:02d} / {int(_dur//60)}:{int(_dur%60):02d}  ({pct}%)')
            elif progress_cb:
                progress_cb(None, f'Transcribing... {len(segments)} segments found')

        print(f'[CF] Whisper done: {len(segments)} segments, lang={info.language}')
        return {'segments': segments, 'language': info.language}

    except Exception as fw_err:
        print(f'[CF] faster-whisper error: {fw_err}')
        print('[CF] Falling back to openai-whisper...')

    # ── Fallback: openai-whisper, with DirectML if available ────────────────
    try:
        import whisper as _w
    except ImportError:
        raise RuntimeError(
            'No transcription engine available.\n\n'
            'Go to Settings → Update Modules and install:\n'
            '  • faster-whisper  (recommended)\n'
            '  • openai-whisper  (fallback)\n\n'
            'The app will stay open while packages download.'
        )
    with _wn.catch_warnings():
        _wn.simplefilter('ignore')
        # Try to load on DirectML (AMD/Intel GPU via torch-directml)
        _device_str = 'cpu'
        try:
            import torch_directml as _dml2
            if _dml2.device_count() > 0:
                _device_str = _dml2.device(0)
                print(f'[CF] Whisper using DirectML GPU')
        except Exception:
            pass

        _ow_model = model_size if model_size not in ('auto', '') else 'base'
        model = _w.load_model(_ow_model, device=_device_str)

    if ffmpeg_path:
        try:
            import whisper.audio as _wa
            _wa.FFMPEG_PATH = ffmpeg_path
        except Exception: pass

    opts = {'verbose': False, 'word_timestamps': use_word_timestamps, 'fp16': False}
    if initial_prompt:
        opts['initial_prompt'] = initial_prompt
    with _wn.catch_warnings():
        _wn.simplefilter('ignore')
        result = model.transcribe(vid, **opts)
        raw_segs = result.get('segments', [])
        out_segs = []
        for seg in raw_segs:
            sd = {'start': seg['start'], 'end': seg['end'], 'text': seg['text'].strip()}
            if use_word_timestamps and seg.get('words'):
                sd['words'] = [{'word': w['word'], 'start': w['start'], 'end': w['end']}
                               for w in seg['words']]
            out_segs.append(sd)
        return {'segments': out_segs, 'language': result.get('language','en')}

