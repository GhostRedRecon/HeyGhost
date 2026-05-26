from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from heyghost.logger import configure_logging
from heyghost.response_policy import guard_llm_response
from heyghost.routing import TurnRouter
from heyghost.state import AssistantState
from heyghost.stt.types import Transcript

if TYPE_CHECKING:
    from heyghost.config import AppConfig


SYSTEM_PROMPT = (
    'You are Ghost, a fast local voice assistant running on a small Intel N100 '
    'Linux device. Speak naturally, warmly, and briefly. Usually answer in one or two short '
    'sentences. Do not use lists, bullets, or numbered answers unless the user asks. '
    'Reply in the same language the user uses. You can respond in English, Spanish, '
    'or Chinese. If the user mixes languages, use the language that is clearest from '
    'the request. You can discuss robotics, yoga, cybersecurity, general health, and '
    'fitness at a practical educational level. For health and fitness, give general '
    'wellness information, avoid diagnosis, and recommend professional medical help '
    'for urgent, severe, or personal medical concerns. For cybersecurity, stay defensive '
    'and educational; do not provide instructions for theft, malware, credential abuse, '
    'or unauthorized access. '
    'Use persistent memory when it is relevant, but do not mention memory mechanics. '
    'Do not give long explanations unless the user asks. If the user asks '
    'a question, answer it directly instead of asking for permission. If the '
    'transcript looks incomplete or garbled, say that you did not catch it and ask '
    'for the request again. Answer safe '
    'read-only questions directly and never ask for confirmation for local '
    'information requests. Safe whitelisted actions such as opening the browser or a '
    'website should be executed directly when available. Never invent command '
    'results. Only ask for confirmation for risky or destructive actions.'
)

YOGA_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + ' The user is asking about yoga. Give practical, grounded yoga education with '
    'clear beginner-friendly language. You may discuss poses, breathing, meditation, '
    'mobility, flexibility, strength, stress reduction, routines, and history. Keep '
    'health advice general, avoid diagnosis or treatment claims, and tell the user '
    'to stop and consult a qualified professional for pain, injury, dizziness, or '
    'medical concerns. Prefer concise spoken answers unless the user asks for detail.'
)

CYBERSECURITY_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + ' The user is asking about cybersecurity. Give accurate defensive, educational '
    'answers about concepts, safe lab learning, privacy, account security, network '
    'defense, incident response, compliance basics, and secure habits. Do not provide '
    'malware, credential theft, evasion, phishing, persistence, exploitation, or '
    'unauthorized access instructions. If a request is risky, redirect to safe, '
    'authorized defensive guidance.'
)

YOGA_TERMS = (
    'yoga',
    'asana',
    'pose',
    'poses',
    'pranayama',
    'breathing exercise',
    'meditation',
    'mindfulness',
    'surya namaskar',
    'sun salutation',
    'chakra',
    'flexibility',
    'mobility',
    'stretching',
    'vinyasa',
    'hatha',
    'yin yoga',
    'power yoga',
)

CYBERSECURITY_TERMS = (
    'cyber',
    'cybersecurity',
    'cyber security',
    'security',
    'phishing',
    'spyware',
    'malware',
    'ransomware',
    'hacking',
    'hacker',
    'ssh',
    'secure shell',
    'firewall',
    'vpn',
    'zero trust',
    'encryption',
    'password',
    'passkey',
    'mfa',
    '2fa',
    'network defense',
    'incident response',
    'vulnerability',
    'patching',
    'pentest',
    'penetration test',
    'soc',
    'siem',
    'threat',
    'privacy',
)

SERVICE_NAME = 'hey-ghost.service'


