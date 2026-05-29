from __future__ import annotations

import os
import re
from typing import Callable

from heyghost.debug_events import DebugEventStream
from heyghost.llm.capabilities import LLMCapabilityLayer
from heyghost.rag import LocalRAG
from heyghost.rag.embeddings import OllamaEmbedder
from heyghost.rag.rag_skill import NO_LOCAL_KNOWLEDGE
from heyghost.rag.vector_store import SQLiteVectorStore
from heyghost.skills.command_grammar import canonicalize_command
from heyghost.skills.result import SkillResult

from . import app_launcher, arithmetic, device_info, domain_catalog, linux_system, qa_bank, system_status, time_skill


def _result(
    source: str,
    text: str,
    confidence: float = 1.0,
    requires_confirmation: bool = False,
    **metadata,
) -> SkillResult:
    return SkillResult(
        handled=True,
        confidence=confidence,
        spoken_text=text,
        source=source,
        requires_confirmation=requires_confirmation,
        metadata=metadata,
    )


class SkillRegistry:
    def __init__(
        self,
        debug_events: DebugEventStream | None = None,
        llm_model: str | None = None,
        llm=None,
        llm_capabilities_config=None,
        rag_config=None,
        ollama_url: str = "http://localhost:11434/api/generate",
        debug_events_file: str | None = None,
    ) -> None:
        self.debug_events = debug_events
        self.llm_model = llm_model or ''
        self.llm = llm
        self.terminal_mode = False
        self.last_result_text = ''
        self.last_result_source = ''
        self.llm_capabilities_config = llm_capabilities_config
        self.rag_config = rag_config
        install_root = os.environ.get('HEY_GHOST_INSTALL_ROOT', '/opt/hey-ghost')
        if debug_events_file is None:
            debug_events_file = f'{install_root}/shared/debug-events.jsonl'
        self.capabilities = LLMCapabilityLayer(
            llm=llm,
            debug_events_file=debug_events_file,
            max_spoken_words=getattr(llm_capabilities_config, 'max_spoken_words', 55),
            vision_enabled=getattr(llm_capabilities_config, 'vision_enabled', False),
        )
        self.rag = self._build_rag(ollama_url)
        self._skills: dict[str, Callable[[], str]] = {
            'time': time_skill.run,
            'system_status': system_status.run,
            'memory': device_info.memory_summary,
            'cpu': device_info.cpu_summary,
            'storage': device_info.storage_summary,
            'os': device_info.os_summary,
            'system': device_info.system_summary,
        }

    def maybe_handle(self, text: str) -> SkillResult | None:
        normalized = _normalize(text)
        grammar_match = canonicalize_command(normalized)
        if grammar_match is not None:
            normalized = grammar_match.text
            text = grammar_match.text

        demo_terminal_result = self._maybe_handle_demo_terminal_intent(normalized)
        if demo_terminal_result is not None:
            return demo_terminal_result

        if normalized in {'proceed', 'continue', 'go ahead', 'yes', 'okay', 'ok'}:
            return _result(
                'clarify',
                'Say the full request again, for example how much RAM does the system have or open the browser.',
                confidence=0.7,
            )

        if _looks_like_close_terminal(normalized):
            self.terminal_mode = False
            action = {'kind': 'close_app', 'target': 'terminal', 'message': 'Closing the terminal.'}
            if self.debug_events is not None:
                self.debug_events.emit_payload(
                    {
                        'event': 'action_request',
                        'text': action['message'],
                        'action': action,
                    }
                )
            return _result('action', action['message'], action=action)

        terminal_response = self._maybe_handle_terminal_followup(normalized)
        if terminal_response is not None:
            return terminal_response

        demo_terminal_action = _basic_terminal_action_from_text(normalized)
        if demo_terminal_action is not None:
            if self.debug_events is not None:
                self.debug_events.emit_payload(
                    {
                        'event': 'action_request',
                        'text': demo_terminal_action['message'],
                        'action': demo_terminal_action,
                    }
                )
            return _result('terminal_input', demo_terminal_action['message'], action=demo_terminal_action)

        if _mentions_time(normalized):
            return _result('time', self._skills['time']())

        if _mentions_memory(normalized):
            return _result('memory', self._skills['memory']())

        if _mentions_cpu(normalized):
            return _result('cpu', self._skills['cpu']())

        if _mentions_model(normalized):
            return _result('model', self._model_summary())

        if _mentions_os(normalized):
            return _result('os', self._skills['os']())

        if _mentions_system_status(normalized):
            return _result('system_status', self._skills['system_status']())

        if _mentions_storage(normalized):
            return _result('storage', self._skills['storage']())

        if _mentions_system_summary(normalized):
            return _result('system', self._skills['system']())

        if _mentions_capabilities(normalized):
            return _result(
                'capabilities',
                'I can answer system questions and run terminal demos.',
            )

        arithmetic_response = arithmetic.maybe_answer_arithmetic(text)
        if arithmetic_response is not None:
            name, answer = arithmetic_response
            return _result(name, answer)

        capability_response = self._maybe_handle_llm_capability(normalized, text)
        if capability_response is not None:
            return capability_response

        knowledge_response = _domain_knowledge(normalized)
        if knowledge_response is not None:
            return knowledge_response

        linux_response = linux_system.maybe_linux_skill(normalized)
        if linux_response is not None:
            name, answer, action = linux_response
            if action is not None and action.get('kind') in {'ssh', 'terminal'}:
                self.terminal_mode = True
            if action is not None and self.debug_events is not None:
                self.debug_events.emit_payload(
                    {
                        'event': 'action_request',
                        'text': answer,
                        'action': action,
                    }
                )
            return _result(name, answer, action=action)

        qa_response = qa_bank.answer_qa_bank(normalized)
        if qa_response is not None:
            name, answer = qa_response
            return _result(name, answer)

        action = app_launcher.maybe_build_action(normalized)
        if action is not None:
            if action.get('kind') in {'ssh', 'terminal'}:
                self.terminal_mode = True
            if self.debug_events is not None:
                self.debug_events.emit_payload(
                    {
                        'event': 'action_request',
                        'text': action['message'],
                        'action': action,
                    }
                )
            if action.get('kind') == 'ssh':
                return _result(
                    'action',
                    f"{action['message']} What should I do in the SSH terminal?",
                    requires_confirmation=True,
                    action=action,
                )
            return _result('action', action['message'], action=action)

        return None

    def _maybe_handle_demo_terminal_intent(self, text: str) -> SkillResult | None:
        if _looks_like_open_terminal(text):
            self.terminal_mode = True
            action = {
                'kind': 'terminal',
                'prompt': 'HeyGhost terminal ready. Say a command for me to run.',
                'message': 'Opening terminal.',
            }
            return self._emit_action_result('linux:open_terminal', action)

        if _looks_like_close_terminal(text):
            self.terminal_mode = False
            action = {'kind': 'close_app', 'target': 'terminal', 'message': 'Closing terminal.'}
            return self._emit_action_result('action', action)

        return None

    def _emit_action_result(self, source: str, action: dict[str, object]) -> SkillResult:
        message = str(action.get('message', 'Done.'))
        if self.debug_events is not None:
            self.debug_events.emit_payload(
                {
                    'event': 'action_request',
                    'text': message,
                    'action': action,
                }
            )
        return _result(source, message, action=action)

    def names(self) -> list[str]:
        return sorted(self._skills)

    def remember_result(self, text: str, source: str) -> None:
        if not text or source.startswith('llm_capabilities'):
            return
        self.last_result_text = text
        self.last_result_source = source

    def _model_summary(self) -> str:
        if self.llm_model:
            return f'Model: {self.llm_model}.'
        return 'Model: local Ollama.'

    def _build_rag(self, ollama_url: str) -> LocalRAG | None:
        install_root = os.environ.get('HEY_GHOST_INSTALL_ROOT', '/opt/hey-ghost')
        rag_config = self.rag_config
        capability_config = self.llm_capabilities_config
        if rag_config is None or not getattr(rag_config, 'enabled', False):
            return None
        if capability_config is not None and not getattr(capability_config, 'local_rag_enabled', True):
            return None
        embedder = OllamaEmbedder(ollama_url, getattr(rag_config, 'embedding_model', 'nomic-embed-text'))
        return LocalRAG(
            store=SQLiteVectorStore(getattr(rag_config, 'index_path', f'{install_root}/shared/rag-index.sqlite3')),
            embedder=embedder,
            knowledge_dir=getattr(rag_config, 'knowledge_dir', f'{install_root}/knowledge'),
            chunk_chars=getattr(rag_config, 'chunk_chars', 800),
            chunk_overlap=getattr(rag_config, 'chunk_overlap', 120),
            top_k=getattr(rag_config, 'top_k', 4),
            require_sources=getattr(rag_config, 'require_sources', True),
            llm=self.llm,
        )

    def _maybe_handle_llm_capability(self, normalized: str, original_text: str) -> SkillResult | None:
        if self.llm_capabilities_config is not None and not getattr(self.llm_capabilities_config, 'enabled', True):
            return None

        if _has_any(normalized, ('show your llm capabilities', 'llm capabilities', 'local model capabilities')) or _mentions_capabilities(normalized):
            return _result('llm_capabilities:overview', self.capabilities.overview())

        if _has_any(normalized, ('summarize this note', 'summarize note')):
            if not getattr(self.llm_capabilities_config, 'summarize_notes', True):
                return _result('llm_capabilities:disabled', 'Note summarization is disabled.')
            return _result('llm_capabilities:note_summary', self.capabilities.summarize_note(original_text))

        if _has_any(normalized, ('explain that result', 'explain the result', 'explain previous result')):
            if not getattr(self.llm_capabilities_config, 'explain_command_results', True):
                return _result('llm_capabilities:disabled', 'Command result explanation is disabled.')
            return _result('llm_capabilities:result_explainer', self.capabilities.explain(self.last_result_text))

        if _has_any(normalized, ('why did you answer wrong', 'why was that wrong', 'why did you get that wrong')):
            if not getattr(self.llm_capabilities_config, 'analyze_logs', True):
                return _result('llm_capabilities:disabled', 'Log analysis is disabled.')
            return _result('llm_capabilities:log_analysis', self.capabilities.analyze_logs())

        if 'teach me about linux networking' in normalized:
            return _result('llm_capabilities:teaching', self.capabilities.teach_linux_networking())

        if _has_any(normalized, ('search your local knowledge for', 'search local knowledge for')):
            query = _local_knowledge_query(original_text)
            if self.rag is None:
                return _result('llm_capabilities:rag', NO_LOCAL_KNOWLEDGE, sources=[])
            answer = self.rag.answer(query)
            if answer.text == NO_LOCAL_KNOWLEDGE:
                try:
                    self.rag.index()
                    answer = self.rag.answer(query)
                except Exception:
                    answer = self.rag.answer(query)
            return _result('llm_capabilities:rag', answer.text, sources=answer.sources)

        if _has_any(normalized, ('classify this request', 'classify request')):
            return _result('llm_capabilities:classifier', self.capabilities.classify(original_text))

        if _has_any(normalized, ('make that shorter', 'make this shorter')):
            return _result('llm_capabilities:summarizer', self.capabilities.shorten(original_text, self.last_result_text))

        if _has_any(normalized, ('turn this into action items', 'action items from this')):
            return _result('llm_capabilities:action_items', self.capabilities.action_items(original_text))

        if _has_any(normalized, ('suggest a config change', 'config suggestion')):
            return _result('llm_capabilities:config_suggestion', self.capabilities.suggest_config(original_text))

        return None

    def _maybe_handle_terminal_followup(self, text: str) -> SkillResult | None:
        if not self.terminal_mode:
            return None

        if text in {'stop terminal mode', 'leave terminal mode', 'exit terminal mode'}:
            self.terminal_mode = False
            return _result('terminal_mode', 'Terminal control is off.')

        action = _terminal_action_from_text(text)
        if action is None:
            return None

        if action.get('deactivate'):
            self.terminal_mode = False

        if self.debug_events is not None:
            self.debug_events.emit_payload(
                {
                    'event': 'action_request',
                    'text': action['message'],
                    'action': action,
                }
            )
        return _result('terminal_input', action['message'], action=action)



