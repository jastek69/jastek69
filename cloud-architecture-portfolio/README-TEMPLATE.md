<!--
README-TEMPLATE.md — the standard README structure for every repository.

HOW TO USE
  1. Copy this file to the target repo as README.md.
  2. Fill every section. Delete the HTML comments as you go.
  3. Do NOT add, remove, reorder, or rename the ten H1/H2 sections.
     Sub-headings (H3) inside a section are free-form.
  4. Anything that does not fit a section belongs in docs/, linked from
     Repository Structure — not appended to the end of the README.

THE TEST
  A README describes what the system IS and WHY it is that way.
  Procedures, walkthroughs, CLI recipes, tuning knobs, and reference links
  are documentation — they go in docs/. If a section is growing past a
  screen or two, that is the signal to move it.
-->

# <Project Name>

<!-- Optional: badges, hero image, one-line subtitle, credits. -->

---

# Executive Summary

<!--
Two or three paragraphs. Written for someone who will decide in 30 seconds
whether to keep reading — a hiring manager, a reviewer, a future you.

Answer: what is this, what does it demonstrate, and how big is it?
End with a concrete scale marker (resource count, service count, LOC) and
say how correctness is verified.

No marketing language. No "leveraging cutting-edge".
-->

---

## Problem

<!--
What was broken, missing, or hard BEFORE this existed.

Two to four bullets, each naming a specific failure mode rather than a
general topic. "Authorization is usually one layer deep" beats "security
is important". If you cannot name the failure, you do not have a problem
statement yet — you have a feature list.
-->

---

## Solution

<!--
How this system answers each problem above, at the level of approach
rather than implementation.

Close with the governing constraint or design rule — the one sentence
that explains the most decisions in the codebase. Examples:
  "Bedrock explains, it never authorizes."
  "Every write is idempotent; redelivery is assumed, not prevented."
-->

---

## Architecture

<!--
Lead with an ASCII diagram of the primary request or data flow. Keep it
under ~25 lines; put alternate flows and detail diagrams in docs/.

Then the structural decisions a reader needs to hold in their head —
layering, trust boundaries, what talks to what. Tables work well for
enumerating layers or components.

Link out for depth: "Full treatment in docs/architecture.md".
-->

```
<primary flow diagram>
```

---

## Technologies

<!--
A table, grouped by domain — not a flat alphabetical list. Note the
non-obvious choice where there is one (e.g. "S3-native locking, no
DynamoDB lock table"). Versions only where they actually matter.
-->

| Domain | Services |
|---|---|
| | |

---

## Deployment

<!--
The commands to stand it up, plus every prerequisite that is not
discoverable from the code — required shell, tools on PATH, account-level
access that must be granted out of band, environment quirks.

Include teardown, and state the idle cost if leaving it running is
expensive.

This is the shortest path to a working deploy, NOT the full runbook.
Detailed procedures go in RUNBOOK.md.
-->

```bash
<deploy commands>
```

---

## Security

<!--
State the security MODEL as explicit assumptions — what each layer is
responsible for, and just as importantly what it is NOT responsible for.
Misplaced assumptions are the usual root cause of a security bug.

Then: what is never stored, and what controls are actually in place.
Claim only what is implemented. If something is aspirational it belongs
in Future Improvements.
-->

---

## Repository Structure

<!--
An annotated tree of top-level directories — what each holds, one line
each. Skip build artifacts and vendored dependencies.

Follow with a table of every document in docs/ and what it covers. This
table is the index for everything displaced from the README; keep it
current when adding a doc.
-->

```
.
├──
└──
```

| Document | Covers |
|---|---|
| | |

---

## Lessons Learned

<!--
The findings that cost real time — the things you would tell someone
starting this project. Bold lead-in, then two or three sentences of
specifics.

Prefer non-obvious over textbook. "Silent fallbacks hide real failures"
with the incident that proved it beats "test your code". Include the
symptom, since that is what a future reader will be searching for.

Honest entries are the point. A section with no surprises in it is a
section nobody will read.
-->

---

## Future Improvements

<!--
Known gaps and next steps, each with enough context to act on. Say why it
matters or what it unblocks — a bare "add tests" is not actionable.

Include known limitations, not just planned features. If part of the
system is blind to a case, say so here rather than leaving a reader to
find out.
-->
