# Deploy the public demo to a Hugging Face Space

Result: `https://solomonsmith-dev-soc-triage-ai.hf.space` serves the demo page at `/` and `POST /triage` returning the case envelope from `packages/contracts`.

The Space runs in cached mode by default. Stage 4, the model call, is answered from the cassettes the 100-case harness recorded, so the Space needs no Anthropic key, makes no model calls and costs nothing. Observable extraction, retrieval, the refusal guardrail, schema validation and case packaging run live on every request. An alert that reaches stage 4 with no matching recording gets `404 not_recorded`. Live mode calls Claude with your key and is opt in (step 6).

Hosting: Hugging Face requires a paid plan (PRO, 9 USD a month) to create Docker or Gradio Spaces on its free CPU hardware. A free account in good standing (verified email, account older than 30 days) can host up to 2 Gradio Spaces on ZeroGPU hardware ([Spaces overview](https://huggingface.co/docs/hub/spaces-overview), [ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)). This runbook deploys that free variant. The app never requests a GPU: the embedding model runs on the CPU. The Docker variant is at the end, for an account with a paid plan.

How it works: the Space repo holds `app.py`, `README.md`, `requirements.txt`, and the harness cassettes and cases under `tests/harness/`. `deploy/hf-space-zerogpu/bundle.py` writes all of them from one commit and pins `requirements.txt` to it, so the Space installs this repo's packages from GitHub at that commit. `app.py` starts `soc_demo.space`: the demo API with a Gradio page mounted at `/`. The page calls the API in process, so the page and direct API calls pass the same guards. At startup the API runs every harness case through the engine and checks which recordings reproduce on that machine. `GET /samples` lists only those, and `/healthz` reports the counts. CI bundles the Space from the checkout and smoke-tests it with ZeroGPU's CUDA emulation on (job `space-app`).

Deploying needs a Hugging Face write token. It does not belong in any file in a repo.

Use `/usr/bin/grep` and `/bin/ls` as written. Work under `~/Projects`, not Desktop or Downloads.

## 0. Check main

1. The commit you deploy must be on `main` and include the ZeroGPU Space. Done check, the first line must print a 40-character hash and the `ls-tree` line must print two entries:
   ```bash
   git -C ~/Projects/soc-triage-ai fetch origin && git -C ~/Projects/soc-triage-ai rev-parse origin/main
   git -C ~/Projects/soc-triage-ai ls-tree origin/main deploy/hf-space-zerogpu/bundle.py apps/demo/soc_demo/space.py
   ```
2. CI must be green on that commit, in particular `space-app` and `harness-replay`.
3. The repo must be public, because the Space build downloads it anonymously. Done check (prints `200`):
   ```bash
   curl -sL -o /dev/null -w '%{http_code}\n' https://github.com/SolomonSmith-dev/soc-triage-ai/archive/main.tar.gz
   ```

## 1. Create the Space

1. huggingface.co/new-space. Owner `SolomonSmith-dev`, name `soc-triage-ai`, SDK **Gradio**, template **Blank**, hardware **ZeroGPU**, visibility **Public**. Create.
2. No secret is needed in cached mode. Optional variables, shown with their defaults: `DEMO_RATE_PER_MINUTE=5`, `DEMO_RATE_PER_DAY=20`, `DEMO_MAX_ALERT_CHARS=3000`.
3. Done check: `https://huggingface.co/spaces/SolomonSmith-dev/soc-triage-ai` loads and shows an empty Space with ZeroGPU hardware. If the form asks for a paid plan, the account does not qualify for free ZeroGPU hosting yet.

## 2. Push the Space files

Every file comes from the pinned commit, not your working tree:

```bash
cd ~/Projects
git clone https://huggingface.co/spaces/SolomonSmith-dev/soc-triage-ai hf-soc-triage-ai
cd hf-soc-triage-ai
SHA=$(git -C ~/Projects/soc-triage-ai rev-parse origin/main)
python3 ~/Projects/soc-triage-ai/deploy/hf-space-zerogpu/bundle.py "$SHA" .
/usr/bin/grep -c "$SHA" requirements.txt
/bin/ls
```

Git asks for credentials: username `SolomonSmith-dev`, password a write-scoped token from huggingface.co/settings/tokens.

Done check: `bundle.py` ends with `92 cassettes, 100 cases`, the `grep` prints `3`, and `ls` shows `README.md  app.py  requirements.txt  tests`.

```bash
git add -A
git commit -m "Deploy SOC Triage AI demo at ${SHA:0:7}"
git push
```

## 3. Wait for the build

1. Space page, the status badge reads **Building**, then **Running**. Expect 5 to 15 minutes the first time (torch and the packages install).
2. Done check: badge says **Running** and the page loads at the Space URL. If it says **Build error** or **Runtime error**, open the Logs tab (Build or Container) and read the last 30 lines.

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

The page: open the Space URL, click **SSH brute force (Tor exit)**, then **Run triage**. Done check: a table with `HIGH` and `Yes`, and a line that starts `Model step replayed from the harness recording of case T4_brute_force_ssh`.

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

## Alternative: Docker Space (needs a paid plan)

`deploy/hf-space/` holds a Docker variant: one image with uvicorn, the Streamlit page and nginx on port 7860, CPU-only torch, and the embedding model baked in. CI builds it and smoke-tests both modes (job `demo-image`). Hugging Face creates Docker Spaces only for accounts with a paid plan; without one, creating the Space returns `402 Payment Required`. With a plan, follow steps 0 to 8 with these changes:

- Step 1: SDK **Docker**, template **Blank**, hardware **CPU basic**.
- Step 2: the Space repo holds two files, both taken from the pinned commit:
  ```bash
  git -C ~/Projects/soc-triage-ai show "$SHA:deploy/hf-space/Dockerfile" | sed "s/^ARG REPO_REF=main/ARG REPO_REF=$SHA/" > Dockerfile
  git -C ~/Projects/soc-triage-ai show "$SHA:deploy/hf-space/README.md" > README.md
  /usr/bin/grep -n '^ARG REPO_REF' Dockerfile
  ```
  Done check: the `grep` prints a 40-character hash on the `ARG REPO_REF=` line. Then `git add Dockerfile README.md`, commit and push.

## Operating notes

- Redeploy: repeat step 2 with the new `main` hash, then `git add -A`, commit and push. `bundle.py` replaces the two data directories, so `git add -A` also removes recordings the repo dropped. The Space rebuilds from that commit.
- Spaces on free hardware sleep after a period without traffic. The first visit wakes the Space, then the startup recording check takes a few seconds more.
- ZeroGPU emulates CUDA outside GPU tasks, which would move the embedding model to an emulated `cuda` device. `app.py` sets `SOC_EMBED_DEVICE=cpu` so it stays on the CPU, where the cassettes were checked. `tests/unit/test_space_app.py` fails if `app.py` stops setting it before anything loads torch.
- Cached mode matches recordings on the exact prompt, which includes the exact alert text. An edited alert still gets live extraction, retrieval and the refusal guardrail; if retrieval finds context, the answer is `404 not_recorded` instead of a triage. The page maps an alert that differs from a recorded one only in leading or trailing whitespace back to the recording.
- If cassettes go stale, CI fails on `harness-replay`, and a Space built from that commit shows `replay` below the cassette count in `/healthz`.
- Live mode only: the daily token counter is a file in `/tmp`. It survives process restarts but not a rebuild, so a rebuild refills the day's cap. The Anthropic monthly limit is the hard stop. The cap check runs before the model call and usage is added after it, so simultaneous requests can exceed the cap by a few requests' worth of tokens.
- Behind the Space proxy the client address is the right-most `X-Forwarded-For` entry (`DEMO_TRUSTED_PROXY_HOPS=1`). The page forwards the visitor's header unchanged on its in-process call. If you move hosts, set that to the number of proxies in front of the app, or per-IP limiting will key on the wrong address.
