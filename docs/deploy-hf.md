# Deploy the public demo to a Hugging Face Space

Result: `https://solomonsmith-dev-soc-triage-ai.hf.space` serves the Streamlit UI at `/` and `POST /triage` returning the case envelope from `packages/contracts`.

The Space runs in cached mode by default. Stage 4, the model call, is answered from the cassettes the 100-case harness recorded, so the Space needs no Anthropic key, makes no model calls and costs nothing. Observable extraction, retrieval, the refusal guardrail, schema validation and case packaging run live on every request. An alert that reaches stage 4 with no matching recording gets `404 not_recorded`. Live mode calls Claude with your key and is opt in (step 6).

How it works: the Space repo holds two files (`Dockerfile`, `README.md`). The Dockerfile downloads this repo at a pinned commit, installs CPU-only torch, bakes the embedding model into the image, copies the harness cassettes and cases, and starts uvicorn, Streamlit and nginx behind port 7860. At startup the API runs every harness case through the engine and checks which recordings reproduce on that machine. `GET /samples` lists only those, and `/healthz` reports the counts. CI builds the same Dockerfile from the checkout and smoke-tests both modes (job `demo-image`).

Deploying needs a Hugging Face write token. It does not belong in any file in a repo.

Use `/usr/bin/grep` and `/bin/ls` as written. Work under `~/Projects`, not Desktop or Downloads.

## 0. Check main

1. The commit you deploy must be on `main` and include cached mode. Done check, the first line must print a 40-character hash and the `ls-tree` line must print two entries:
   ```bash
   git -C ~/Projects/soc-triage-ai fetch origin && git -C ~/Projects/soc-triage-ai rev-parse origin/main
   git -C ~/Projects/soc-triage-ai ls-tree origin/main deploy/hf-space/Dockerfile apps/demo/soc_demo/replay.py
   ```
2. CI must be green on that commit, in particular `demo-image` and `harness-replay`.
3. The repo must be public, because the Space build downloads it anonymously. Done check (prints `200`):
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://codeload.github.com/SolomonSmith-dev/soc-triage-ai/tar.gz/main
   ```

## 1. Create the Space

1. huggingface.co/new-space. Owner `SolomonSmith-dev`, name `soc-triage-ai`, SDK **Docker**, template **Blank**, hardware **CPU basic (free)**, visibility **Public**. Create.
2. No secret is needed in cached mode. Optional variables, shown with their defaults: `DEMO_RATE_PER_MINUTE=5`, `DEMO_RATE_PER_DAY=20`, `DEMO_MAX_ALERT_CHARS=3000`.
3. Done check: `https://huggingface.co/spaces/SolomonSmith-dev/soc-triage-ai` loads and shows an empty Space.

## 2. Push the two files

Both files are taken from the pinned commit, not your working tree, so a stale local checkout cannot ship an older Dockerfile:

```bash
cd ~/Projects
git clone https://huggingface.co/spaces/SolomonSmith-dev/soc-triage-ai hf-soc-triage-ai
cd hf-soc-triage-ai
SHA=$(git -C ~/Projects/soc-triage-ai rev-parse origin/main)
git -C ~/Projects/soc-triage-ai show "$SHA:deploy/hf-space/Dockerfile" | sed "s/^ARG REPO_REF=main/ARG REPO_REF=$SHA/" > Dockerfile
git -C ~/Projects/soc-triage-ai show "$SHA:deploy/hf-space/README.md" > README.md
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

## 3. Wait for the build

1. Space page, the status badge reads **Building**, then **Running**. Expect 8 to 15 minutes the first time (torch and the model download).
2. Done check: badge says **Running** and the app loads at the Space URL. If it says **Build error**, open the Logs tab, Build, and read the last 30 lines.

## 4. Verify the endpoints

```bash
U=https://solomonsmith-dev-soc-triage-ai.hf.space
curl -s $U/healthz; echo
curl -s -o /dev/null -w '%{http_code}\n' $U/
```

Done check:
- `healthz` prints `{"status":"ok","demo_mode":true,"mode":"cached","recordings":{"replay":92,"refusal":7,"unservable":1}}`. While the engine loads it prints `"recordings":"loading"`; wait a minute. `replay` must equal the number of files in `tests/harness/cassettes`. The one `unservable` case is INJ-009, which has no cassette (see the model card). If it prints `"status":"error"` and `"recordings":"failed"`, the engine did not load: Logs, Container, find `event=engine_load_failed` for the error type. It retries every minute.
- `/` prints `200`.

A recorded alert replays the model step. Fetch it from `/samples` so the text matches byte for byte:

```bash
curl -s $U/samples | python3 -c 'import json,sys; s={x["id"]:x for x in json.load(sys.stdin)}; json.dump({"alert": s["T4_brute_force_ssh"]["alert"]}, open("t4.json","w"))'
curl -s -D - -o t4-out.json -X POST $U/triage -H 'content-type: application/json' --data @t4.json | /usr/bin/grep -iE '^HTTP|^x-demo'
python3 -c 'import json; c=json.load(open("t4-out.json")); print(c["case_id"], c["triage"]["severity"], c["guardrail_triggered"])'
```

Done check: status `200`, `x-demo-mode: cached`, `x-demo-replay-case: T4_brute_force_ssh`, and a line like `SOC-20261117-1a2b high False`.

An out-of-corpus alert is refused at stage 3, before any model call:

```bash
curl -s -X POST $U/triage -H 'content-type: application/json' \
  -d '{"alert":"Sear the short ribs for 4 minutes per side, then deglaze with red wine and braise at 300F for three hours."}' \
  | python3 -c 'import json,sys; c=json.load(sys.stdin); print(c["guardrail_triggered"], c["uncertainty_mode"], len(c["evidence"]["chunks_retrieved"]))'
