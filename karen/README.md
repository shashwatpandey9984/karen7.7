# KAREN

KAREN is a small Flask application with a plain JavaScript chat interface. Its existing features include browser speech, Wikipedia lookup, news lookup, OpenCV face detection, and a face-presence alarm.

## Architecture and model

- `app.py` serves the UI and exposes Flask API routes.
- `news_service.py` fetches public RSS feeds and filters dated International and National · India headlines.
- `index.html`, `style.css`, `index.js`, and `config.js` implement the browser interface and assistant behavior.
- `code_debugger/` provides source-language detection, Python static analysis, analyzer adapters, security reporting, AI-provider status, correction proposals, diffs, and the safe test-execution gate.
- `models` is an unused face-detector weights manifest; the active face detector is OpenCV's bundled Haar cascade.
- No coding LLM, AI API client, model configuration, or AI API key exists in this project. The debugger does not transmit submitted code to a third party and does not invent provider credentials.

## File inventory

Added:

- `config.js`: default static-host API configuration.
- `render.yaml`: Render blueprint for running the Flask app and serving its frontend.
- `.gitignore`: excludes Python caches, local environments, and local configuration files.
- `.python-version`: selects Python 3.12 on hosts that support this version file.
- `code_debugger/__init__.py`: shared analysis input limit.
- `code_debugger/languages.py`: filename, hint, and source-based language detection.
- `code_debugger/analysis.py`: Python AST, compile, undefined-name, quality, and dynamic-execution checks.
- `code_debugger/tooling.py`: bounded Ruff, Pylint, MyPy, and Bandit adapters.
- `code_debugger/security.py`: security finding report.
- `code_debugger/ai_review.py`: explicit model-availability status.
- `code_debugger/correction.py`: bounded syntax-only proposal generator.
- `code_debugger/comparison.py`: unified diff generation.
- `code_debugger/testing.py`: safe disabled-execution status.
- `code_debugger/api.py`: language analysis, proposal, and test-status endpoints.
- `tests/test_code_debugger.py`: safe debugger regression fixtures.
- `tests/test_news_service.py` and `tests/test_news_api.py`: RSS and API regression fixtures.
- `requirements-debugger.txt`: optional static-analysis and test dependencies.

Modified:

- `app.py`: registers debugger and news routes and caps HTTP request bodies.
- `requirements.txt`: includes the RSS HTTP client and production WSGI server.
- `index.html`, `style.css`, and `index.js`: add the code workbench, approval-gated fixes, and highlighted current-affairs cards.
- `README.md`: installation, architecture, safety limits, usage, test results, and this file inventory.

## Deployment

GitHub Pages serves static files only; it cannot run the Flask APIs used by the code debugger, news lookup, face detection, and face-presence alarm. The assets use relative URLs so the page and CSS still load from a GitHub Pages project URL such as `https://USERNAME.github.io/REPOSITORY/`, but those API features need a running Flask backend.

The simplest full deployment is to push this repository to GitHub, then in Render choose **New → Blueprint**, select the repository, and deploy the `render.yaml` blueprint from the repository root. The blueprint installs the dependencies, starts Gunicorn bound to Render's assigned port, and serves the frontend and API on the same HTTPS origin. Open the resulting `https://...onrender.com` address (not the GitHub Pages or local file URL). Camera access then works in supported browsers after the user grants permission.

The blueprint uses Render's free web-service plan. Free services can sleep when idle and take a short time to wake on the next visit. After the first deployment, check the Render deploy logs if the service does not become healthy.

To keep the frontend on GitHub Pages, deploy the Flask backend separately, then edit `config.js` in the Pages branch:

```js
window.KAREN_API_BASE_URL = "https://YOUR-FLASK-SERVICE.onrender.com";
window.KAREN_API_ENABLED = true;
```

Use the backend's HTTPS origin only (no `/api` suffix). Flask enables CORS for the separate frontend origin. The camera requires HTTPS (or localhost during development). If the backend is not configured, the camera preview can still open, and face detection reports the setup requirement once instead of repeatedly showing a fetch error.

## Install

Use the same Python environment that runs the app:

```powershell
python -m pip install -r requirements.txt -r requirements-debugger.txt
```

The debugger tool list is `ruff`, `pylint`, `pytest`, `mypy`, and `bandit`. To install only these tools:

```powershell
python -m pip install -r requirements-debugger.txt
```

## Run

```powershell
python app.py
```

Open `http://127.0.0.1:5000`. The Code Debugger panel accepts a filename and source text. Analyze Code and Find Errors show static findings; Explain Errors shows their plain-language descriptions. Generate Fixed Code can currently propose only a missing Python block colon when the revised source parses. Compare Original and Fixed Code displays a unified diff. Analyze Again reruns static checks.

For news, use `news <topic>` or ask naturally, for example: `30 October 2026 current affairs international and national India`. Omitting the date requests today's date in India. Results are grouped into International and National · India, with linked headlines, publisher, and publication time. The server reads public BBC and The Hindu RSS feeds; no NewsAPI key is required. RSS providers retain only recent items, so a date outside their feed history may return no stories. If all feeds are unreachable, the app reports a feed/network error rather than inventing headlines.

Applying a proposal requires explicit confirmation. Before changing the editor text, the UI stores the original in session storage and downloads a `.bak` copy. It does not write or overwrite files on disk.

## Analysis and safety

- Supported deeper analysis: Python AST parsing, Python compilation checks, scope-aware undefined-name checks, and optional Ruff, Pylint, MyPy, and Bandit static diagnostics.
- Other recognized languages are identified, but currently receive an unsupported-analyzer notice.
- Source is treated as untrusted text, limited to 100,000 characters, and never passed to `eval`, `exec`, a shell, or an application runtime. External analyzers receive a temporary `.py` file, run without a shell, and have a 15-second timeout. Timed-out analyzers are marked unavailable while built-in findings are still returned.
- Run Tests does not execute submitted code. The app has no OS-level sandbox that can restrict filesystem access, network access, CPU, and memory; the endpoint explains this and returns HTTP 409. Project-owned analyzer tests use harmless fixed fixtures.
- Static checks cannot prove intended behavior or catch every logical/runtime bug. Those require a specification and trusted tests in a properly isolated runner.
- Automatic correction is intentionally narrow. No coding AI is available, so behavioral repairs and AI explanations are not generated. No source file is modified automatically.

## Tests

Run all fixed fixture tests:

```powershell
python -m pytest -q tests
```

The fixtures cover debugger analysis and safety, plus RSS parsing, date filtering, category selection, topic filtering, invalid dates, feed failures, and the news API contract.

## Verification

Run the project fixtures with `python -m pytest -q tests`. These cover debugger safety and analysis, RSS behavior, API responses, and the frontend asset/config routes.