def _normalize(text: str) -> str:
    cleaned = re.sub(r'[^a-z0-9./:@_-]+', ' ', text.lower())
    return ' '.join(cleaned.split())



def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _looks_like_open_terminal(text: str) -> bool:
    if text in {
        'open terminal',
        'open the terminal',
        'open up terminal',
        'open up the terminal',
        'launch terminal',
        'launch the terminal',
        'start terminal',
        'start the terminal',
        'open qterminal',
        'open shell',
        'open bash',
        'open a terminal',
        'open our terminal',
        'open that data menu',
        'open data menu',
        'open the window',
        'open window',
        'open that window',
        'open the menu',
        'open menu',
        'open tell me now',
        'open domain',
        'open a company now',
        'open company now',
        'are you home at every but never never never',
    }:
        return True
    words = text.split()
    if not words or words[0] not in {'open', 'launch', 'start'}:
        return False
    return _has_any(text, ('terminal', 'qterminal', 'shell', 'bash'))


def _looks_like_close_terminal(text: str) -> bool:
    if text in {
        'close terminal',
        'close the terminal',
        'close terminal window',
        'close the terminal window',
        'close qterminal',
        'close the qterminal',
        'close the window',
        'close window',
    }:
        return True
    if not text.startswith('close '):
        return False
    return _has_any(
        text,
        (
            'terminal',
            'qterminal',
            'tour winner',
            'the winner',
            'our winner',
            'mean all',
            'mean that',
            'birmingham',
        ),
    )