class GhostApp:
    def __init__(self, config: AppConfig) -> None:
        from heyghost.audio.input import AudioInput
        from heyghost.audio.output import AudioOutput
        from heyghost.audio.recorder import Recorder
        from heyghost.audio.vad import VoiceActivityDetector
        from heyghost.conversation.memory import ConversationMemory
        from heyghost.debug_events import DebugEventStream
        from heyghost.llm.ollama_client import OllamaClient
        from heyghost.skills.registry import SkillRegistry
        from heyghost.stt.filter import TranscriptFilter
        from heyghost.stt.profiles import build_whisper_stt
        from heyghost.tts.piper import PiperTTS
        from heyghost.wake.openwakeword import build_wake_backend

        self.config = config
        self.logger = configure_logging(
            config.logging.level, config.logging.log_file
        )
        self.debug_events = DebugEventStream(config.logging.debug_events_file)
        self.state = AssistantState.IDLE
        self.running = True
        self._skip_memory_for_turn = False
        self.session_start_file = Path(config.wake_word.dev_trigger_file).with_name('heyghost_session')

        self.audio_input = AudioInput(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            device=config.audio.input_device,
        )
        resolved_sample_rate = self.audio_input.resolve_sample_rate()
        if resolved_sample_rate != config.audio.sample_rate:
            config.audio.sample_rate = resolved_sample_rate
        self.audio_output = AudioOutput(device=config.audio.output_device)
        self.vad = VoiceActivityDetector(
            aggressiveness=config.audio.vad_aggressiveness,
            backend=config.audio.vad_backend,
        )
        self.recorder = Recorder(
            audio_input=self.audio_input,
            vad=self.vad,
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            frame_duration_ms=config.audio.frame_duration_ms,
            silence_timeout_ms=config.audio.silence_timeout_ms,
            min_speech_ms=config.audio.min_speech_ms,
            max_record_seconds=config.audio.max_record_seconds,
            preroll_ms=config.audio.preroll_ms,
            on_speech_started=lambda: self._emit_turn_event('speech_started'),
            on_speech_ended=lambda: self._emit_turn_event('speech_ended'),
            on_audio_level=lambda level: self.debug_events.emit('audio_level', level=round(level, 3)),
        )
        if config.stt.engine == 'vosk':
            from heyghost.stt.vosk_stt import VoskSTT

            self.stt = VoskSTT(
                model_path=config.stt.model_path,
                sample_rate=config.audio.sample_rate,
            )
        else:
            self.stt = build_whisper_stt(config.stt, config.stt.active_profile)
            self.retry_stt = build_whisper_stt(config.stt, config.stt.retry_profile)
        self.transcript_filter = TranscriptFilter(config.stt.ignored_phrases)
        self.wake_word = build_wake_backend(config.wake_word, config.audio)
        self.tts = PiperTTS(
            binary_path=config.tts.binary_path,
            model_path=config.tts.model_path,
            output_wav_path=config.tts.speaker_wav_path,
            audio_output=self.audio_output,
            length_scale=config.tts.length_scale,
            sentence_silence=config.tts.sentence_silence,
        )
        self.memory = ConversationMemory(
            keep_last_turns=config.conversation.keep_last_turns,
            storage_path=config.conversation.memory_path,
            summary_max_chars=config.conversation.summary_max_chars,
            max_persistent_messages=config.conversation.max_persistent_messages,
        )
        self.llm = OllamaClient(
            url=config.llm.url,
            model=config.llm.model,
            num_ctx=config.llm.num_ctx,
            num_predict=config.llm.num_predict,
            temperature=config.llm.temperature,
            max_response_words=config.assistant.max_response_words,
            keep_alive=config.llm.keep_alive,
        )
        self.skills = SkillRegistry(
            debug_events=self.debug_events,
            llm_model=config.llm.model,
            llm=self.llm,
            llm_capabilities_config=config.llm_capabilities,
            rag_config=config.rag,
            ollama_url=config.llm.url,
            debug_events_file=config.logging.debug_events_file,
        )
        self.router = TurnRouter(
            skill_registry=self.skills,
            llm=self.llm,
            structured_routing_enabled=config.routing.structured_output,
            min_confidence=config.routing.min_route_confidence,
        )
        self.current_turn_id = ''
        self._last_response_timing: dict[str, float] = {}

    def stop(self, *_args) -> None:
        self.logger.info('Stopping Hey Ghost')
        self.debug_events.emit('service_stopped')
        self.running = False

    def _emit_turn_event(self, event: str, **fields) -> None:
        if self.current_turn_id:
            fields.setdefault('turn_id', self.current_turn_id)
        self.debug_events.emit(event, **fields)

    def run(self, install_signal_handlers: bool = True) -> int:
        if install_signal_handlers:
            signal.signal(signal.SIGTERM, self.stop)
            signal.signal(signal.SIGINT, self.stop)

        self.logger.info('Hey Ghost starting with config %s', self.config.source_path)
        self.logger.info(
            'Wake detector using %s (fallback trigger %s)',
            self.config.wake_word.engine,
            self.config.wake_word.dev_trigger_file,
        )
        self.logger.info('Audio input sample rate resolved to %s Hz', self.config.audio.sample_rate)
        self.debug_events.reset()
        self.debug_events.emit('service_started')
        self.debug_events.emit('audio_input_ready', sample_rate=self.config.audio.sample_rate)

        if self.config.wake_word.engine == 'always_on':
            self.debug_events.emit('always_listening')
            while self.running:
                try:
                    self._interaction_cycle(continuous=True)
                except Exception as exc:
                    self.logger.exception('Always-listening cycle failed: %s', exc)
                    self.debug_events.emit('error', text=f'Always-listening cycle failed: {exc}')
                    time.sleep(2.0)
            return 0

        while self.running:
            self.state = AssistantState.IDLE_WAKE_WORD
            self.debug_events.emit('idle_wake_word')
            if self.session_start_file.exists():
                self.session_start_file.unlink(missing_ok=True)
                Path(self.config.wake_word.dev_trigger_file).unlink(missing_ok=True)
                self.state = AssistantState.WAKE_DETECTED
                self.debug_events.emit('session_started')
                self._safe_speak(self.config.assistant.acknowledgement)
                try:
                    self._interaction_cycle(
                        follow_up_until=time.time()
                        + self.config.assistant.session_timeout_seconds
                    )
                except Exception as exc:
                    self.logger.exception('Interaction cycle failed: %s', exc)
                    self.debug_events.emit('error', text=f'Interaction cycle failed: {exc}')
                continue

            woke = self.wake_word.wait_for_wake(lambda: self.running)
            if not self.running or not woke:
                break

            self.state = AssistantState.WAKE_DETECTED
            self.debug_events.emit('wake_detected')
            self._safe_speak(self.config.assistant.acknowledgement)
            try:
                self._interaction_cycle(
                    follow_up_until=time.time()
                    + self.config.assistant.session_timeout_seconds
                )
            except Exception as exc:
                self.logger.exception('Interaction cycle failed: %s', exc)
                self.debug_events.emit('error', text=f'Interaction cycle failed: {exc}')

        return 0

    def _interaction_cycle(
        self,
        follow_up_until: float | None = None,
        continuous: bool = False,
    ) -> None:
        empty_turns = 0
        while self.running:
            self.current_turn_id = uuid.uuid4().hex[:12]
            self.state = AssistantState.ACTIVE_SESSION
            self._emit_turn_event('listening')
            record_started = time.perf_counter()
            wav_path = self.recorder.record_until_silence()
            record_timing = dict(getattr(self.recorder, 'last_timing', {}))
            if not wav_path:
                empty_turns += 1
                self._emit_turn_event(
                    'no_speech',
                    reason='no_voice_detected',
                    recording_ms=round(record_timing.get('recording_ms', 0.0), 1),
                    speech_ms=round(record_timing.get('speech_ms', 0.0), 1),
                    max_audio_level=round(record_timing.get('max_audio_level', 0.0), 3),
                )
                if continuous:
                    self.state = AssistantState.FOLLOW_UP_LISTENING
                    continue
                if empty_turns >= 2:
                    self._emit_turn_event('session_idle')
                    return
                if follow_up_until is not None and time.time() >= follow_up_until:
                    self._emit_turn_event('session_idle')
                    return
                self.state = AssistantState.FOLLOW_UP_LISTENING
                continue
            record_ms = (time.perf_counter() - record_started) * 1000.0
            silence_wait_ms = record_timing.get('silence_wait_ms', 0.0)
            speech_ms = record_timing.get('speech_ms', 0.0)

            try:
                self.state = AssistantState.TRANSCRIBING
                self._emit_turn_event('transcribing')
                stt_ms = 0.0
                filter_ms = 0.0
                stt_started = time.perf_counter()
                transcript = self.stt.transcribe(wav_path)
                stt_ms += (time.perf_counter() - stt_started) * 1000.0
                if isinstance(transcript, str):
                    transcript = Transcript(text=transcript)
                filter_started = time.perf_counter()
                correction = self.transcript_filter.clean_with_result(transcript.text)
                text = correction.cleaned_text
                filter_ms += (time.perf_counter() - filter_started) * 1000.0
                if self._should_retry_stt(text, transcript):
                    retry_started = time.perf_counter()
                    retry_transcript = self.retry_stt.transcribe(wav_path)
                    stt_ms += (time.perf_counter() - retry_started) * 1000.0
                    if not isinstance(retry_transcript, str) and retry_transcript.text:
                        transcript = retry_transcript
                        filter_started = time.perf_counter()
                        correction = self.transcript_filter.clean_with_result(transcript.text)
                        text = correction.cleaned_text
                        filter_ms += (time.perf_counter() - filter_started) * 1000.0
                self._emit_turn_event(
                    'stt_result',
                    text=transcript.text,
                    corrected_text=text,
                    confidence=round(transcript.confidence, 2),
                    engine=transcript.engine,
                    stt_ms=round(stt_ms, 1),
                )
                if correction.corrected:
                    self._emit_turn_event(
                        'transcript_corrected',
                        text=text,
                        original=correction.original_text,
                        reason=correction.reason,
                    )
            finally:
                Path(wav_path).unlink(missing_ok=True)
                Path(Path(wav_path).with_suffix('.txt')).unlink(missing_ok=True)

            if not text or transcript.confidence < self.config.stt.min_confidence:
                empty_turns += 1
                self.logger.info(
                    'No speech recognized confidence=%.2f text=%s',
                    transcript.confidence,
                    text,
                )
                self._emit_turn_event(
                    'no_speech',
                    confidence=round(transcript.confidence, 2),
                    engine=transcript.engine,
                )
                if empty_turns >= 2:
                    if continuous:
                        self.state = AssistantState.FOLLOW_UP_LISTENING
                        continue
                    self._emit_turn_event('session_idle')
                    return
                if continuous:
                    self.state = AssistantState.FOLLOW_UP_LISTENING
                    continue
                if follow_up_until is not None and time.time() >= follow_up_until:
                    self._emit_turn_event('session_idle')
                    return
                self.state = AssistantState.FOLLOW_UP_LISTENING
                continue

            self.logger.info('User said: %s', text)
            empty_turns = 0
            self._emit_turn_event(
                'user_text',
                text=text,
                confidence=round(transcript.confidence, 2),
                engine=transcript.engine,
            )
            try:
                self._last_response_timing = {}
                response_started = time.perf_counter()
                response, source = self._generate_response(text)
                response = guard_llm_response(text, response, source)
                response_ms = (time.perf_counter() - response_started) * 1000.0
            except Exception as exc:
                self.logger.exception('Response generation failed: %s', exc)
                self._emit_turn_event('error', text=f'Response generation failed: {exc}')
                response = 'I hit a local error while handling that.'
                source = 'error'
                response_ms = 0.0
            if not response:
                response = 'I did not get a usable answer.'
            speak_started = time.perf_counter()

            self.state = AssistantState.SPEAKING
            self._emit_turn_event('speaking')
            self._emit_turn_event('tts_started')
            tts_timing = self._safe_speak(response)
            tts_ms = (time.perf_counter() - speak_started) * 1000.0
            tts_synthesis_ms = tts_timing.get('tts_synthesis_ms', 0.0)
            playback_ms = tts_timing.get('playback_ms', 0.0)
            self._emit_turn_event(
                'tts_finished',
                tts_ms=round(tts_ms, 1),
                tts_synthesis_ms=round(tts_synthesis_ms, 1),
                playback_ms=round(playback_ms, 1),
            )
            response_timing = dict(self._last_response_timing)
            routing_ms = response_timing.get('routing_ms', 0.0)
            llm_ms = response_timing.get('llm_ms', 0.0)
            total_ms = record_ms + stt_ms + filter_ms + routing_ms + llm_ms + tts_ms
            self.debug_events.emit_payload(
                {
                    'event': 'turn_timing',
                    'turn_id': self.current_turn_id,
                    'record_ms': round(record_ms, 1),
                    'recording_ms': round(record_ms, 1),
                    'speech_ms': round(speech_ms, 1),
                    'silence_wait_ms': round(silence_wait_ms, 1),
                    'stt_ms': round(stt_ms, 1),
                    'transcript_filter_ms': round(filter_ms, 1),
                    'routing_ms': round(routing_ms, 1),
                    'llm_ms': round(llm_ms, 1),
                    'response_ms': round(response_ms, 1),
                    'tts_synthesis_ms': round(tts_synthesis_ms, 1),
                    'playback_ms': round(playback_ms, 1),
                    'tts_ms': round(tts_ms, 1),
                    'total_ms': round(total_ms, 1),
                    'source': source,
                }
            )
            if self._skip_memory_for_turn:
                self._skip_memory_for_turn = False
            else:
                self.memory.add_user(text)
                self.memory.add_assistant(response)
            if source == 'local skill: stop_session':
                self.state = AssistantState.IDLE
                return
            if continuous:
                self.state = AssistantState.FOLLOW_UP_LISTENING
                continue
            if follow_up_until is not None and time.time() < follow_up_until:
                self.state = AssistantState.FOLLOW_UP_LISTENING
                continue
            self._emit_turn_event('session_idle')
            return

    def _should_retry_stt(self, text: str, transcript: Transcript) -> bool:
        if not self.config.stt.retry_on_low_confidence:
            return False
        if self.config.stt.retry_profile == self.config.stt.active_profile:
            return False
        if transcript.confidence < self.config.stt.min_confidence:
            return True
        return self._looks_like_garbled_transcript(text)

    def _generate_response(self, text: str) -> tuple[str, str]:
        self._last_response_timing = {
            'routing_ms': 0.0,
            'llm_ms': 0.0,
        }
        if self._is_simple_wake_phrase(text):
            self.debug_events.emit('response_source', text='local skill: wake_ack')
            return self.config.assistant.acknowledgement, 'local skill: wake_ack'

        memory_result = self._maybe_handle_memory_request(text)
        if memory_result is not None:
            return memory_result, 'local skill: memory'

        route_started = time.perf_counter()
        route = self.router.route(text)
        self._last_response_timing['routing_ms'] = (
            time.perf_counter() - route_started
        ) * 1000.0
        self._emit_turn_event(
            'route_selected',
            route=route.route,
            confidence=round(route.confidence, 2),
            handled=route.handled,
            requires_confirmation=route.requires_confirmation,
        )
        if route.handled:
            self.logger.info('Handled request with route: %s', route.route)
            self._emit_turn_event('skill_result', text=route.spoken_text, source=route.route)
            self.debug_events.emit('response_source', text=f'local skill: {route.route}')
            self.skills.remember_result(route.spoken_text, route.route)
            return route.spoken_text, f'local skill: {route.route}'

        domain_prompt = self._domain_system_prompt(text)
        if domain_prompt is not None:
            return self._generate_model_response(text, domain_prompt, 'local model:domain')

        if self._looks_like_garbled_transcript(text):
            self.debug_events.emit('response_source', text='clarify')
            return 'I did not catch that clearly. Please say the request again.', 'clarify'

        return self._generate_model_response(text, SYSTEM_PROMPT, 'local model')

    def _generate_model_response(
        self,
        text: str,
        system_prompt: str,
        source: str,
    ) -> tuple[str, str]:
        self.state = AssistantState.THINKING
        self._emit_turn_event('thinking')
        self.debug_events.emit('response_source', text=source)
        memory_text = self.memory.as_prompt_text()
        summary_text = self.memory.as_summary_text()
        if summary_text:
            memory_text = f'Persistent memory:\n{summary_text}\n\nRecent conversation:\n{memory_text}'
        llm_started = time.perf_counter()
        result = self.llm.generate(
            system_prompt=system_prompt,
            user_text=text,
            memory_text=memory_text,
        )
        self._last_response_timing['llm_ms'] = (
            time.perf_counter() - llm_started
        ) * 1000.0
        self._emit_turn_event('llm_result', text=result, source=source, model=self.config.llm.model)
        return result, source

    def _domain_system_prompt(self, text: str) -> str | None:
        normalized = ' '.join(text.lower().replace('-', ' ').split())
        if any(term in normalized for term in YOGA_TERMS):
            return YOGA_SYSTEM_PROMPT
        if any(term in normalized for term in CYBERSECURITY_TERMS):
            return CYBERSECURITY_SYSTEM_PROMPT
        return None

    def _looks_like_garbled_transcript(self, text: str) -> bool:
        words = text.lower().split()
        if len(words) <= 3:
            return True
        question_starts = {'what', 'why', 'how', 'who', 'when', 'where', 'can', 'could', 'is', 'are', 'do'}
        command_starts = {'open', 'close', 'run', 'start', 'stop', 'tell', 'show', 'remember', 'forget'}
        if words[0] not in question_starts | command_starts and len(words) < 6:
            return True
        filler_count = sum(1 for word in words if word in {'the', 'of', 'to', 'for', 'and', 'a'})
        return len(words) >= 5 and filler_count / len(words) > 0.55

    def _is_simple_wake_phrase(self, text: str) -> bool:
        normalized = ' '.join(text.lower().replace(',', ' ').replace('.', ' ').split())
        return normalized in {
            'hey',
            'hey ghost',
            'hello ghost',
            'hi ghost',
            'ghost',
            'hey jarvis',
            'hello',
            'hi',
        }

    def _maybe_handle_memory_request(self, text: str) -> str | None:
        normalized = text.lower()
        if any(
            phrase in normalized
            for phrase in (
                'forget the conversation',
                'forget this conversation',
                'clear the conversation',
                'clear your memory',
            )
        ):
            self.memory.clear()
            self._skip_memory_for_turn = True
            return 'I cleared the conversation memory.'

        if any(
            phrase in normalized
            for phrase in (
                'what do you remember',
                'what are you remembering',
                'what is in your memory',
            )
        ):
            summary = self.memory.as_summary_text() or self.memory.as_prompt_text()
            if not summary:
                return 'I do not have any conversation memory yet.'
            return self.llm.generate(
                system_prompt=(
                    'Summarize this assistant memory in one short spoken sentence. '
                    'Mention only useful user facts or recent context.'
                ),
                user_text=summary,
                memory_text='',
            )

        return None

    def _safe_speak(self, text: str) -> dict[str, float]:
        self.debug_events.emit('assistant_text', text=text)
        try:
            timing = self.tts.speak(text)
            if isinstance(timing, dict):
                return timing
        except Exception as exc:
            self.logger.error('TTS failed: %s', exc)
            self.debug_events.emit('error', text=f'TTS failed: {exc}')
        return {}


