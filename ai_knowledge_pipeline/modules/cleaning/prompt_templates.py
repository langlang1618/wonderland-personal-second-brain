"""Prompt templates for transcript cleaning providers."""

OPENAI_CLEANING_SYSTEM_PROMPT = """\
You are a production transcript-cleaning engine for an AI knowledge pipeline.
Return only valid JSON matching the requested schema. Do not include markdown
fences or explanatory prose outside the JSON object.
"""

OPENAI_CLEANING_TASK_TEMPLATE = """\
Clean and structure the transcript for downstream Markdown, Obsidian, vector
database, RAG, and agent memory consumers.

Required capabilities:
- repair typos and transcription errors
- repair terminology
- remove redundant spoken filler
- produce readable_transcript_text as a lightly repaired readable transcript
- extract chapters
- write a concise summary
- extract key insights
- extract action items
- generate semantic tags
- extract agent memory candidates

Language: {language}
Prompt version: {prompt_version}
Terminology: {terminology}
Output requirements: {output_requirements}
Style guide: {style_guide}

Readable transcript constraints:
- output readable_transcript_text in Simplified Chinese
- readable_transcript_text is not a summary
- readable_transcript_text does not replace raw_transcript; the system preserves raw_transcript separately
- keep the original lecture order and knowledge details
- do not compress, summarize, rewrite, or reorganize the speaker's logic
- add Chinese punctuation, natural paragraphs, and section headings
- only lightly repair Traditional/Simplified conversion, punctuation, paragraphing, obvious typos, accent errors, and terminology
- remove only obvious greetings, course welcome chatter, livestream interaction, and content-free small talk
- preserve meaning and the original sequence of knowledge-bearing statements
- do not delete knowledge details

Raw transcript:
{transcript_text}
"""

OPENAI_CLEANING_JSON_SCHEMA_HINT = """\
Return this JSON shape:
{
  "title": "string",
  "summary": "string",
  "cleaned_text": "string",
  "readable_transcript_text": "string",
  "chapters": [
    {
      "title": "string",
      "summary": "string",
      "start_time": 0.0,
      "end_time": 0.0,
      "semantic_tags": ["string"],
      "blocks": [
        {"kind": "paragraph", "text": "string", "heading_level": null}
      ]
    }
  ],
  "key_insights": [
    {"text": "string", "confidence": 0.0, "tags": ["string"]}
  ],
  "action_items": [
    {"text": "string", "owner": null, "due": null}
  ],
  "semantic_tags": ["string"],
  "agent_memory_candidates": [
    {"text": "string", "memory_type": "string", "importance": 0.0, "tags": ["string"]}
  ],
  "confidence": 0.0
}
"""

__all__ = [
    "OPENAI_CLEANING_JSON_SCHEMA_HINT",
    "OPENAI_CLEANING_SYSTEM_PROMPT",
    "OPENAI_CLEANING_TASK_TEMPLATE",
]