def _local_knowledge_query(text: str) -> str:
    lowered = text.lower()
    for phrase in ('search your local knowledge for', 'search local knowledge for'):
        index = lowered.find(phrase)
        if index != -1:
            return text[index + len(phrase):].strip(' :,-')
    return text



def _mentions_time(text: str) -> bool:
    return (
        'time' in text and _has_any(text, ('what', 'tell', 'current'))
    ) or _has_any(text, ('hora', 'tiempo actual', 'que hora', 'qué hora', '几点', '時間'))



def _mentions_memory(text: str) -> bool:
    return _has_any(
        text,
        (
            'ram',
            'memory',
            'total ram',
            'system ram',
            'memory status',
        ),
    )



def _mentions_cpu(text: str) -> bool:
    return _has_any(text, ('cpu', 'processor', 'intel n100', 'cpu info'))



def _mentions_model(text: str) -> bool:
    if _has_any(text, ('ollama model', 'olama model', 'llm model', 'modelo ollama', 'modelo local', '模型')):
        return True
    if _has_any(text, ('which model', 'what model', 'model is running', 'model are you using', 'qué modelo', 'que modelo')):
        return True
    return 'model' in text and _has_any(text, ('running', 'installed', 'using', 'current'))



def _mentions_os(text: str) -> bool:
    return _has_any(
        text,
        (
            'operating system',
            'os version',
            'linux version',
            'what system are you running',
            'which operating system',
            'what os',
            'sistema operativo',
            'qué sistema',
            'que sistema',
            '操作系统',
            '系統',
        ),
    )



