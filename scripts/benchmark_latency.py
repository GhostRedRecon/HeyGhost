#!/usr/bin/env python3
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from heyghost.config import load_config
from heyghost.llm.ollama_client import OllamaClient
from heyghost.routing import TurnRouter
from heyghost.skills.registry import SkillRegistry

MODEL_BENCHMARK_PROMPTS = (
    "What is yoga?",
    "What is phishing?",
    "Explain Linux networking in one sentence.",
    "What is a firewall?",
    "What is ransomware?",
    "Give one safe password tip.",
    "What is two factor authentication?",
    "What is a CPU?",
    "What is RAM?",
    "How should I stretch safely?",
)


def elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 1)


def build_llm(config, model: str) -> OllamaClient:
    return OllamaClient(
        url=config.llm.url,
        model=model,
        num_ctx=config.llm.num_ctx,
        num_predict=config.llm.num_predict,
        temperature=config.llm.temperature,
        max_response_words=config.assistant.max_response_words,
        keep_alive=config.llm.keep_alive,
    )


def benchmark_models(config, models: list[str]) -> None:
    system_prompt = "You are Ghost. Answer in one short sentence."
    results = []
    for model in models:
        llm = build_llm(config, model)
        timings = []
        failures = 0
        print(f"\nmodel={model}")
        for index, prompt in enumerate(MODEL_BENCHMARK_PROMPTS, start=1):
            started = time.perf_counter()
            try:
                response = llm.generate(system_prompt, prompt, "")
                ms = elapsed_ms(started)
                ok = bool(response.strip())
            except Exception as exc:
                ms = elapsed_ms(started)
                response = f"ERROR: {exc}"
                ok = False
            if ok:
                timings.append(ms)
            else:
                failures += 1
            print(f"  {index:02d}. {ms:8.1f} ms ok={ok} prompt={prompt!r} response={response!r}")
        if timings:
            avg_ms = statistics.mean(timings)
            median_ms = statistics.median(timings)
            max_ms = max(timings)
        else:
            avg_ms = median_ms = max_ms = float("inf")
        results.append((model, failures, avg_ms, median_ms, max_ms))
        print(
            f"summary model={model} failures={failures} "
            f"avg_ms={avg_ms:.1f} median_ms={median_ms:.1f} max_ms={max_ms:.1f}"
        )

    acceptable = [item for item in results if item[1] == 0]
    if not acceptable:
        print("\nrecommendation=none all benchmarked models had failures")
        return
    fastest = min(acceptable, key=lambda item: item[2])
    print(
        "\nrecommendation="
        f"{fastest[0]} fastest acceptable avg_ms={fastest[2]:.1f} "
        f"median_ms={fastest[3]:.1f} max_ms={fastest[4]:.1f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark HeyGhost local latency")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--wav", help="Optional WAV file to benchmark STT")
    parser.add_argument(
        "--benchmark-models",
        action="store_true",
        help="Benchmark qwen2.5:0.5b, gemma3:1b, and llama3.2:1b with the same 10 prompts",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5:0.5b", "gemma3:1b", "llama3.2:1b"],
        help="Ollama models to benchmark when --benchmark-models is set",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.benchmark_models:
        benchmark_models(config, args.models)
        return 0

    if args.wav:
        from heyghost.stt.profiles import build_whisper_stt

        stt = build_whisper_stt(config.stt, config.stt.active_profile)
        start = time.perf_counter()
        transcript = stt.transcribe(args.wav)
        print(f"stt_ms={elapsed_ms(start)} text={transcript.text!r}")
    else:
        print("stt_ms=skipped pass --wav path/to/audio.wav")

    router = TurnRouter(SkillRegistry(llm_model=config.llm.model))
    start = time.perf_counter()
    route = router.route("what is phishing")
    print(f"router_ms={elapsed_ms(start)} route={route.route} handled={route.handled}")

    llm = build_llm(config, config.llm.model)
    start = time.perf_counter()
    response = llm.generate("You are Ghost. Answer in one short sentence.", "What is yoga?", "")
    print(f"llm_ms={elapsed_ms(start)} response={response!r}")

    from heyghost.audio.output import AudioOutput
    from heyghost.tts.piper import PiperTTS

    tts = PiperTTS(
        binary_path=config.tts.binary_path,
        model_path=config.tts.model_path,
        output_wav_path=config.tts.speaker_wav_path,
        audio_output=AudioOutput(device=config.audio.output_device),
        length_scale=config.tts.length_scale,
        sentence_silence=config.tts.sentence_silence,
    )
    start = time.perf_counter()
    tts.speak("HeyGhost benchmark complete.")
    print(f"tts_ms={elapsed_ms(start)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
