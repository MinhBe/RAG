# Phase 6 Runtime Expansion Report — 7 Bot Profiles

## Bot mappings

| Bot profile | Telegram username | Role tags |
|---|---|---|
| lead | Swain_SubAgent_bot | orchestrator, planner |
| scout | Shen_SubAgent_bot | research, analyst, monitor |
| builder_core | Garen_SubAgent_bot | implementation |
| builder_ui | Taric_SubAgent_bot | implementation, design_publishing |
| reviewer | Jarvan_SubAgent_bot | reviewer, documentation |
| sentinel | Sylas_SubAgent_bot | security, critic |
| validator | Lucian_SubAgent_bot | validator |

## Runtime commands

- `/whoami`: current bot identity, role tags, permission ceiling.
- `/skills`: allowed skills for current bot profile.
- `/skills-all`: access matrix across all 7 bot profiles.

## Status

Runtime adapter now scopes skill inventory by receiver bot username. General chat also receives bot-scoped skill context before the LLM route.
