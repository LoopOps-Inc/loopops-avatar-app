---
title: Writing Style Guide
scope: agents
last-updated: 2026-09-01
source: ../loopops-web-app/knowledge/writing-style.md
---

# Writing Style Guide

Canonical prose rules for Cursor, Copilot, Gemini, Claude, and other coding agents.
IDE mirrors: `.cursor/rules/writing-style.mdc`, `GEMINI.md`.

## Context

Rewrite AI-generated or overly formal text so it sounds natural, professional, and easy to read. Keep the original meaning and tone.

**Use this guide when writing or rewriting:**

- User-facing copy (i18n strings, empty states, toasts, modals)
- Knowledge docs, README, comments meant for humans
- PR descriptions and commit messages

**Do not use this guide for:**

- Code identifiers, API names, or file paths

When adding UI copy as part of a coding task, match nearby strings. Do not stop to ask tone questions.

## Architecture

`knowledge/writing-style.md` is the source of truth. IDE instruction files only mirror format and link here.

## Patterns

### Clarity

- Use clear, direct phrasing.
- Keep sentences short.
- Remove redundancy and filler.

### Tone

- Sound professional and approachable.
- Avoid jargon unless needed. If you use it, explain it briefly.
- Use active voice.
- Vary sentence length so it reads naturally.
- No emojis.
- No em dashes. Use periods or commas instead.
- Default to an eighth-grade reading level unless the topic requires more technical detail.

### Do

- Use contractions when they fit.
- Match the tone to the context (formal, conversational, academic).
- Keep structure logical and easy to scan.

### Don't

- Add new facts or remove key details.
- Use marketing language, hype, or clichés.
- Overcomplicate sentences.
- Make it overly casual unless asked.

## Gotchas

### Avoid list

- Filler openers like "In today's fast moving world."
- Filler phrases like "It's important to note that."
- Clichés and corporate jargon like "touch base," "move the needle," "mission-critical."
- Hashtags, semicolons, emojis, and asterisks.
- Overuse of hedging (might, may, could) when you can be direct.
- "In conclusion," "in summary," "in general."

### Word blacklist

Avoid these words when possible:

actually, certainly, could, maybe, may, just, truly, very, believe, esteemed, seem, imagine, really, unveil, pivot, intricate, however, moreover, furthermore, in addition, therefore, thus, consequently, leverage, optimize, cutting-edge, dynamic, seamlessly, holistic, granular, synergy, paradigm, implement, utilize, in-depth, robust, enterprise, aspirational, always, never, everyone, unprecedented, revolutionary, fundamentally, absolutely, stuff, things, many, various
