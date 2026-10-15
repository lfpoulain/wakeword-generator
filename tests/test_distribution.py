"""Checks approved French speakers and balanced synthesis variations."""
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import DEFAULT_CONFIG, load_config, sample_plan, speaker_pool


def test_approved_french_speakers():
    from download_assets import DEFAULT_VOICES

    assert DEFAULT_VOICES == ("siwis", "upmc", "tom")
    expected = [(0, 0), (1, 0), (1, 1), (2, 0)]
    assert speaker_pool([1, 2, 1], "train") == expected
    assert speaker_pool([1, 2, 1], "test") == expected


def test_speaker_phrase_and_speed_distribution():
    pool = speaker_pool([1, 2, 1], "train")
    config = load_config(DEFAULT_CONFIG)
    positive_phrases = len(config["target_phrase"])
    negative_phrases = len(config["custom_negative_phrases"])
    for count, phrase_count in ((20_000, positive_phrases),
                                (20_000, negative_phrases),
                                (2_000, positive_phrases)):
        speakers = Counter()
        phrases = {identity: Counter() for identity in pool}
        variations = {identity: Counter() for identity in pool}
        for index in range(count):
            voice, speaker, variation, phrase = sample_plan(
                index, pool, 5, phrase_count)
            identity = (voice, speaker)
            speakers[identity] += 1
            phrases[identity][phrase] += 1
            variations[identity][variation] += 1
        assert max(speakers.values()) - min(speakers.values()) <= 1
        for identity in pool:
            assert len(phrases[identity]) == phrase_count
            assert len(variations[identity]) == 5
            assert max(phrases[identity].values()) - min(phrases[identity].values()) <= 1
            assert max(variations[identity].values()) - min(variations[identity].values()) <= 1


def test_short_clip_retries_at_slower_speed(tmp_path, monkeypatch):
    import types
    import wave

    class Settings:
        def __init__(self, **values):
            self.__dict__.update(values)

    class FakeVoice:
        def __init__(self):
            self.scales = []

        def synthesize_wav(self, phrase, wav_file, syn_config):
            self.scales.append(syn_config.length_scale)
            duration = 0.8 if syn_config.length_scale >= 0.85 else 0.1
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\0\0" * int(duration * 16000))

    monkeypatch.setitem(sys.modules, "piper",
                        types.SimpleNamespace(SynthesisConfig=Settings))
    from pipeline import synthesize_valid_wav
    voice = FakeVoice()
    chosen = synthesize_valid_wav(voice, "Cornelius", tmp_path / "test.wav",
                                  [0], 0.78, 0.52, 0.6, 0.55)
    assert chosen == 0
    assert len(voice.scales) == 2
    assert voice.scales == [0.78, 0.98]


