

https://github.com/user-attachments/assets/2011c855-78d7-440b-9c39-f9a59e2b2f6b

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

Run the local development tests before installing:

```bash
python3 tests/run_tests.py
```

Install HeyGhost and all default runtime dependencies with one command:

```bash
sudo ./install.sh
```

The installer installs system packages, Ollama, default Ollama models, whisper.cpp, Whisper models, Piper, the default Piper voice, the Python virtual environment, the `heyghost` command, the systemd service, and a desktop launcher icon. It also runs post-install checks so the user knows whether the installation is usable. By default HeyGhost listens continuously, opens the GhostWave GUI fullscreen from the desktop icon, and shows the active Ollama model on the GUI.

Useful installer options:

```bash
sudo ./install.sh --skip-tests
sudo ./install.sh --skip-desktop-icon
sudo ./install.sh --ollama-model llama3.2:1b
```

All dependency installation now lives in `install.sh`, so new users only need one installer command.

Manual Ollama model installation:

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
heyghost doctor
```

Trigger a manual listening session:

```bash
heyghost trigger
```

Open the debug UI:

```bash
heyghost debug-window
```

Run a local install diagnostic:

```bash
heyghost doctor
```

## How To Use HeyGhost

After installation, HeyGhost can be used in three main ways:

| Mode | Command | Best For |
| --- | --- | --- |
| Background service | `heyghost start` | Daily use after setup. |
| Manual trigger | `heyghost trigger` | Testing the assistant without wake-word tuning. |
| Visual desktop mode | Double-click the HeyGhost desktop icon or run `heyghost desktop` | Seeing transcripts, state, and responses in the GhostWave UI. |

The desktop icon opens the GhostWave GUI. Click inside the window or press Space to start a listening session. If the icon does not open, check `~/.local/state/heyghost/desktop-launch.log` for the launch error.

Basic flow:

1. Start the service:

   ```bash
   heyghost start
   ```

2. Trigger a listening session:

   ```bash
   heyghost trigger
   ```

3. Speak a short request clearly.

4. HeyGhost transcribes, routes, answers, and speaks the response locally.

5. Check service status or logs if something does not work:

   ```bash
   heyghost status
   journalctl -u hey-ghost.service -f
   ```

## Example Questions And Voice Commands

Use short, direct phrases for the best response time. These examples show the type of things HeyGhost is designed to handle.

### System Information

| Ask HeyGhost | What It Does |
| --- | --- |
| `what time is it` | Speaks the current local time. |
| `how much memory do I have` | Reports RAM information. |
| `which CPU is this` | Reports processor information. |
| `show disk space` | Reports disk usage. |
| `what operating system is running` | Reports OS details. |
| `system status` | Gives a short system status summary. |
| `what USB devices are connected` | Lists visible USB devices. |
| `what is my IP address` | Reports active network interface addresses. |

### Linux And Desktop Helpers

| Ask HeyGhost | What It Does |
| --- | --- |
| `open terminal` | Opens a terminal action through the desktop flow. |
| `open browser` | Opens the default browser. |
| `open google dot com` | Opens a website. |
| `search the web for local AI tools` | Opens a web search. |
| `open file manager` | Opens the default file manager if available. |
| `open calculator` | Opens a calculator app if installed. |
| `what Linux tools are installed` | Summarizes common visible command-line tools. |

### Local AI And Model Questions

| Ask HeyGhost | What It Does |
| --- | --- |
| `which model are you using` | Reports the configured Ollama model. |
| `what can you do` | Summarizes assistant capabilities. |
| `show your LLM capabilities` | Lists local model-assisted features. |
| `make that shorter` | Shortens the previous assistant response. |
| `explain that result` | Explains the previous local skill result. |
| `classify this request: open browser` | Demonstrates local request classification. |

### Local Knowledge And RAG

After adding documents to the configured knowledge directory and running `heyghost index-rag`, you can ask source-backed local document questions.

| Ask HeyGhost | What It Does |
| --- | --- |
| `search your local knowledge for USB microphone` | Searches indexed local documents. |
| `search local knowledge for install notes` | Looks for matching local notes. |
| `search your local knowledge for Ollama setup` | Answers from local indexed files when sources exist. |

Refresh the local knowledge index:

```bash
heyghost index-rag
```

### Educational Topics

HeyGhost includes local answer banks and domain routing for short educational explanations.

| Ask HeyGhost | What It Does |
| --- | --- |
| `what is cybersecurity` | Gives a defensive educational explanation. |
| `what is phishing` | Explains the concept safely. |
| `how do I make SSH safer` | Gives defensive security guidance. |
| `what is yoga` | Gives a short wellness explanation. |
| `give me a beginner yoga tip` | Gives general wellness guidance. |
| `what is robotics` | Explains robotics at a high level. |

### Debugging And Testing Commands

These are terminal commands, not voice questions:

| Command | Purpose |
| --- | --- |
| `heyghost test-ollama` | Tests the local Ollama connection. |
| `heyghost test-tts` | Tests Piper speech output. |
| `heyghost debug-window` | Opens the GhostWave diagnostics window. |
| `heyghost replay tests/fixtures/transcripts.jsonl` | Replays transcript fixtures through routing. |
| `python3 tests/run_tests.py` | Runs the lightweight test suite. |

### Tips For Better Results

- Keep voice commands short and specific.
- Use the manual trigger while testing your microphone and models.
- Start with `qwen2.5:0.5b` on low-power hardware.
- Use `heyghost status` and `journalctl -u hey-ghost.service -f` when debugging.
- Keep cybersecurity requests defensive, educational, and authorized.
- Do not expect HeyGhost to run arbitrary LLM-generated shell commands; that is intentionally blocked for safety.

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

Linux audio hardware varies a lot between laptops, mini PCs, USB microphones, HDMI audio, Bluetooth devices, PipeWire, PulseAudio, and plain ALSA setups. HeyGhost ships with `null` audio devices by default so PortAudio can use the system defaults, but some devices need extra microphone or speaker configuration before voice input and TTS playback work correctly.

Start with the built-in diagnostic:

```bash
heyghost doctor
```

If `audio input` or `audio output` fails, inspect the devices visible to Linux:

```bash
python3 -m sounddevice
arecord -l
arecord -L
aplay -l
aplay -L
```

Then edit `/etc/hey-ghost/config.yaml` for an installed service, or edit your local `config.yaml` when running from a clone:

```yaml
audio:
  input_device: null
  output_device: null
