# Adaptive Interview Intelligence
**Hackathon Problem 3 — Full-Stack AI Interview Platform**

Adaptive Interview Intelligence is an evidence-grounded technical interview preparation and assessment platform built with **Python, Flask, PyMongo (MongoDB Atlas), Jinja2, Vanilla JavaScript, and Google Gemini API**.

---

## Security corrections in this version

- Public registration always creates a candidate account; submitted role values are ignored.
- Public one-click demo-login routes and automatic demo-account seeding have been removed.
- Logout uses POST with CSRF protection.
- Login redirects reject external and protocol-relative URLs.
- Inactive accounts are not loaded into authenticated sessions.
- Tests use an isolated `mongomock` database rather than a local or production MongoDB server.
- AI model failures do not create fake resume skills or fabricated answer scores. Unavailable evaluations are marked for human review.
- Resume replacement retains the previous file until the new profile reference has been saved.
- Interview identifiers and numeric form fields receive server-side validation.
- Adaptive follow-ups are inserted only when an evaluation is available and a valid model-generated follow-up is returned.

## Setup

1. Install Python 3.11 or newer (use a version supported by the listed dependencies).
2. Open a terminal in the project folder and create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and set a long random `SECRET_KEY`, your MongoDB Atlas `MONGO_URI`, and at least one AI provider key (`GEMINI_API_KEY` or `GROQ_API_KEY`). For automatic fallback, configure both. Keep `.env` private and never commit or upload it.
5. In MongoDB Atlas, allow network access only from the IPs you need and use a database user with limited permissions.
6. Start the application:

   ```bash
   python run.py
   ```

7. Visit `http://127.0.0.1:5000`, create a candidate account, and complete the candidate profile. Gemini-powered analysis requires a valid API key and supported model ID.

### Create a recruiter account securely

Recruiter accounts are not publicly self-registerable and are not automatically seeded. After configuring `.env`, run:

```bash
python scripts/create_recruiter.py
```

The script asks for the recruiter's name, email, and password interactively. Use a strong unique password. Run this only from a trusted development/admin environment.

### Run tests

```bash
pytest -q
```

Tests use an isolated in-memory MongoDB mock. AI-dependent tests are written to verify safe failure behavior when no API key is configured; they do not require real Gemini calls.

### Voice interview controls

The interview room supports browser-based voice interaction:

- **Read question aloud** uses the browser's Speech Synthesis API.
- **Answer by voice** uses the browser's Speech Recognition API when available, then places the transcript into the editable answer box.
- Candidates can stop recording, edit the transcript, or type the whole answer instead. Voice input is optional and does not change the scoring rubric.
- The current default speech locale is English (India). Browser and operating-system support varies; Chrome-based desktop browsers are the best starting point. Microphone access generally requires localhost or HTTPS.
- Browser speech recognition may process audio using the browser vendor's service. This implementation does not upload a raw audio recording to the Flask app, but candidates should be informed of the browser's speech-processing behavior and given the typed-answer alternative.

### Important limitations

- The integrity module records browser events as signals only; it cannot prove misconduct.
- GitHub evidence is limited to public API-accessible data and is not proof of authorship or skill mastery.
- This is a hackathon foundation, not a production hiring system. Before real candidate use, add formal privacy/retention controls, request rate limiting, security review, malware scanning for uploaded files, deployment monitoring, and a documented human-review process.

## Architecture & The 5-Module Pipeline

```
Candidate Evidence (PDF Resume + GitHub API)
                    │
                    ▼
   [Module 1: Profile & Adaptive Question Generation]
                    │
                    ▼
      [Module 2: Interview Room & 5-D Rubric Evaluation]
       ├── Server-Validated Timer
       └── 5 Dimensions: Correctness, Depth, Reasoning, Relevance, Clarity
                    │
                    ▼
     [Module 3: Transparent Integrity Telemetry]
       ├── Visibility & Window Blur Logging
       └── Neutral Server Timestamps (Never Auto-Accuses)
                    │
                    ▼
   [Module 4: Resume-to-Interview Skill Gap Mapping]
       └── Claimed vs Project Evidence vs Demonstrated ("Not assessed ≠ Failed")
                    │
                    ▼
   [Module 5: Explainable Report & Recruiter Decision Support]
       ├── Audit Trail & Personalized Learning Roadmap
       └── Human Recruiter Decision Recording with Attribution
```

---

## Project Structure