def _mentions_system_status(text: str) -> bool:
    return _has_any(text, ('system status', 'status right now', 'current system status'))



def _mentions_storage(text: str) -> bool:
    return _has_any(text, ('disk space', 'storage', 'free space', 'disk free', 'disk usage'))



def _mentions_system_summary(text: str) -> bool:
    return _has_any(
        text,
        (
            'system info',
            'system information',
            'hardware info',
            'device info',
            'machine info',
        ),
    )


def _mentions_capabilities(text: str) -> bool:
    return _has_any(
        text,
        (
            'capab',
            'ability',
            'abilities',
            'what can you do',
            'what are your features',
            'what do you do',
            'qué puedes hacer',
            'que puedes hacer',
            'habilidades',
            'funciones',
            '你会什么',
            '你能做什么',
        ),
    )


def _domain_knowledge(text: str) -> SkillResult | None:
    if _has_any(text, ('what is yoga', 'what s yoga', 'define yoga', 'explain yoga', 'yoga mean')):
        return _result(
            'knowledge:yoga',
            'Yoga is a mind and body practice from ancient India that uses movement, breathing, and attention to build flexibility, strength, calm, and balance.',
        )
    if _has_any(text, ('what is robotics', 'define robotics', 'explain robotics')):
        return _result(
            'knowledge:robotics',
            'Robotics is the field of designing, building, sensing, and controlling machines that can act in the physical world.',
        )
    if _has_any(text, ('what is cybersecurity', 'what is cyber security', 'define cybersecurity', 'define cyber security')):
        return _result(
            'knowledge:cybersecurity',
            'Cybersecurity is the practice of protecting computers, networks, accounts, and data from unauthorized access, damage, or misuse.',
        )
    if _has_any(text, ('what is fitness', 'define fitness', 'explain fitness')):
        return _result(
            'knowledge:fitness',
            'Fitness means having enough strength, endurance, mobility, and energy to handle daily life and physical activity well.',
        )
    if _has_any(text, ('what is health', 'define health', 'explain health')):
        return _result(
            'knowledge:health',
            'Health is overall physical, mental, and social well-being, not just the absence of illness.',
        )
    catalog_response = domain_catalog.answer_domain_question(text)
    if catalog_response is not None:
        name, answer = catalog_response
        return _result(name, answer)
    return None