```

For PortAudio devices, use the numeric device ID shown by `python3 -m sounddevice`:

```yaml
audio:
  input_device: 3
  output_device: 5
```

For ALSA devices, use the ALSA name shown by `arecord -L` or `aplay -L`:

```yaml
audio:
  input_device: "plughw:CARD=sofhdadsp,DEV=6"
  output_device: "plughw:CARD=sofhdadsp,DEV=31"
```

Common symptoms and fixes:

| Symptom | What To Check |
| --- | --- |
| HeyGhost hears nothing | Confirm the mic is not muted, run `arecord -l`, then set `audio.input_device`. |
| TTS creates text but no sound plays | Run `heyghost test-tts`, check `aplay -L`, then set `audio.output_device`. |
| `heyghost doctor` says the mic is busy | Stop the service with `heyghost stop`, test the device, then start it again. |
| Built-in laptop mic fails but USB mic works | Use the USB mic device ID or ALSA name explicitly. |
| HDMI or Bluetooth becomes the default speaker | Set the speaker device explicitly instead of relying on `null`. |
| Speech is clipped or missed | Increase `audio.max_record_seconds` or `audio.silence_timeout_ms`. |
| Background noise triggers false speech | Increase `audio.vad_aggressiveness` or use a quieter microphone. |

After changing audio settings, restart the service:

```bash
heyghost restart
heyghost doctor
```

If you are preparing a public release or installing HeyGhost on a new machine, do not assume the laptop-specific values from another computer will work. Keep `config.example.yaml` generic, then document any working hardware-specific values in your own deployment notes.

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

## Acknowledgements

HeyGhost is possible because of excellent open-source and local-first AI projects. Special thanks to:

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) and OpenAI Whisper for local speech-to-text.
- [Piper](https://github.com/rhasspy/piper) for fast local text-to-speech.
- [Ollama](https://ollama.com/) for making local LLMs easy to run and test.
- [WebRTC VAD](https://github.com/wiseman/py-webrtcvad) for lightweight voice activity detection.
- [SoundDevice](https://python-sounddevice.readthedocs.io/) and PortAudio for microphone/audio integration.
- [PyYAML](https://pyyaml.org/) for configuration loading.
- The Python and Linux open-source communities that make local assistant projects like this practical.

These projects belong to their respective authors and maintainers. HeyGhost integrates with them but is not affiliated with or endorsed by them.

## License

HeyGhost is released under the [MIT License](LICENSE).
