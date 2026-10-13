import json
import re

from app.core.config import get_settings
from app.providers.aws import (
    bedrock_runtime_client,
)


FILLER_PHRASES = (
    "hello everyone",
    "good morning",
    "good afternoon",
    "thank you",
    "thanks everyone",
    "give me a thumbs up",
    "please give me a thumbs up",
    "can you hear me",
    "am i audible",
    "very good",
    "excellent",
    "next topic",
    "next question",
    "have you written this down",
)


KIND_BONUS = {
    "diagnosis": 8,
    "treatment": 8,
    "management": 8,
    "complication": 7,
    "mechanism": 6,
    "definition": 6,
    "criteria": 6,
    "finding": 6,
    "investigation": 5,
    "comparison": 5,
    "procedure": 5,
    "takeaway": 8,
    "concept": 5,
    "evidence": 4,
    "other": 0,
}


def tokens(
    text: str,
) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
        if len(token) > 3
    }


def similarity(
    a: str,
    b: str,
) -> float:
    aa = tokens(a)
    bb = tokens(b)

    if not aa or not bb:
        return 0.0

    return (
        len(aa & bb)
        / min(
            len(aa),
            len(bb),
        )
    )


def is_filler(
    segment: dict,
) -> bool:
    text = (
        segment["text"]
        .lower()
        .strip()
    )

    if len(text.split()) <= 2:
        return True

    return any(
        phrase in text
        for phrase in FILLER_PHRASES
    )


def extract_json(
    text: str,
) -> dict:
    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end < start:
        raise ValueError(
            "Bedrock response did not contain JSON."
        )

    return json.loads(
        text[
            start:
            end + 1
        ]
    )


def bedrock_json(
    prompt: str,
    max_tokens: int = 5000,
) -> dict:
    settings = get_settings()

    response = (
        bedrock_runtime_client()
        .converse(
            modelId=(
                settings
                .bedrock_model_id
            ),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text":
                                prompt
                        }
                    ],
                }
            ],
            inferenceConfig={
                "temperature": 0.0,
                "maxTokens":
                    max_tokens,
            },
        )
    )

    content = (
        response
        .get("output", {})
        .get("message", {})
        .get("content", [])
    )

    text = "".join(
        item.get(
            "text",
            "",
        )
        for item in content
        if isinstance(
            item,
            dict,
        )
    )

    return extract_json(
        text
    )


