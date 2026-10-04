# Runtime Enforcement Report

This report records the post-resolver enforcement layer.

## Deterministic Telegram commands

The following commands are handled in adapter code and do not route through the LLM:

- /whoami
- /skills
- /skills-all
- /health

A single Telegram message containing multiple deterministic commands returns one TelegramReply per command. This prevents the model from rephrasing command output or merging it into persona text.

## Runtime guard checks

Implemented guard paths:

- skill invocation: /skill, /run-skill, /use-skill, un skill, chay, dung, chay skill
- repo-write attempt: write/edit/commit/file/repo/code patterns

Expected adversarial results:

- Lucian_SubAgent_bot chay omh-ralph => blocked because validator does not wear implementation.
- Swain_SubAgent_bot write file to repo => blocked because Lead ceiling is 	ask_create, below epo_write.
- Swain_SubAgent_bot chay omh-autopilot => blocked as direct execution because omh-autopilot is composite and must_delegate=true.

## Remaining boundary

Allowed skill invocation still does not execute arbitrary plugin code. Execution requires a supported mission/case runner with traceable inputs.
