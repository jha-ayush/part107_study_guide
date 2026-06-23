# Part 107 Ground School

A FAA Part 107 knowledge-test prep app, built as a server-rendered Python
(Flask) web app. All logic runs in Python: page rendering, answer checking,
scoring, the exam timer, accounts, and progress tracking. There is no
client-side application JavaScript.

It ships in two equivalent forms:

- A multi-file project (`app.py` plus `templates/` and `static/`).
- A single self-contained file (`main.py`) with the questions and all HTML and
  CSS embedded, for the simplest possible run and share.

## Run it locally

Multi-file version:

```
bash run-local.sh
```

That creates a virtual environment, installs Flask, and starts the server at
http://127.0.0.1:8000. By hand:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Single-file version:

```
pip install flask
python main.py
```

Either way, open http://127.0.0.1:8000.

## Study modes

- Learn: flashcard-style reading through a topic, showing each question with the
  correct answer and the rule, no quiz. Ends by handing off to a quiz.
- Practice: one question at a time with instant feedback and the rule. Filter by
  topic or practice all topics.
- Focus: practice weighted toward your lowest-scoring and not-yet-seen topics.
- Drill: replays the specific questions you have missed, weighted toward the ones
  you miss most. Questions leave the list once you answer them correctly.
- Exam: a timed simulation of 65 questions (60 scored plus 5 unscored
  experimental, mirroring the real test), 120-minute limit, 70 percent of the
  scored questions to pass. Questions are drawn in FAA ACS topic proportions
  (Operations and Regulations weighted heaviest), with a question palette,
  previous/next, a by-topic breakdown, and a missed list. After grading, the result breaks your
  misses down by FAA ACS task, the way the real Knowledge Test Report does.
- Study list: every missed question grouped by topic, with lifetime accuracy.
- Progress: an exam history page with a readiness verdict, best score, recent
  average, pass rate, and a score-trend chart with the pass line drawn in.
- Cheat sheet: every distinct rule grouped by topic, plus a visual sectional
  chart symbology legend (airport, airspace, obstacle, and navigation symbols
  drawn in chart-accurate blue and magenta), print-optimized for
  last-minute review (use Cmd or Ctrl + P).
- ACS study sheet: a personalized, printable page of your weak FAA ACS tasks
  and the rules to review under each, built from the questions you have
  missed and ordered by how often.

Topics are Regulations, Airspace, Charts, Weather, Operations, and Loading. The
bank currently holds 560+ questions, each tagged with its FAA ACS task code. Some
chart questions include an original sectional-excerpt figure to read, and the
cheat sheet carries a visual symbology legend; you can also practice just the
chart-reading figures from the home screen. Per-topic mastery badges and a
dark mode are built in.

## Content currency

Question content is written to current federal rules: 14 CFR parts 89 (Remote
ID) and 107, aligned to the FAA Remote Pilot ACS (FAA-S-ACS-10B, current in
2026). This includes the post-2021 rules for night operations, operations over
people (Categories 1 to 4), operations over moving vehicles, and the Remote ID
requirement in effect since 2023. The exam simulation follows the ACS
knowledge-area weighting. See `CONTENT_CURRENCY.md` for the full baseline,
sources, last-reviewed date, and the checks used to keep outdated material out.

## Accounts and progress

Without an account, progress is stored on the server keyed to a cookie in your
browser, so it persists on that machine. Create an account (`/register`) or sign
in (`/login`) with your email to make progress follow you across devices. When
you first sign in, any anonymous progress on that browser migrates into your
account.

Accounts are stored in `users.json` with hashed passwords, and progress in
`progress_store.json`, both kept out of version control. The session secret is
read from the `FLASK_SECRET_KEY` environment variable, falling back to a local
`.flask_secret` file for development. Set `FLASK_SECRET_KEY` in production.

All POST forms (sign in, register, sign out, answer, exam navigation, reset) are
protected against cross-site request forgery with a per-session token.

The exam timer is enforced on the server. The remaining time is shown each time
a page loads; since there is no JavaScript, it does not tick live between loads.

## Project structure

```
part107_study_guide/
  app.py                 Flask app and all logic (multi-file entry point)
  main.py                single-file build (questions, HTML, and CSS embedded)
  questions.json         the question bank
  requirements.txt       Python dependencies
  Procfile               process command for hosts like Render
  run-local.sh           one-command local run
  templates/             Jinja templates
    base.html  home.html  learn.html  practice.html  exam.html
    exam_result.html  review.html  history.html  cheatsheet.html
    studysheet.html
    login.html  register.html
  static/
    styles.css           styling
    icons/               app icons (used for the browser tab)
  README.md  CONTENT_CURRENCY.md  .gitignore  LICENSE
```

## Edit the question bank

Open `questions.json`. Each entry:

```
{ "b": "Weather", "s": "METAR", "q": "Question text",
  "c": ["A", "B", "C", "D"], "a": 1, "e": "The rule.",
  "acs": "UA.III.A", "fig": "sectional_poc_1" }
```

`b` is the bucket (Regulations, Airspace, Charts, Weather, Operations, Loading),
`s` a subtopic, `c` the four choices, `a` the index of the correct choice (0 to
3), `e` the one-sentence rule. `acs` (optional) is the FAA ACS task code shown
with the question and on the review screen. `fig` (optional) names an entry in the
`FIGURES` registry in `app.py`, an original SVG sectional excerpt rendered above
the question. Restart the server to load changes. The exam size, pass mark, and
time limit are constants near the top of `app.py`.

After editing the multi-file version, regenerate `main.py` if you want the
single-file build to match, or just edit the one you use.

Before adding questions, see `CONTENT_CURRENCY.md` for the rule baseline, the
ACS-aligned exam weighting, and the currency checks that keep outdated content
out of the bank.

## Deploy

The `Procfile` runs the app under gunicorn bound to the host port
(`web: gunicorn app:app --bind 0.0.0.0:${PORT:-8000}`), which works on hosts like
Render. Set `FLASK_SECRET_KEY` as an environment variable in production.

One caveat to plan for: the file-based `users.json` and `progress_store.json`
live on the local disk, which most hosts reset on every deploy or restart. For a
hosted, multi-user deployment, put that data on a persistent disk or move it to a
database (for example SQLite on a persistent disk, or managed Postgres) so
accounts and progress survive redeploys.
