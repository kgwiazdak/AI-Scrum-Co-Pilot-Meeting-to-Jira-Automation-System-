"""Speech-to-text utilities backed by Azure Speech Services."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import threading
import wave
from functools import lru_cache
from pathlib import Path
from typing import Callable, List, Tuple

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import transcription as speech_transcription

SUPPORTED_AUDIO_EXTENSIONS: Tuple[str, ...] = (".wav", ".mp3")
TARGET_SAMPLE_RATE = int(os.getenv("TRANSCRIBER_SAMPLE_RATE", "16000"))
TARGET_CHANNELS = 1
INTRO_AUDIO_DIR = Path(os.getenv("INTRO_AUDIO_DIR", "data"))
INTRO_AUDIO_PATTERN = os.getenv("INTRO_AUDIO_PATTERN", "intro_*.mp3")
INTRO_SILENCE_MS = int(os.getenv("INTRO_SILENCE_MS", "300"))


class Transcriber:
    def __init__(self) -> None:
        self.SUPPORTED_AUDIO_EXTENSIONS: Tuple[str, ...] = SUPPORTED_AUDIO_EXTENSIONS

    @lru_cache(maxsize=1)
    def _speech_config(self) -> speechsdk.SpeechConfig:
        """Create a cached Azure Speech configuration instance."""

        key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")

        assert key and region, "Azure Speech key and region must be configured"
        config = speechsdk.SpeechConfig(subscription=key, region=region)

        language = os.getenv("AZURE_SPEECH_LANGUAGE", "en-US")
        config.speech_recognition_language = language
        return config

    def _audio_config_from_wav(self, wav_bytes: bytes) -> tuple[speechsdk.audio.AudioConfig, Callable[[], None]]:
        """Create an AudioConfig backed by a push stream plus a feeder function."""

        try:
            with wave.open(io.BytesIO(wav_bytes)) as wav_reader:
                frames = wav_reader.readframes(wav_reader.getnframes())
                sample_rate = wav_reader.getframerate()
                bits_per_sample = wav_reader.getsampwidth() * 8
                channels = wav_reader.getnchannels()
        except wave.Error as exc:  # pragma: no cover - depends on input data
            raise ValueError("Unable to read WAV audio data") from exc

        stream_format = speechsdk.audio.AudioStreamFormat(
            sample_rate,
            bits_per_sample,
            channels,
        )
        push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)

        def feed_audio() -> None:
            push_stream.write(frames)
            push_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        return audio_config, feed_audio

    @staticmethod
    def _convert_to_standard_wav(content: bytes) -> bytes:
        """Normalize any supported audio into mono 16kHz WAV for downstream processing."""

        if shutil.which("ffmpeg") is None:
            raise ValueError("FFmpeg is required to handle audio but was not found in PATH")

        process = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                "pipe:0",
                "-ac",
                str(TARGET_CHANNELS),
                "-ar",
                str(TARGET_SAMPLE_RATE),
                "-f",
                "wav",
                "-acodec",
                "pcm_s16le",
                "pipe:1",
            ],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.returncode != 0:
            error_details = process.stderr.decode("utf-8", errors="ignore").strip()
            raise ValueError(f"Failed to normalize audio via FFmpeg: {error_details}")
        return process.stdout

    @staticmethod
    def _wav_payload(wav_bytes: bytes):
        with wave.open(io.BytesIO(wav_bytes)) as wav_reader:
            reported_frames = wav_reader.getnframes()
            frames = wav_reader.readframes(reported_frames)
            sample_rate = wav_reader.getframerate()
            sample_width = wav_reader.getsampwidth()
            channels = wav_reader.getnchannels()
        bytes_per_frame = sample_width * channels
        num_frames = len(frames) // bytes_per_frame if bytes_per_frame else 0
        return frames, num_frames, sample_rate, sample_width, channels

    @staticmethod
    def _frames_to_ticks(frame_index: int, sample_rate: int) -> int:
        seconds = frame_index / sample_rate
        return int(seconds * 10_000_000)

    @staticmethod
    def _build_wav(frames_sequence: List[bytes], sample_rate: int, sample_width: int, channels: int) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_writer:
            wav_writer.setnchannels(channels)
            wav_writer.setsampwidth(sample_width)
            wav_writer.setframerate(sample_rate)
            for chunk in frames_sequence:
                wav_writer.writeframes(chunk)
        buffer.seek(0)
        return buffer.read()

    def _load_intro_chunks(self, sample_rate: int, sample_width: int, channels: int):
        if not INTRO_AUDIO_DIR.exists():
            return []

        chunks = []
        for path in sorted(INTRO_AUDIO_DIR.glob(INTRO_AUDIO_PATTERN)):
            if not path.is_file():
                continue
            role = path.stem.split("_", 1)[-1].upper()
            raw_bytes = path.read_bytes()
            wav_bytes = self._convert_to_standard_wav(raw_bytes)
            frames, num_frames, sr, sw, ch = self._wav_payload(wav_bytes)
            if (sr, sw, ch) != (sample_rate, sample_width, channels):
                raise ValueError(f"Intro sample {path.name} has incompatible audio format")
            chunks.append(
                {
                    "role": role,
                    "frames": frames,
                    "num_frames": num_frames,
                }
            )
        return chunks

    def _prepend_reference_intros(
        self,
        meeting_frames: bytes,
        sample_rate: int,
        sample_width: int,
        channels: int,
    ):
        intros = self._load_intro_chunks(sample_rate, sample_width, channels)
        if not intros:
            wav_bytes = self._build_wav([meeting_frames], sample_rate, sample_width, channels)
            return wav_bytes, [], 0

        silence_frames = int(sample_rate * INTRO_SILENCE_MS / 1000)
        silence_chunk = b"\x00" * silence_frames * sample_width * channels if silence_frames else b""

        frames_sequence: List[bytes] = []
        boundaries = []
        frame_cursor = 0

        for idx, intro in enumerate(intros):
            frames_sequence.append(intro["frames"])
            start_tick = self._frames_to_ticks(frame_cursor, sample_rate)
            frame_cursor += intro["num_frames"]
            end_tick = self._frames_to_ticks(frame_cursor, sample_rate)
            boundaries.append({"role": intro["role"], "start": start_tick, "end": end_tick})
            if silence_chunk:
                frames_sequence.append(silence_chunk)
                frame_cursor += silence_frames

        meeting_start_tick = self._frames_to_ticks(frame_cursor, sample_rate)
        frames_sequence.append(meeting_frames)

        combined_wav = self._build_wav(frames_sequence, sample_rate, sample_width, channels)
        return combined_wav, boundaries, meeting_start_tick

    def transcribe_content(self, content: bytes, extension: str) -> str:
        config = self._speech_config()
        wav_bytes = self._convert_to_standard_wav(content)
        meeting_frames, _, sample_rate, sample_width, channels = self._wav_payload(wav_bytes)
        combined_wav, intro_boundaries, meeting_start_tick = self._prepend_reference_intros(
            meeting_frames, sample_rate, sample_width, channels
        )
        audio_config, feed_audio = self._audio_config_from_wav(combined_wav)
        transcriber = speech_transcription.ConversationTranscriber(
            speech_config=config,
            audio_config=audio_config,
        )

        recognized_segments: List[str] = []
        done = threading.Event()
        canceled_error: List[str] = []
        speaker_roles: dict = {}

        def _label_for_speaker(speaker_id: int | None) -> str:
            if speaker_id is None:
                return "Speaker"
            return speaker_roles.get(speaker_id, f"Speaker {speaker_id}")

        def _role_for_offset(offset_ticks: int) -> str | None:
            for boundary in intro_boundaries:
                if boundary["start"] <= offset_ticks < boundary["end"]:
                    return boundary["role"]
            return None

        def _recognized_handler(evt: speech_transcription.ConversationTranscriptionEventArgs) -> None:
            result = evt.result
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = result.text.strip()
                if text:
                    offset_ticks = result.offset
                    speaker_id = getattr(result, "speaker_id", None)
                    role = _role_for_offset(offset_ticks)
                    if role and speaker_id is not None:
                        speaker_roles.setdefault(speaker_id, role)
                        return
                    if offset_ticks < meeting_start_tick:
                        return
                    label = _label_for_speaker(speaker_id)
                    recognized_segments.append(f"{label}: {text}")

        def _canceled_handler(evt: speech_transcription.ConversationTranscriptionCanceledEventArgs) -> None:
            cancellation_details = evt.result.cancellation_details
            if cancellation_details.reason == speechsdk.CancellationReason.EndOfStream:
                done.set()
                return

            error_details = getattr(cancellation_details, "error_details", "")
            message = f"Conversation transcription canceled: {cancellation_details.reason}"
            if error_details:
                message = f"{message}. {error_details}"
            canceled_error.append(message)
            done.set()

        def _stopped_handler(_: speechsdk.SessionEventArgs) -> None:
            done.set()

        transcriber.transcribed.connect(_recognized_handler)
        transcriber.canceled.connect(_canceled_handler)
        transcriber.session_stopped.connect(_stopped_handler)

        started = False
        try:
            transcriber.start_transcribing_async().get()
            feed_audio()
            started = True
            done.wait(timeout=60)
        finally:
            try:
                if started:
                    transcriber.stop_transcribing_async().get()
            finally:
                transcriber.transcribed.disconnect_all()

        if canceled_error:
            raise RuntimeError(canceled_error[0])
        if not recognized_segments:
            raise RuntimeError("No speech could be recognized.")

        return "\n".join(recognized_segments)


def transcribe_audio_if_needed(content: bytes, filename: str) -> str:
    """Transcribe supported audio files using Azure Speech Services."""
    extension = os.path.splitext(filename)[1].lower()
    assert extension in SUPPORTED_AUDIO_EXTENSIONS, f"Unsupported audio format: {extension}"
    transcriber = Transcriber()
    return transcriber.transcribe_content(content, extension)
