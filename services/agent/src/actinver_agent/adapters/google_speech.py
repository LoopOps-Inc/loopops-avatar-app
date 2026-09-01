"""Streaming speech-to-text via Google Cloud Speech v2 (Vertex platform, ADR-0003).

Partials matter for latency: routing runs speculatively on the partial
transcript while the client is still speaking. Provider SDK imports live here
only (ADR-0011).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog
from google.cloud import speech_v2 as speech

from actinver_agent.ports import Transcript

log = structlog.get_logger(__name__)


class GoogleSpeechToText:
    def __init__(
        self,
        *,
        project_id: str,
        location: str = "global",
        language: str = "es-MX",
        model: str = "latest_long",
        phrase_hints: tuple[str, ...] = (),
        sample_rate_hz: int = 16_000,
    ) -> None:
        self._client = speech.SpeechAsyncClient()
        self._recognizer = f"projects/{project_id}/locations/{location}/recognizers/_"
        self._config = speech.RecognitionConfig(
            explicit_decoding_config=speech.ExplicitDecodingConfig(
                encoding=speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate_hz,
                audio_channel_count=1,
            ),
            language_codes=[language],
            model=model,
            features=speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_confidence=True,
            ),
            adaptation=_adaptation(phrase_hints) if phrase_hints else None,
        )
        self._language = language

    async def stream(self, audio_frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        streaming_config = speech.StreamingRecognitionConfig(
            config=self._config,
            streaming_features=speech.StreamingRecognitionFeatures(
                interim_results=True,
                enable_voice_activity_events=True,
            ),
        )

        async def requests() -> AsyncIterator[speech.StreamingRecognizeRequest]:
            yield speech.StreamingRecognizeRequest(
                recognizer=self._recognizer, streaming_config=streaming_config
            )
            async for frame in audio_frames:
                yield speech.StreamingRecognizeRequest(audio=frame)

        responses = await self._client.streaming_recognize(requests=requests())
        async for response in responses:
            for result in response.results:
                if not result.alternatives:
                    continue
                best = result.alternatives[0]
                yield Transcript(
                    text=best.transcript,
                    is_final=result.is_final,
                    confidence=best.confidence or 0.0,
                    language=result.language_code or self._language,
                )


def _adaptation(hints: tuple[str, ...]) -> speech.SpeechAdaptation:
    """Mexican financial vocabulary and ticker names are materially better
    recognised with explicit phrase hints (ADR-0013)."""
    return speech.SpeechAdaptation(
        phrase_sets=[
            speech.SpeechAdaptation.AdaptationPhraseSet(
                inline_phrase_set=speech.PhraseSet(
                    phrases=[speech.PhraseSet.Phrase(value=h, boost=12.0) for h in hints]
                )
            )
        ]
    )
