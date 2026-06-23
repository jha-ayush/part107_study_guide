# Content currency

This document records the regulatory baseline the question bank is written to,
the sources behind it, and the checks used to keep outdated material out. It is
the reference for anyone adding or reviewing questions.

Last reviewed: June 2026.

Display convention: because the bank is constantly evolving, all user-facing
bank counts (per-topic counts on the home screen, rule counts on the cheat
sheet) are shown softly, for example "130+", via the `soft_count` helper in
`app.py`. Counts that are the user's own data (exam scores, missed-question
counts) are shown exactly.

## Regulatory baseline

Questions reflect current United States federal rules for small unmanned
aircraft flown under Part 107:

- 14 CFR part 107, Small Unmanned Aircraft Systems (operating rules, pilot
  certification, waivers).
- 14 CFR part 89, Remote Identification of Unmanned Aircraft.
- 14 CFR parts 47 and 48, aircraft registration and marking.
- FAA Remote Pilot ACS, FAA-S-ACS-10B (current in 2026), which defines the
  knowledge areas and tasks tested on the Unmanned Aircraft General (UAG) test.
- Supporting references: AC 107-2A, the Remote Pilot sUAS Study Guide
  (FAA-G-8082-22), the Pilot's Handbook of Aeronautical Knowledge, and the
  Airman Knowledge Testing Supplement (FAA-CT-8080 series).

## Current rules incorporated

These post-2021 and later changes are reflected throughout the bank:

- Recurrent currency is met by free online training within the previous 24
  calendar months, not a proctored recurrent knowledge test (since April 2021).
- Night operations are allowed without a waiver when the aircraft has
  anti-collision lighting visible for at least 3 statute miles and the remote
  pilot has completed the required training.
- Operations over people are allowed without a waiver under Categories 1 to 4,
  each with its own requirements (impact-energy limits of 11 ft-lb for Category
  2 and 25 ft-lb for Category 3, a Declaration of Compliance for Categories 2
  and 3, and an airworthiness certificate for Category 4).
- Operations over moving vehicles are allowed under the same category framework.
- Remote ID has been required since 2023: a standard Remote ID drone, a
  broadcast module (operated within visual line of sight), or operation within
  an FAA-Recognized Identification Area (FRIA).
- Controlled airspace access is via prior authorization, typically through
  LAANC, bounded by the ceilings on the UAS Facility Maps.

Not yet incorporated as tested rules: BVLOS under the proposed Part 108, which
was still in rulemaking as of this review and is therefore treated only as a
future framework, not current law.

## Exam structure

The exam simulation mirrors the real test: 65 questions presented, 60 scored,
5 unscored experimental, 120-minute limit, 70 percent of the scored questions to
pass. The 60 scored questions are drawn in proportions modeled on the ACS
knowledge-area weighting:

| Topic        | Scored share |
|--------------|--------------|
| Operations   | 38%          |
| Regulations  | 20%          |
| Airspace     | 16%          |
| Weather      | 12%          |
| Loading      | 8%           |
| Charts       | 6%           |

The weights live in the `EXAM_BLUEPRINT` constant in `app.py` and are safe to
tune. Sectional chart reading is a skill folded into Airspace in the ACS, so
Charts carries a small share carved from the Airspace band.

## Currency guardrails

When adding or reviewing questions, none of the following outdated patterns
should appear (these were audited to zero at the last review):

- A recurrent knowledge test taken at a testing center, or recurrency satisfied
  by retesting rather than online training.
- Night flight described as waiver-only, prohibited, or daylight or civil
  twilight only.
- Operations over people described as prohibited or waiver-only rather than the
  Category 1 to 4 framework.
- Remote ID described as optional, future, or not required.
- The older $150 test fee (the current fee is about $175; avoid hardcoding fees
  in questions where possible).

## Adding questions

Each question is an object with this schema:

```
{ "b": bucket, "s": subtopic, "q": text, "c": [4 choices], "a": correct index 0-3, "e": one-sentence rule }
```

Buckets are Regulations, Airspace, Charts, Weather, Operations, and Loading.
Process for a new batch:

- Add in batches of roughly 20 to 40 at a time.
- Check every fact against the baseline above before adding.
- Deduplicate against existing question text (normalized, case-insensitive).
- Randomize the correct-answer position so answers are not clustered at one
  index, then confirm the answer-index distribution stays roughly even.