def _run_systemctl(action: str) -> int:
    commands = (
        ['systemctl', action, SERVICE_NAME],
        ['sudo', 'systemctl', action, SERVICE_NAME],
    )
    last_error = ''
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            if result.stdout.strip():
                print(result.stdout.strip())
            return 0
        last_error = result.stderr.strip() or result.stdout.strip()

    if 'could not be found' in last_error.lower():
        print('Service unit not installed. Run sudo ./install.sh first.')
    elif last_error:
        print(last_error)
    return 1


def _status_systemctl() -> int:
    commands = (
        ['systemctl', 'status', '--no-pager', SERVICE_NAME],
        ['sudo', 'systemctl', 'status', '--no-pager', SERVICE_NAME],
    )
    last_error = ''
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            if result.stdout.strip():
                print(result.stdout.strip())
            return 0
        last_error = result.stderr.strip() or result.stdout.strip()

    if 'could not be found' in last_error.lower():
        print('Service unit not installed. Run sudo ./install.sh first.')
    elif last_error:
        print(last_error)
    return 1


def prepare_desktop_config(config: AppConfig) -> AppConfig:
    state_root = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local' / 'state')) / 'heyghost'
    data_root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'heyghost'
    shared_dir = state_root / 'shared'
    log_dir = state_root / 'logs'
    knowledge_dir = data_root / 'knowledge'

    for directory in (shared_dir, log_dir, knowledge_dir):
        directory.mkdir(parents=True, exist_ok=True)

    config.tts.speaker_wav_path = str(shared_dir / 'heyghost_response.wav')
    config.wake_word.dev_trigger_file = str(shared_dir / 'heyghost_wake')
    config.conversation.memory_path = str(shared_dir / 'conversation-memory.sqlite3')
    config.logging.log_file = str(log_dir / 'hey-ghost.log')
    config.logging.debug_events_file = str(shared_dir / 'debug-events.jsonl')
    config.rag.index_path = str(shared_dir / 'rag-index.sqlite3')
    config.rag.knowledge_dir = str(knowledge_dir)
    return config


