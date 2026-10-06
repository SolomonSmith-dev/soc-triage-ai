# Deploy the public demo to a Hugging Face Space

Result: `https://solomonsmith-dev-soc-triage-ai.hf.space` serves the Streamlit UI at `/` and `POST /triage` returning the case envelope from `packages/contracts`.

Why this is a runbook and not done for you: deploying needs your Anthropic key as a Space secret and a Hugging Face write token. Neither belongs in an unattended session.

How it works: the Space repo holds two files (`Dockerfile`, `README.md`). The Dockerfile downloads this repo at a pinned commit, installs CPU-only torch, bakes the embedding model into the image, and starts uvicorn, Streamlit and nginx behind port 7860. CI builds the same Dockerfile from the checkout and smoke-tests it (job `demo-image`).

Use `/usr/bin/grep`, `/bin/ls`, `/bin/cp -f` as written. Work under `~/Projects`, not Desktop or Downloads.

## 0. Merge the PRs in order

1. Merge the scope PR, then the harness PR, then the deploy PR into `main` (each one is stacked on the previous).
2. Done check, must print a 40-character hash and the file must exist:
   ```bash
   git -C ~/Projects/soc-triage-ai fetch origin && git -C ~/Projects/soc-triage-ai rev-parse origin/main
   git -C ~/Projects/soc-triage-ai ls-tree origin/main deploy/hf-space/Dockerfile
   ```
   The `ls-tree` line must print one entry. If it prints nothing, the deploy PR is not merged yet.
3. The repo must be public, because the Space build downloads it anonymously. Done check (prints `200`):
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://codeload.github.com/SolomonSmith-dev/soc-triage-ai/tar.gz/main
   ```

## 1. Create a dedicated, capped Anthropic key

1. console.anthropic.com, Settings, API keys, Create key, name it `soc-triage-demo`.
2. Settings, Limits: set a monthly spend limit (suggest 5 USD). This is the backstop behind the app's own daily token cap.
3. Copy the key once. Do not paste it into any file in a repo.
4. Done check: the key is listed as `soc-triage-demo` and the limit shows on the Limits page.

## 2. Create the Space

1. huggingface.co/new-space. Owner `SolomonSmith-dev`, name `soc-triage-ai`, SDK **Docker**, template **Blank**, hardware **CPU basic (free)**, visibility **Public**. Create.
2. Done check: `https://huggingface.co/spaces/SolomonSmith-dev/soc-triage-ai` loads and shows an empty Space.

## 3. Add the secret and limits

1. Space, Settings, Variables and secrets.
2. New secret: name `ANTHROPIC_API_KEY`, value the key from step 1.
3. New variables (optional, these are the defaults): `DEMO_DAILY_TOKEN_CAP=200000`, `DEMO_RATE_PER_MINUTE=5`, `DEMO_RATE_PER_DAY=20`, `DEMO_MAX_ALERT_CHARS=3000`.
4. Done check: `ANTHROPIC_API_KEY` is listed under Secrets with its value hidden.

## 4. Push the two files

```bash
cd ~/Projects
git clone https://huggingface.co/spaces/SolomonSmith-dev/soc-triage-ai hf-soc-triage-ai
cd hf-soc-triage-ai
/bin/cp -f ~/Projects/soc-triage-ai/deploy/hf-space/Dockerfile .
/bin/cp -f ~/Projects/soc-triage-ai/deploy/hf-space/README.md .
SHA=$(git -C ~/Projects/soc-triage-ai rev-parse origin/main)
sed -i '' "s/^ARG REPO_REF=main/ARG REPO_REF=$SHA/" Dockerfile
/usr/bin/grep -n '^ARG REPO_REF' Dockerfile
/bin/ls
```

Git asks for credentials: username `SolomonSmith-dev`, password a write-scoped token from huggingface.co/settings/tokens.

Done check: the `grep` prints a line with a 40-character hash on the first `ARG REPO_REF=` line, and `ls` shows `Dockerfile  README.md`. If the hash is missing, the `sed` did not match: fix before pushing.

```bash
git add Dockerfile README.md
git commit -m "Deploy SOC Triage AI demo"
git push
```

## 5. Wait for the build

1. Space page, the status badge reads **Building**, then **Running**. Expect 8 to 15 minutes the first time (torch and the model download).
2. Done check: badge says **Running** and the app loads at the Space URL. If it says **Build error**, open the Logs tab, Build, and read the last 30 lines.

## 6. Verify the endpoint

```bash
U=https://solomonsmith-dev-soc-triage-ai.hf.space
curl -s $U/healthz
curl -s $U/budget
curl -s -X POST $U/triage -H 'content-type: application/json' \
  -d '{"alert":"5000 failed SSH authentication attempts in 10 minutes against srv-bastion-01 from 185.220.101.45. No successful logins."}' \
  | python3 -m json.tool | /usr/bin/grep -E '"case_id"|"severity"|"guardrail_triggered"'
```

Done check, all must hold:
- `healthz` prints `{"status":"ok","demo_mode":true}`.
- `budget` prints a JSON object with `tokens_remaining` close to 200000.
- The triage call prints a `case_id` starting `SOC-`, a `severity`, and `"guardrail_triggered": false`. A `503` with `not_configured` means the secret is missing or misnamed (step 3).

## 7. Verify the guards

1. Refusal when the cap is hit: Space, Settings, set `DEMO_DAILY_TOKEN_CAP=0`, wait for **Running**, then:
   ```bash
   curl -s -i -X POST $U/triage -H 'content-type: application/json' -d '{"alert":"test alert text"}' | /usr/bin/grep -E 'HTTP|demo_budget_reached'
   ```
   Done check: status line `429` and the body contains `demo_budget_reached`. Then set the variable back to `200000`.
2. Per-IP limit: run the triage call from step 6 six times in a row. Done check: the sixth prints `rate_limited`.
3. No alert text in logs: POST an alert containing the word `zebracanary`, then open Space, Logs, Container, and use the browser's find for `zebracanary`. Done check: 0 matches.

## 8. Wire the link and record the numbers

1. In `README.md` replace `DEMO_URL_PLACEHOLDER` with the Space URL. Check: `/usr/bin/grep -c DEMO_URL_PLACEHOLDER README.md` prints `0`.
2. Record the live harness run locally (uses your key, about 100 calls, capped at 5 USD by the CLI):
   ```bash
   cd ~/Projects/soc-triage-ai
   export ANTHROPIC_API_KEY=...   # from your shell only, never a file
   python -m tests.harness.test_harness --record --update-baseline
   python -m tests.harness.report
   ```
   Done check: the run ends with `wrote .../baseline.json` and prints a live spend line under 5 USD; `tests/harness/RESULTS.md` now has a "Live run" table.

## Operating notes

- Free Spaces sleep after about 48 hours without traffic. The first visit wakes the container in roughly a minute.
- The daily token counter is a file in `/tmp`. It survives process restarts but not a container rebuild, so a rebuild refills the day's cap. The Anthropic monthly limit from step 1 is the hard stop.
- Cap overshoot: the check runs before the model call and usage is added after it, so simultaneous requests can exceed the cap by a few requests' worth of tokens.
- Behind the Space proxy the client address is the right-most `X-Forwarded-For` entry (`DEMO_TRUSTED_PROXY_HOPS=1`). If you move hosts, set that to the number of proxies in front of the app, or per-IP limiting will key on the wrong address.
