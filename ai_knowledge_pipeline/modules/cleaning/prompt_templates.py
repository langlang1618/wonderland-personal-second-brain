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

Raw transcript:
{transcript_text}
"""

OPENAI_CLEANING_JSON_SCHEMA_HINT = """\
Return this JSON shape:
{
  "title": "string",
  "summary": "string",
  "cleaned_text": "string",
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
