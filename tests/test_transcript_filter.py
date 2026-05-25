from heyghost.stt.filter import TranscriptFilter


def test_spyware_misrecognition_is_corrected():
    result = TranscriptFilter().clean_with_result("What is my U.N.")
    assert result.cleaned_text == "what is spyware"
    assert result.corrected


def test_spyware_random_misrecognition_is_corrected():
    result = TranscriptFilter().clean_with_result("What is a spy random?")
    assert result.cleaned_text == "what is spyware"
    assert result.corrected


def test_wake_phrase_is_removed():
    result = TranscriptFilter().clean_with_result("Hey Ghost what is phishing")
    assert result.cleaned_text == "what is phishing"
    assert result.reason == "wake_phrase_removed"


def test_ignored_phrase_is_removed():
    result = TranscriptFilter().clean_with_result("Thank you for watching.")
    assert result.cleaned_text == ""
    assert result.reason == "ignored_phrase"


def test_video_filler_phrase_is_removed():
    result = TranscriptFilter().clean_with_result("For more information, please visit me.")
    assert result.cleaned_text == ""
    assert result.reason == "ignored_phrase"


def test_short_idle_filler_is_removed():
    result = TranscriptFilter().clean_with_result("Yeah.")
    assert result.cleaned_text == ""
    assert result.reason == "ignored_phrase"


def test_capabilities_misrecognition_doing_with_me_is_corrected():
    result = TranscriptFilter().clean_with_result("What are you doing with me?")
    assert result.cleaned_text == "what are your capabilities"
    assert result.corrected


def test_capabilities_misrecognition_kiwi_b_is_corrected():
    result = TranscriptFilter().clean_with_result("What are you, kiwi b")
    assert result.cleaned_text == "what are your capabilities"
    assert result.corrected


def test_capabilities_missing_a_is_corrected():
    result = TranscriptFilter().clean_with_result("What are your capblities?")
    assert result.cleaned_text == "what are your capabilities"
    assert result.corrected


def test_usb_misrecognition_coming_through_today_is_corrected():
    result = TranscriptFilter().clean_with_result("What is coming through today, USB?")
    assert result.cleaned_text == "what is connected to the usb"
    assert result.corrected


def test_terminal_list_files_misrecognition_list_file_is_corrected():
    result = TranscriptFilter().clean_with_result("List file.")
    assert result.cleaned_text == "list files"
    assert result.corrected


def test_terminal_list_files_misrecognition_please_twice_is_corrected():
    result = TranscriptFilter().clean_with_result("Please twice.")
    assert result.cleaned_text == "list files"
    assert result.corrected


def test_terminal_disk_space_misrecognition_short_is_corrected():
    result = TranscriptFilter().clean_with_result("Short disk space.")
    assert result.cleaned_text == "show disk space"
    assert result.corrected


def test_terminal_demo_misrecognitions_are_corrected():
    cases = {
        "Please find.": "list files",
        "Show all this space.": "show disk space",
        "Ghost, Birmingham.": "show memory",
        "Close that mean all.": "close terminal",
        "Close that mean that.": "close terminal",
        "Close to the winner.": "close terminal",
        "Close to our winner.": "close terminal",
        "Close the winner.": "close terminal",
        "Close Birmingham.": "close terminal",
        "Close terminal window.": "close terminal",
        "Contoncy!": "close terminal",
        "Take one.": "close terminal",
        "Ghost terminal.": "close terminal",
        "Open a company now.": "open terminal",
        "Open, tell me now.": "open terminal",
        "Open domain.": "open terminal",
        "Open the menu.": "open terminal",
        "Open that data menu.": "open terminal",
        "Open the window.": "open terminal",
        "Are you home at every but never, never, never.": "open terminal",
    }
    for phrase, expected in cases.items():
        result = TranscriptFilter().clean_with_result(phrase)
        assert result.cleaned_text == expected
        assert result.corrected
