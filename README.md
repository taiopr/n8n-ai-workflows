# n8n AI Workflows

A collection of automated workflows built with n8n during a structured AI integration learning program. Each workflow demonstrates a different automation pattern using LLM integration, file processing, form handling, and scheduled tasks.

## Workflows

### Workflow 1 — LLM + Slack Notification
Calls an LLM via API, formats the response, and posts it to Slack.
**Patterns:** HTTP Request, LLM integration, webhook output
[View workflow →](./workflow-1-llm-slack/)

### Workflow 2 — Automated File Summariser
Watches a Google Drive folder. When a file appears, extracts the text, summarises it with an LLM, and saves the summary as a new file.
**Patterns:** Event trigger, file I/O, binary data handling, error handling
[View workflow →](./workflow-2-file-summariser/)

### Workflow 3 — Support Ticket Triage
A form submission triggers LLM classification into billing, technical, or general. Routes to the correct branch and notifies the team via Slack.
**Patterns:** Form trigger, LLM classification, conditional routing, sub-workflows
[View workflow →](./workflow-3-ticket-triage/)

### Workflow 4 — Daily Briefing
Runs every morning at 8am. Fetches live weather data, generates a human-readable briefing with an LLM, and posts it to Slack.
**Patterns:** Scheduled trigger, external API, LLM generation, sub-workflow reuse
[View workflow →](./workflow-4-daily-briefing/)

### Workflow 5 — Compound Image Generation Pipeline
The flagship project. n8n webhook → FastAPI → ComfyUI → Slack.
Fully automated image generation with error handling, reliability
testing, and direct Slack image upload.
**Patterns:** Webhook trigger, Python microservice, ComfyUI API,
callback pattern, non-blocking background tasks
[View workflow →](./workflow-5-image-generator/)

## Sub-workflows

### Send Ticket Notification
Reusable notification handler called by Workflow 3 and Workflow 4. Receives ticket or briefing data and posts a formatted message to Slack.
[View sub-workflow →](./sub-workflows/send-ticket-notification/)

## Stack
- n8n (local install)
- OpenAI GPT-4o-mini
- Google Drive API
- Slack Incoming Webhooks
- Open-Meteo Weather API

## Setup
Each workflow folder contains a `workflow.json` file that can be imported directly into n8n via Settings → Import from File. You will need to configure your own credentials for OpenAI, Google Drive, and Slack.