- Balance choice lengths. The correct answer must not be the single longest
  choice. Distractors should be plausible, clearly incorrect, and comparable in
  length to the correct answer, so an item tests knowledge rather than letting a
  test-taker pick the longest option. The real FAA test uses length-balanced
  choices, so a bank that does not will train the wrong habit.
- Avoid duplicates by concept, not just wording. Before adding, check that no
  existing question tests the same fact with the same answer, even if phrased
  differently. Two questions that teach the same point are a functional
  duplicate and should not both be in the bank.
- Validate the schema and re-run the app to confirm the home counts, study
  modes, and exam still work with the larger bank.

## Recent currency updates
- June 2026: ACS code mapping (complete). Tagged every question in the bank (Regulations,
  Airspace, Charts, Weather, Loading, and Operations) with FAA Airman Certification Standards task codes (for example
  UA.I.B Operating Rules, UA.II.A Airspace Classification, UA.II.B Airspace
  Operational Requirements, UA.III.B Effects of Weather, UA.IV.A Loading and
  Performance), shown next to each question during practice with
  the task title on hover, so a learner can map a question to the ACS task to
  study, the way the FAA Knowledge Test Report points to deficient codes. Note:
  FAA-S-ACS-10B was marked obsolete in August 2025 pending a refreshed ACS; the
  topics and the area/task code structure are unchanged, so task-level codes
  remain valid, but element-level codes (the K-numbers) are deferred until the
  updated document is published. A few questions filed under one topic test
  another area (a speed or altitude limit is a Regulations operating limitation)
  and were coded to their true area. All 548 questions now carry an ACS task
  code, shown during practice with the task title on hover.
- June 2026: Systematic dedup pass. Clustered the bank by answer concept
  (normalized correct answer within each topic) rather than by question
  wording, which surfaces duplicates that reworded questions hide. Reviewed
  every candidate cluster and removed 62 functional duplicates, keeping the
  clearest of each (the bank went from 610 to 548). Distinct questions that
  merely share answer wording (for example Category 2 vs Category 3 energy
  limits, sea breeze vs land breeze, the per-class line-color set) were kept.
  The subtopic labels shown under each practice question were also normalized,
  merging case and synonym variants (for example "Night Ops" and "Night
  operations") into one consistent label each.
- June 2026: Quality pass. Removed 26 duplicate questions (the bank went from
  636 to 610). Began a length-balance remediation: an audit found the correct
  answer was the single longest choice in about 80 percent of items (chance is
  about 25 percent), which lets a test-taker game the bank by length. The
  worst offenders are being rewritten in batches to give plausible, clearly
  incorrect, comparable-length distractors so the correct answer is no longer a
  length giveaway. The pass is complete: 247 items were rewritten across eight
  batches, lowering the correct-is-longest rate from about 80 percent to about 34
  percent. The pass stopped at the planned point, where no item has the correct
  answer more than about 20 characters longer than its longest distractor, so the
  pick-the-longest exploit is gone. The remaining share is normal length
  variation of a few characters, not a giveaway, and is left alone rather than
  padding distractors for a cosmetic number. Twenty-six functional duplicates
  (same question and answer, reworded) were removed along the way; a dedicated
  dedup pass by answer concept is the recommended next quality step.
- June 2026: Added a batch focused on loading and performance (maximum
  gross weight, weight and density-altitude effects, battery and
  temperature, propeller condition, center-of-gravity distribution) and
  weather reading (METAR sky and wind codes, altimeter, TAF, fog,
  thunderstorms and microbursts, density altitude, standard atmosphere),
  plus Operations items on emergency deviation and carriage of property.
- June 2026: Added a batch of Operations and aeronautical-decision-making
  scenarios (lost link, interference, IMSAFE, PAVE, hazardous-attitude
  antidotes, CTAF awareness), airspace items (Class B authorization,
  restricted and prohibited areas, MOAs, NOTAMs), sectional symbology
  (Class C and E depictions, Maximum Elevation Figure), and METAR reading.

- June 2026: Audited the full bank for pre-2021 content; none found. Added
  current questions covering operations over people Categories 1 to 4, over
  people at night, Declaration of Compliance, Part 89 Remote ID specifics, the
  broadcast module visual-line-of-sight rule, FRIA, and UAS Facility Map
  ceilings. Updated the exam to the 65/60 ACS-weighted structure.