```

Done check: `True out_of_scope 0`.

An in-corpus alert with no recording is not answered:

```bash
curl -s -X POST $U/triage -H 'content-type: application/json' \
  -d '{"alert":"40 failed SSH logins against srv-bastion-07, then one success and a new sudoers entry"}'
```

Done check: the body has `"status":"not_recorded"` and a `retrieval` list of the chunks that matched.

## 5. Verify the guards

1. Per-IP limit: wait a minute after step 4, then send the recorded alert six times:
   ```bash
   sleep 60; for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w '%{http_code}\n' -X POST $U/triage -H 'content-type: application/json' --data @t4.json; done
   ```
   Done check: five `200` lines, then `429`.
2. No alert text in logs: POST an alert containing the word `zebracanary`, then open Space, Logs, Container, and use the browser's find for `zebracanary`. Done check: 0 matches.

## 6. Live mode (optional, costs money)

Only if visitors should be able to triage any alert. The Space then calls Claude for every request that passes the guards.

1. console.anthropic.com, Settings, API keys, Create key, name it `soc-triage-demo`. Settings, Limits: set a monthly spend limit (suggest 5 USD). This is the backstop behind the app's own daily token cap. Copy the key once and do not paste it into any file in a repo.
2. Space, Settings, Variables and secrets. New secret `ANTHROPIC_API_KEY` with the key. New variable `DEMO_MODE=live`. Optional variables with their defaults: `DEMO_DAILY_TOKEN_CAP=200000`, `DEMO_RATE_PER_MINUTE=5`, `DEMO_RATE_PER_DAY=20`.
3. Done check: `healthz` prints `"mode":"live"` and `budget` prints `tokens_remaining` close to 200000. A `503` with `not_configured` means the secret is missing or misnamed.
4. Cap check: set `DEMO_DAILY_TOKEN_CAP=0`, wait for **Running**, POST any alert. Done check: status `429` and `demo_budget_reached` in the body. Then set it back.

To return to cached mode, delete the `DEMO_MODE` variable and the secret.

## 7. Record a fresh harness run (optional, about 0.60 USD)

Needed after any change to the prompt, corpus or retrieval, because those change the prompt hash and every cassette goes stale. Uses your key, about 100 calls, capped at 5 USD by the CLI:

```bash
cd ~/Projects/soc-triage-ai
export ANTHROPIC_API_KEY=...   # from your shell only, never a file
python -m tests.harness.test_harness --record --update-baseline
python -m tests.harness.report
```

Done check: the run ends with `wrote .../baseline.json` and prints a live spend line under 5 USD. Commit the cassettes, merge, and redeploy so the Space replays the new recordings.

## 8. Link the demo from the README

Only after steps 4 and 5 pass. In `README.md`, replace the `**Public demo:**` paragraph with a link to the Space URL, open a PR and merge it once CI is green. The Space does not rebuild for a README change. Done check: `/usr/bin/grep -c 'solomonsmith-dev-soc-triage-ai.hf.space' README.md` prints `1` or more on `main`.

## Operating notes

- Redeploy: repeat step 2 with the new `main` hash, which also picks up any change to the Dockerfile or the Space README, then commit and push. The Space rebuilds from that commit.
- Free Spaces sleep after about 48 hours without traffic. The first visit wakes the container in roughly a minute, then the startup recording check takes a few seconds more.
- Cached mode matches recordings on the exact prompt, which includes the exact alert text. An edited alert still gets live extraction, retrieval and the refusal guardrail; if retrieval finds context, the answer is `404 not_recorded` instead of a triage.
- If cassettes go stale, CI fails on `harness-replay`, and a Space built from that commit shows `replay` below the cassette count in `/healthz`.
- Live mode only: the daily token counter is a file in `/tmp`. It survives process restarts but not a container rebuild, so a rebuild refills the day's cap. The Anthropic monthly limit is the hard stop. The cap check runs before the model call and usage is added after it, so simultaneous requests can exceed the cap by a few requests' worth of tokens.
- Behind the Space proxy the client address is the right-most `X-Forwarded-For` entry (`DEMO_TRUSTED_PROXY_HOPS=1`). If you move hosts, set that to the number of proxies in front of the app, or per-IP limiting will key on the wrong address.