```
adaptive-interview-intelligence/
├── run.py                          # Flask application entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable configuration template
├── README.md                       # Documentation & setup guide
├── instance/
│   └── private_resumes/            # Private resume storage (outside static)
├── app/
│   ├── __init__.py                 # Flask application factory
│   ├── extensions.py               # Flask-Login, Bcrypt, CSRF, PyMongo
│   ├── models.py                   # User & MongoDB document models
│   ├── auth.py                     # Login, candidate-only registration, logout
│   ├── profile.py                  # Module 1: Resume PDF upload & GitHub analysis
│   ├── interview.py                # Module 2: Setup, live room, answer submission
│   ├── integrity.py                # Module 3: Transparent browser event telemetry
│   ├── reports.py                  # Module 5: Report detail and PDF export
│   ├── recruiter.py                # Protected Recruiter dashboard & decision recording
│   ├── routes/
│   │   └── main.py                 # Landing page & Authoritative Dashboard
│   ├── services/
│   │   ├── ai_service.py           # Google Gen AI SDK integration with validated outputs
│   │   ├── resume_service.py       # pypdf text extraction & private file handling
│   │   ├── github_service.py       # Official GitHub REST API evidence gathering
│   │   ├── question_service.py     # Question plan generator & persistence
│   │   ├── evaluation_service.py   # 5-dimension rubric scoring engine
│   │   ├── integrity_service.py    # Non-accusatory telemetry logging
│   │   ├── skill_gap_service.py    # Competency mapper (Claimed vs Demonstrated)
│   │   └── report_service.py       # Report compiler & ReportLab PDF generator
│   ├── templates/
│   │   ├── base.html               # Reusable master layout & navigation
│   │   ├── index.html              # Landing page explaining the 5 modules
│   │   ├── login.html              # Authentication sign-in
│   │   ├── register.html           # Candidate-only public registration
│   │   ├── dashboard.html          # Authoritative candidate dashboard & checklist
│   │   ├── profile.html            # Candidate profile, resume upload, GitHub stats
│   │   ├── interview_setup.html    # Role selection, time limit, questions count
│   │   ├── interview_room.html     # Live interview room with timer & auto-save
│   │   ├── interview_result.html   # Instant rubric feedback & competency status
│   │   ├── report_detail.html      # Comprehensive audit trail & recruiter decision panel
│   │   ├── recruiter_dashboard.html# Recruiter dashboard with candidate metrics
│   │   └── error.html              # Accessible 403, 404, 413, 500 error views
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css           # Clean SaaS stylesheet (zero-pill discipline)
│   │   └── js/
│   │       ├── main.js             # Flash alerts auto-dismissal
│   │       └── interview.js        # Timer, localStorage draft save, integrity logs
│   └── utils/
│       ├── security.py             # Role decorators & secure filename generation
│       └── validators.py           # GitHub URL validation & PDF magic byte checks
└── tests/
    ├── test_auth.py                # Registration, login, and duplicate prevention
    ├── test_profile.py             # URL validation & completion calculation
    ├── test_interview.py           # Question plan sequencing & time limits
    └── test_evaluation.py          # Rubric dimensions & empty answer handling
```

---

## Local Setup Instructions (macOS & VS Code)

Follow the Setup section near the beginning of this README. In short:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your own secret, MongoDB Atlas URI, and Gemini API key.
python run.py
```

Open `http://127.0.0.1:5000`. The application intentionally does not seed demo accounts or expose one-click login routes. Create a candidate account through the registration page. Create recruiter accounts only from a trusted terminal using `python scripts/create_recruiter.py`.

## Running the Automated Test Suite

```bash
pytest -q
```

The test configuration uses `mongomock` and does not connect to the configured Atlas cluster. Tests that need a real Gemini response should be implemented as separately marked integration tests and must not run automatically in the default unit-test suite.

---

## Key Principles & Design Decisions

1. **Not Assessed is NOT a Failure**: Skills listed on a candidate's resume that were not asked about during an interview are transparently marked as *"Not yet assessed"* or *"Claimed"*, never as a negative score.
2. **Browser Signals are NOT Proof of Cheating**: Tab switches or focus losses are recorded neutrally as *"visibility change recorded"* with server timestamps for human recruiter context. The system never terminates an interview automatically or makes accusations.
3. **Concise Answers Rewarded**: The 5-dimension rubric rewards precision, architectural insight, and trade-off understanding. It does not penalize non-native writing styles or reward filler text.
4. **Human Decision Control**: AI outputs are strictly structured decision support. Final decisions (*Further interview recommended*, *Additional evidence required*, etc.) are recorded by human recruiters with clear attribution and notes.


## AI provider setup and retrying failed evaluations

The app supports Gemini and Groq. Set `AI_PROVIDER=auto` to try Gemini first and Groq second, or set `AI_PROVIDER=groq` / `AI_PROVIDER=gemini` to choose a preferred provider. Configure one or both API keys in `.env`, then restart Flask. Models are configurable with `GEMINI_MODEL` and `GROQ_MODEL`.

If a report already contains unavailable evaluations, open that report and click **Retry Unavailable Evaluations** after configuring the provider. The app retries saved answers without requiring a new interview and rebuilds the cached report. The report distinguishes completed evaluations from submitted answers and labels the overall score provisional when one or more evaluations still need retry or human review. Provider errors are logged in sanitized form to the Flask terminal; never share your API keys or full `.env` file.

### Recommended macOS workflow

Use Python 3.11 or 3.12 if your installed scientific/AI packages have issues on a newer Python release. From Terminal, run the setup commands in order. If tests fail with `ModuleNotFoundError`, activate the project's `.venv` first and run `python -m pip install -r requirements.txt`; then use `python -m pytest -q` so the test runner uses the same interpreter.

## Update note — question/competency alignment

The ready-to-test build includes a guard for AI-generated question labels and a revised deterministic fallback plan. When AI question generation is unavailable, each fallback question explicitly names the competency shown beside it, uses hypothetical role-based wording, and avoids unsupported claims about internships or personal implementation history. A regression test covers this behavior.

The automated test suite requires the dependencies in `requirements.txt` and a test MongoDB configuration. If those dependencies are not installed, `pytest` cannot collect the tests; run `./setup_mac.sh` in a virtual environment before testing.
