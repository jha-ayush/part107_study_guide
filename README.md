# Part 107 Ground School

A FAA Part 107 knowledge-test prep app, built as a server-rendered Python
(Flask) web app. All logic runs in Python: page rendering, answer checking,
scoring, the exam timer, and progress tracking. There is no client-side
application JavaScript.

## Structure

```
part107_study_guide/
  app.py                 Flask app and all logic (entry point)
  questions.json         the 400-question bank
  requirements.txt       Python dependencies
  Procfile               process command for hosts like Render
  run-local.sh           one-command local run
  templates/             Jinja templates
    base.html  home.html  practice.html  exam.html  exam_result.html  review.html
  static/
    styles.css           styling
    icons/               app icons (used for the browser tab)
  README.md
  .gitignore  LICENSE
```

## Run it locally

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

## How it works

- `/` is the dashboard: lifetime accuracy, questions answered, study-list size,
  and per-topic mastery.
- `/practice?bucket=Weather` serves one question, checks your answer on submit,
  shows the rule, and links to the next.
- `/exam/start` builds a {exam_n}-question timed exam; you answer one per page
  with a question palette and previous/next, then it grades against {exam_pass}%.
- `/review` shows lifetime accuracy and your missed questions grouped by topic.

## Accounts and progress

Without an account, progress is stored on the server keyed to a cookie in your
browser, so it persists on that machine. Create an account (`/register`) or sign
in (`/login`) to make progress follow you across devices. When you first sign
in, any anonymous progress on that browser migrates into your account.

Accounts are stored in `users.json` with hashed passwords, and progress in
`progress_store.json`, both kept out of version control. The session secret is
read from the `FLASK_SECRET_KEY` environment variable, falling back to a local
`.flask_secret` file for development. Set `FLASK_SECRET_KEY` in production.

The exam timer is enforced on the server. The remaining time is shown each time
a page loads; since there is no JavaScript, it does not tick live between loads.

## Edit the question bank

Open `questions.json`. Each entry:

```
{ "b": "Weather", "s": "METAR", "q": "Question text",
  "c": ["A", "B", "C", "D"], "a": 1, "e": "The rule." }
```

`b` is the bucket (Regulations, Airspace, Charts, Weather, Operations, Loading),
`s` a subtopic, `c` the choices, `a` the index of the correct choice (0 to 3),
`e` the one-sentence rule. Restart the server to load changes.

## Deploy later

The `Procfile` runs the app under gunicorn (`web: gunicorn app:app`), which works
on hosts like Render.

## Roadmap

- Accounts. Progress is per-browser via a cookie today; a sign-in would replace
  that cookie id with a real user id for cross-device sync.
- Continued bank growth, all in `questions.json`.
