# HeyGhost

**HeyGhost** is a local-first Linux voice assistant built for users who want a private, hackable assistant that runs on their own hardware. It uses local speech-to-text, local Ollama models, local Piper text-to-speech, deterministic Python skills, and a systemd service so it can run as a native Linux background assistant.

Repository: <https://github.com/GhostRedRecon/HeyGhost>

> Educational use only: HeyGhost is for learning, research, and authorized personal automation. Do not use this project for hacking, unauthorized access, credential theft, malware activity, network abuse, or illegal activity. Cybersecurity-related features and responses must remain defensive, educational, and authorized.

## Highlights

- Local-first voice assistant for Linux.
- No cloud API required for the core voice loop.
- Speech-to-text through `whisper.cpp`.
- LLM responses through local Ollama models.
- Text-to-speech through Piper.
- Native systemd service installation.
- Tkinter GhostWave debug interface.
- Deterministic local skills for system information and common desktop actions.
- Local RAG over your own documents using Ollama embeddings.
- Public-safe defaults with no voice aliases for offensive tooling.
- Lightweight test suite for development and regression checks.

## What HeyGhost Can Do

- Listen through a manual trigger or a configurable wake-word backend.
- Record microphone audio and detect speech with VAD.
- Transcribe speech locally.
- Answer system questions about time, CPU, memory, disk, OS, hardware, USB devices, IP address, and visible Wi-Fi information.
- Open safe desktop apps, browser pages, websites, and web searches.
- Route known commands through local Python skills before using the LLM.
- Use Ollama for concise fallback responses.
- Speak responses with local TTS.
- Index local documents and answer with source-backed RAG.
- Show runtime diagnostics through the GhostWave UI.

The LLM output is treated as text only. It does not directly execute shell commands.

## Supported Operating Systems

HeyGhost is designed for Linux.

| Platform | Status | Notes |
| --- | --- | --- |
| Kali Linux | Primary target | Best tested target for this project. |
| Debian 12+ | Supported | `install.sh` uses `apt-get` and systemd. |
| Ubuntu 22.04+ / 24.04+ | Supported | Install flow should work with equivalent audio packages. |
| Raspberry Pi OS 64-bit | Experimental | Use smaller models and lightweight STT/TTS settings. |
| Fedora / Arch / other Linux | Manual setup | Install equivalent packages manually; systemd is still expected. |
| macOS / Windows | Not supported | WSL may work for development, but audio/service behavior is not a target. |

## Hardware Guidance

HeyGhost can run on modest Linux hardware, but model choice matters.

| Hardware | Suggested Ollama model | Expected behavior |
| --- | --- | --- |
| Raspberry Pi 5 / low-power ARM, 4-8 GB RAM | `qwen2.5:0.5b` | Fastest option, best for short commands and simple answers. |
| Intel N100 / mini PC, 8-16 GB RAM | `qwen2.5:0.5b`, `llama3.2:1b`, `gemma3:1b` | Good voice-assistant latency with short responses. |
| Laptop/desktop CPU, 16 GB RAM | `llama3.2:1b`, `gemma3:1b`, `qwen2.5:1.5b` | Better answer quality while staying practical on CPU. |
| Modern CPU or GPU, 16-32 GB+ RAM | Larger Ollama models | Better quality, but slower and more power hungry. |

Recommended default: `qwen2.5:0.5b` because it is small and responsive for voice use. For better quality, try `llama3.2:1b`, `gemma3:1b`, or `qwen2.5:1.5b` and benchmark on your own device.

Run the included benchmark helper:

```bash
python3 scripts/benchmark_latency.py --config config.yaml --models qwen2.5:0.5b llama3.2:1b gemma3:1b
```

## Architecture

```text
microphone
  -> audio recorder + VAD
  -> whisper.cpp STT
  -> transcript filter
  -> local skill router
  -> domain catalog / RAG / Ollama fallback
  -> response policy guard
  -> Piper TTS
  -> speaker output
```

Main directories:

```text
heyghost.py                 CLI entry point
config.yaml                 Public-safe default config
config.example.yaml         Copyable config template
install.sh                  Linux installer
uninstall.sh                Linux uninstaller
requirements.txt            Python dependencies
heyghost/audio/             Audio input, output, recorder, VAD
heyghost/stt/               STT integrations and transcript cleanup
heyghost/tts/               Piper TTS integration
heyghost/wake/              Manual and wake-word backends
heyghost/llm/               Ollama client and LLM helper layers
heyghost/rag/               Local document retrieval
heyghost/skills/            Local skills and action routing
heyghost/gui/               Tkinter UI components
scripts/                    Smoke tests and benchmark helpers
systemd/                    Example service unit
tests/                      Lightweight test suite
```