def run_desktop_session(config: AppConfig) -> int:
    from heyghost.debug_window import run_debug_window

    config = prepare_desktop_config(config)
    app = GhostApp(config)
    app_error: list[BaseException] = []

    def run_assistant() -> None:
        try:
            app.run(install_signal_handlers=False)
        except BaseException as exc:
            app_error.append(exc)
            app.logger.exception('Desktop assistant loop failed: %s', exc)
            app.debug_events.emit('error', text=f'Desktop assistant loop failed: {exc}')

    thread = threading.Thread(
        target=run_assistant,
        name='heyghost-desktop-assistant',
        daemon=True,
    )
    thread.start()

    def stop_assistant() -> None:
        app.stop()

    window_code = run_debug_window(config, on_close=stop_assistant, standalone=True)
    app.stop()
    thread.join(timeout=max(2.0, float(config.audio.max_record_seconds) + 1.0))
    if app_error:
        return 1
    return window_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Hey Ghost local voice assistant')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to config.yaml',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('run', help='Run foreground assistant loop')
    sub.add_parser('start', help='Start systemd service')
    sub.add_parser('stop', help='Stop systemd service')
    sub.add_parser('restart', help='Restart systemd service')
    sub.add_parser('status', help='Show systemd service status')
    sub.add_parser('trigger', help='Start a continuous listening session')
    replay_parser = sub.add_parser('replay', help='Replay transcript fixtures through filter and router')
    replay_parser.add_argument('fixture', help='JSONL fixture path')
    sub.add_parser('test-tts', help='Synthesize and play a test phrase')
    sub.add_parser('test-ollama', help='Send a hello prompt to the configured Ollama model')
    sub.add_parser('index-rag', help='Index local knowledge documents for RAG search')
    sub.add_parser('debug-window', help='Open the desktop debug console')
    sub.add_parser('desktop', help='Run assistant and desktop window together')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from heyghost.config import load_config

    config = load_config(args.config)

    if args.command == 'run':
        app = GhostApp(config)
        return app.run()

    if args.command == 'start':
        return _run_systemctl('start')

    if args.command == 'stop':
        return _run_systemctl('stop')

    if args.command == 'restart':
        return _run_systemctl('restart')

    if args.command == 'status':
        return _status_systemctl()

    if args.command == 'trigger':
        wake_path = Path(config.wake_word.dev_trigger_file)
        session_path = wake_path.with_name('heyghost_session')
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.unlink(missing_ok=True)
        wake_path.write_text('wake\n', encoding='utf-8')
        print(f'Started listening session: {wake_path}')
        return 0

    if args.command == 'replay':
        from heyghost.replay import replay_transcripts

        return replay_transcripts(args.fixture)

    if args.command == 'test-tts':
        from heyghost.audio.output import AudioOutput
        from heyghost.tts.piper import PiperTTS

        tts = PiperTTS(
            binary_path=config.tts.binary_path,
            model_path=config.tts.model_path,
            output_wav_path=config.tts.speaker_wav_path,
            audio_output=AudioOutput(device=config.audio.output_device),
        )
        tts.speak('Hey Ghost text to speech test.')
        return 0

    if args.command == 'test-ollama':
        from heyghost.llm.ollama_client import OllamaClient

        llm = OllamaClient(
            url=config.llm.url,
            model=config.llm.model,
            num_ctx=config.llm.num_ctx,
            num_predict=config.llm.num_predict,
            temperature=config.llm.temperature,
            max_response_words=config.assistant.max_response_words,
            keep_alive=config.llm.keep_alive,
        )
        print(
            llm.generate(
                system_prompt='You are Ghost. Reply with one short greeting.',
                user_text='Say hello.',
                memory_text='',
            )
        )
        return 0

    if args.command == 'index-rag':
        from heyghost.rag.embeddings import OllamaEmbedder
        from heyghost.rag.rag_skill import LocalRAG
        from heyghost.rag.vector_store import SQLiteVectorStore

        rag = LocalRAG(
            store=SQLiteVectorStore(config.rag.index_path),
            embedder=OllamaEmbedder(config.llm.url, config.rag.embedding_model),
            knowledge_dir=config.rag.knowledge_dir,
            chunk_chars=config.rag.chunk_chars,
            chunk_overlap=config.rag.chunk_overlap,
            top_k=config.rag.top_k,
            require_sources=config.rag.require_sources,
        )
        count = rag.index()
        print(f'Indexed {count} local knowledge chunks.')
        return 0

    if args.command == 'debug-window':
        from heyghost.debug_window import run_debug_window

        return run_debug_window(config)

    if args.command == 'desktop':
        return run_desktop_session(config)

    parser.error(f'Unknown command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