def score_segments(
    segments: list[dict],
) -> list[dict]:
    source = [
        item
        for item in segments
        if not is_filler(
            item
        )
    ]

    scored = []

    for offset in range(
        0,
        len(source),
        40,
    ):
        batch = source[
            offset:
            offset + 40
        ]

        compact = [
            {
                "id":
                    item["id"],
                "start":
                    item["start"],
                "end":
                    item["end"],
                "text":
                    item["text"],
            }
            for item in batch
        ]

        prompt = f"""
You are an expert educational video editor.

Analyze the supplied transcript passages from a teaching
video and score their educational value.

The purpose is to automatically create a concise
"highly important learning points" video.

Importance scale:

90-100:
Critical teaching point. Omitting it risks losing an
essential concept.

75-89:
High-value teaching content.

60-74:
Useful supporting explanation.

45-59:
Optional context.

Below 45:
Do not return the passage.

Prioritize:
- definitions
- core concepts
- mechanisms
- diagnosis
- clinical findings
- investigations
- treatment
- management
- indications
- contraindications
- complications
- classifications
- criteria
- comparisons
- practical procedures
- examination/high-yield facts
- conclusions and key takeaways

Strongly penalize:
- greetings
- audience interaction
- repetition
- administrative comments
- transitions
- conversational filler
- questions without their answer

If a question and its answer occur in separate segments,
prefer the answer or the complete explanatory segment.

For each useful segment return:
- id
- importance
- critical
- topic
- kind
- reason
- learning_point

learning_point must be a concise factual learning note,
not a copy of conversational transcript language.

Allowed kinds:
concept
definition
mechanism
diagnosis
finding
investigation
treatment
management
complication
criteria
comparison
procedure
takeaway
evidence
other

Return JSON only:

{{
  "items": [
    {{
      "id": 21,
      "importance": 94,
      "critical": true,
      "topic": "short topic",
      "kind": "diagnosis",
      "reason": "short reason",
      "learning_point": "concise factual teaching point"
    }}
  ]
}}

Never create an ID that is not supplied.

TRANSCRIPT:
{json.dumps(compact, ensure_ascii=False)}
"""

        response = bedrock_json(
            prompt
        )

        by_id = {
            int(item["id"]):
                item
            for item in batch
        }

        for analysis in (
            response.get(
                "items",
                []
            )
            or []
        ):
            try:
                item_id = int(
                    analysis["id"]
                )

                importance = int(
                    analysis.get(
                        "importance",
                        0,
                    )
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            if item_id not in by_id:
                continue

            if importance < 45:
                continue

            original = dict(
                by_id[item_id]
            )

            critical_value = (
                analysis.get(
                    "critical",
                    False,
                )
            )

            if isinstance(
                critical_value,
                str,
            ):
                critical = (
                    critical_value
                    .lower()
                    .strip()
                    in {
                        "true",
                        "yes",
                        "1",
                    }
                )

            else:
                critical = bool(
                    critical_value
                )

            original.update({
                "importance":
                    max(
                        1,
                        min(
                            importance,
                            100,
                        ),
                    ),

                "critical":
                    critical,

                "topic":
                    str(
                        analysis.get(
                            "topic",
                            "Learning point",
                        )
                    ).strip(),

                "kind":
                    str(
                        analysis.get(
                            "kind",
                            "other",
                        )
                    ).strip(),

                "reason":
                    str(
                        analysis.get(
                            "reason",
                            "",
                        )
                    ).strip(),

                "learning_point":
                    str(
                        analysis.get(
                            "learning_point",
                            "",
                        )
                    ).strip(),
            })

            original["duration"] = (
                float(
                    original["end"]
                )
                - float(
                    original["start"]
                )
            )

            scored.append(
                original
            )

    return scored


def topic_key(
    item: dict,
) -> str:
    value = (
        item.get(
            "topic"
        )
        or item["text"]
    )

    return " ".join(
        sorted(
            tokens(value)
        )[:6]
    )


def select_segments(
    candidates: list[dict],
    target_seconds: int,
) -> list[dict]:
    if not candidates:
        return []

    maximum = float(
        target_seconds
    )

    minimum = maximum * 0.65
    preferred = maximum * 0.82

    selected = []
    selected_ids = set()
    selected_topics = set()

    used = 0.0

    def duplicate_score(
        candidate,
    ):
        if not selected:
            return 0.0

        return max(
            similarity(
                candidate["text"],
                existing["text"],
            )
            for existing
            in selected
        )

    def add(candidate):
        nonlocal used

        selected.append(
            candidate
        )

        selected_ids.add(
            candidate["id"]
        )

        selected_topics.add(
            topic_key(
                candidate
            )
        )

        used += (
            candidate[
                "duration"
            ]
        )

    critical = sorted(
        (
            item
            for item in candidates
            if item.get(
                "critical"
            )
        ),
        key=lambda item: (
            -item["importance"],
            item["start"],
        ),
    )

    for candidate in critical:
        if (
            used
            + candidate["duration"]
            > maximum
        ):
            continue

        if duplicate_score(
            candidate
        ) >= 0.82:
            continue

        add(candidate)

    remaining = [
        item
        for item in candidates
        if item["id"]
        not in selected_ids
    ]

    while (
        remaining
        and used < preferred
    ):
        best = None
        best_score = None

        for candidate in remaining:
            duration = (
                candidate[
                    "duration"
                ]
            )

            if (
                used
                + duration
                > maximum
            ):
                continue

            duplicate = (
                duplicate_score(
                    candidate
                )
            )

            if duplicate >= 0.78:
                continue

            topic = topic_key(
                candidate
            )

            score = float(
                candidate[
                    "importance"
                ]
            )

            if (
                topic
                not in selected_topics
            ):
                score += 11

            score += KIND_BONUS.get(
                str(
                    candidate.get(
                        "kind",
                        "other",
                    )
                ).lower(),
                0,
            )

            score += (
                8
                * (
                    1.0
                    - duplicate
                )
            )

            if candidate.get(
                "critical"
            ):
                score += 12

            if duration <= 16:
                score += 2

            if (
                best_score is None
                or score > best_score
            ):
                best = candidate
                best_score = score

        if best is None:
            break

        if (
            best["importance"] < 56
            and used >= minimum
        ):
            break

        add(best)

        remaining = [
            item
            for item in remaining
            if item["id"]
            != best["id"]
        ]

    if used < minimum:
        supporting = sorted(
            (
                item
                for item in candidates
                if (
                    item["id"]
                    not in selected_ids
                    and item["importance"]
                    >= 54
                )
            ),
            key=lambda item: (
                -item["importance"],
                item["start"],
            ),
        )

        for candidate in supporting:
            if used >= minimum:
                break

            if (
                used
                + candidate["duration"]
                > maximum
            ):
                continue

            if duplicate_score(
                candidate
            ) >= 0.74:
                continue

            add(candidate)

    exceptional = sorted(
        (
            item
            for item in candidates
            if (
                item["id"]
                not in selected_ids
                and (
                    item["importance"]
                    >= 90
                    or item.get(
                        "critical"
                    )
                )
            )
        ),
        key=lambda item: (
            -item["importance"],
            item["start"],
        ),
    )

    for candidate in exceptional:
        if (
            used
            + candidate["duration"]
            > maximum
        ):
            continue

        if duplicate_score(
            candidate
        ) >= 0.76:
            continue

        add(candidate)

    selected.sort(
        key=lambda item:
            item["start"]
    )

    return selected


def build_notes(
    selected: list[dict],
) -> dict:
    ranked = sorted(
        selected,
        key=lambda item:
            -item["importance"],
    )

    bullets = []
    seen = set()

    for item in ranked:
        note = (
            item.get(
                "learning_point"
            )
            or item.get(
                "text",
                "",
            )
        ).strip()

        normalized = (
            note.lower()
        )

        if (
            not note
            or normalized in seen
        ):
            continue

        seen.add(
            normalized
        )

        bullets.append(
            note
        )

        if len(bullets) >= 10:
            break

    return {
        "title":
            "High-value learning points",

        "bullets":
            bullets,
    }


def generate_summary(
    segments: list[dict],
    target_seconds: int,
) -> dict:
    candidates = score_segments(
        segments
    )

    selected = select_segments(
        candidates,
        target_seconds,
    )

    selected_seconds = sum(
        float(
            item["duration"]
        )
        for item in selected
    )

    topics = []

    for item in sorted(
        selected,
        key=lambda value:
            -value["importance"],
    ):
        topic = (
            item.get(
                "topic",
                ""
            )
            .strip()
        )

        if (
            topic
            and topic not in topics
        ):
            topics.append(
                topic
            )

    result_segments = []

    for item in selected:
        result_segments.append({
            "id":
                item["id"],

            "start":
                item["start"],

            "end":
                item["end"],

            "start_word_id":
                item.get(
                    "start_word_id"
                ),

            "end_word_id":
                item.get(
                    "end_word_id"
                ),

            "text":
                item["text"],

            "importance":
                item["importance"],

            "critical":
                item["critical"],

            "topic":
                item.get(
                    "topic",
                    "",
                ),

            "kind":
                item.get(
                    "kind",
                    "other",
                ),

            "reason":
                item.get(
                    "reason",
                    "",
                ),

            "learning_point":
                item.get(
                    "learning_point",
                    "",
                ),
        })

    return {
        "selected_segments":
            result_segments,

        "notes":
            build_notes(
                selected
            ),

        "coverage_topics":
            topics[:15],

        "candidate_count":
            len(candidates),

        "selected_seconds":
            round(
                selected_seconds,
                3,
            ),

        "budget_usage_pct":
            round(
                (
                    selected_seconds
                    / target_seconds
                    * 100
                )
                if target_seconds
                else 0,
                2,
            ),
    }
