# Sub-workflow — Send Ticket Notification

## What it does
Reusable notification handler called by Workflow 3 and Workflow 4. 
Receives ticket or briefing data and posts a formatted message 
to Slack via webhook.

## Architecture
When Executed by Another Workflow → HTTP Request (Slack)

## Called by
- Workflow 3 (Ticket Triage) — posts ticket details per category
- Workflow 4 (Daily Briefing) — posts morning weather briefing

## Key nodes
| Node | Purpose |
|------|---------|
| When Executed by Another Workflow | Entry point, receives all data from parent |
| HTTP Request | Posts formatted message to Slack webhook |

## Why a sub-workflow
Centralises notification logic. Both parent workflows share one 
Slack node. Changes to message format only need to be made once.