## Dependencies

System packages installed by `install.sh` on Debian/Kali/Ubuntu systems:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  build-essential \
  portaudio19-dev \
  ffmpeg \
  alsa-utils
```

Python packages from `requirements.txt`:

- `PyYAML`
- `sounddevice`
- `setuptools<82`
- `webrtcvad`

External local runtimes:

- Ollama for local LLM generation.
- `whisper.cpp` for local STT.
- Piper for local TTS.
- Optional `openwakeword` if you enable an OpenWakeWord backend.

Default runtime paths:

```text
/opt/hey-ghost/bin/whisper-cli
/opt/hey-ghost/models/whisper/ggml-tiny.en.bin
/opt/hey-ghost/models/whisper/ggml-base.en.bin
/opt/hey-ghost/bin/piper
/opt/hey-ghost/models/piper/en_US-lessac-medium.onnx
```

These paths are configurable with environment variables and `config.yaml`.

## Installation

Clone the repository:

```bash
git clone https://github.com/GhostRedRecon/HeyGhost.git
cd HeyGhost
```

Run the tests before installing:

```bash
python3 tests/run_tests.py
```

Install HeyGhost as a system service:

```bash
sudo ./install.sh
```

Install Ollama models:

```bash
ollama pull qwen2.5:0.5b
ollama pull nomic-embed-text
```

Optional quality models:

```bash
ollama pull llama3.2:1b
ollama pull gemma3:1b
ollama pull qwen2.5:1.5b
```

Install or build `whisper.cpp`, then place or symlink the binary and models to the configured paths. Install Piper and place or symlink the Piper binary and voice model to the configured paths.

Start HeyGhost:

```bash
heyghost start
heyghost status
```

Trigger a manual listening session:

```bash
heyghost trigger
```

Open the debug UI:

```bash
heyghost debug-window
```

## Configuration

The config loader checks paths in this order:

1. `--config /path/to/config.yaml`
2. `HEY_GHOST_CONFIG`
3. `./config.yaml`
4. `${HEY_GHOST_CONFIG_ROOT:-/etc/hey-ghost}/config.yaml`

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HEY_GHOST_INSTALL_ROOT` | `/opt/hey-ghost` | Runtime install directory. |
| `HEY_GHOST_CONFIG_ROOT` | `/etc/hey-ghost` | Installed config directory. |
| `HEY_GHOST_LOG_DIR` | `/var/log/hey-ghost` | Service log directory. |
| `HEY_GHOST_CONFIG` | unset | Explicit config file path. |
| `HEY_GHOST_OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama generate endpoint. |

Example custom install root:

```bash
sudo HEY_GHOST_INSTALL_ROOT=/srv/heyghost ./install.sh
```

## Audio Setup

The default config uses `null` devices so PortAudio can use system defaults. If your microphone or speaker is not selected correctly, list devices:

```bash
python3 -m sounddevice
aplay -l
```

Then edit `/etc/hey-ghost/config.yaml` or your local `config.yaml`:

```yaml
audio:
  input_device: null
  output_device: null
```

Use explicit device IDs only when needed.

## CLI Commands

```bash
heyghost run
heyghost start
heyghost stop
heyghost restart
heyghost status
heyghost trigger
heyghost test-tts
heyghost test-ollama
heyghost index-rag
heyghost debug-window
heyghost desktop
heyghost replay tests/fixtures/transcripts.jsonl
```

## Development

Run tests:

```bash
python3 tests/run_tests.py
```

Run without installing the service:

```bash
python3 heyghost.py --config config.yaml run
```

Run the debug window from the clone:

```bash
python3 heyghost.py --config config.yaml debug-window
```

Run latency benchmarks:

```bash
python3 scripts/benchmark_latency.py --config config.yaml
```

## Security And Safety

- HeyGhost is educational software for authorized systems only.
- The LLM never directly executes shell commands.
- Local actions are explicit Python code paths.
- The public build does not include voice aliases that launch offensive tools.
- Risky manual GUI console commands require typed confirmation.
- Cybersecurity answers should stay defensive and authorized.
- Health and yoga answers are general wellness information, not medical diagnosis.
- The response policy blocks unverified LLM claims about local system status.

See [SECURITY.md](SECURITY.md) for reporting and safe-use guidance.

## Contributing

Contributions are welcome if they keep the project local-first, safe, and easy to install. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Support The Project

If HeyGhost helps you, you can support development here:

[Buy me a coffee](https://buymeacoffee.com/navnish)

## License

HeyGhost is released under the [MIT License](LICENSE).