def _terminal_action_from_text(text: str) -> dict[str, object] | None:
    if _looks_dangerous_terminal_command(text):
        return {
            'kind': 'noop',
            'message': 'I will not run destructive terminal commands by voice.',
        }

    if text in {'press enter', 'hit enter', 'enter'}:
        return {
            'kind': 'terminal_input',
            'text': '',
            'enter': True,
            'message': 'Pressed Enter in the terminal.',
        }

    if text in {'press control c', 'control c', 'ctrl c', 'cancel command'}:
        return {
            'kind': 'terminal_key',
            'key': 'ctrl+c',
            'message': 'Sent Control C to the terminal.',
        }

    if text in {'exit', 'exit ssh', 'close ssh', 'logout'}:
        return {
            'kind': 'terminal_input',
            'text': 'exit',
            'enter': True,
            'deactivate': True,
            'message': 'Exiting the SSH terminal.',
        }

    command = _terminal_command_text(text)
    if not command:
        return None

    return {
        'kind': 'terminal_input',
        'text': command,
        'enter': True,
        'message': f'Running {command} in the terminal.',
    }


def _basic_terminal_action_from_text(text: str) -> dict[str, object] | None:
    command = _terminal_command_text(text, allow_prefixed=False)
    if not command:
        return None
    return {
        'kind': 'terminal_input',
        'text': command,
        'enter': True,
        'message': f'Running {command} in the terminal.',
    }


def _terminal_command_text(text: str, allow_prefixed: bool = True) -> str | None:
    text = _normalize_terminal_command_text(text)
    replacements = {
        'list files': 'ls',
        'show directory': 'ls',
        'show the directory': 'ls',
        'show folder': 'ls',
        'show files in this folder': 'ls',
        'list directory': 'ls',
        'list the directory': 'ls',
        'list folder': 'ls',
        'list the folder': 'ls',
        'ls': 'ls',
        'show files': 'ls',
        'list all files': 'ls -la',
        'show hidden files': 'ls -la',
        'list hidden files': 'ls -la',
        'long listing': 'ls -la',
        'print working directory': 'pwd',
        'current directory': 'pwd',
        'show current directory': 'pwd',
        'where am i': 'pwd',
        'where am i in the terminal': 'pwd',
        'pwd': 'pwd',
        'clear screen': 'clear',
        'clear terminal': 'clear',
        'clear': 'clear',
        'show processes': 'ps aux',
        'list processes': 'ps aux',
        'process list': 'ps aux',
        'show running processes': 'ps aux',
        'top processes': 'top',
        'show top': 'top',
        'show disk space': 'df -h',
        'short disk space': 'df -h',
        'disk space': 'df -h',
        'list disks': 'lsblk',
        'show disks': 'lsblk',
        'show memory': 'free -h',
        'memory usage': 'free -h',
        'show network addresses': 'ip -brief address',
        'show network address': 'ip -brief address',
        'show ip address': 'ip -brief address',
        'ip address': 'ip -brief address',
        'show date': 'date',
        'date': 'date',
        'who am i': 'whoami',
        'whoami': 'whoami',
        'show calendar': 'cal',
        'calendar': 'cal',
    }
    if text in replacements:
        return replacements[text]

    if not allow_prefixed:
        return None

    for prefix in (
        'run ',
        'execute ',
        'type ',
        'write ',
        'send ',
        'enter command ',
        'terminal ',
    ):
        if text.startswith(prefix):
            command = text.removeprefix(prefix).strip()
            if _looks_dangerous_terminal_command(command):
                return None
            alias_command = _terminal_command_text(command, allow_prefixed=False)
            if alias_command:
                return alias_command
            return command

    return None


def _normalize_terminal_command_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = normalized.strip(' .!?')
    normalized = re.sub(r'\s+', ' ', normalized)
    for suffix in (
        ' in the terminal',
        ' in terminal',
        ' on the terminal',
        ' on terminal',
        ' to the terminal',
        ' into the terminal',
    ):
        if normalized.endswith(suffix):
            normalized = normalized.removesuffix(suffix).strip()
    return normalized


def _looks_like_question(text: str) -> bool:
    return text.startswith(('what ', 'why ', 'how ', 'who ', 'when ', 'where ', 'can you ', 'could you '))


def _looks_dangerous_terminal_command(text: str) -> bool:
    return any(term in text for term in ('rm -rf', 'mkfs', 'shutdown', 'reboot', 'poweroff'))
