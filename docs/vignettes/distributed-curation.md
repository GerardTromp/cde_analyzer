# Vignette: Distributed Curation

A guide to multi-curator pattern curation — distributing TSV files to
independent reviewers, collecting annotations, computing inter-rater
agreement, and resolving disagreements.

## What This Vignette Covers

Human curation is a critical step in both the instrument and phrase
pipelines. When multiple curators review the same pattern set independently,
inter-rater agreement statistics quantify reliability and highlight patterns
that need discussion.

This vignette covers two approaches:

**File-based** (§1–7): Distribute standalone editor + TSV files via email.

- Building the standalone editor for distribution
- Initializing and distributing per-curator files
- Collecting and merging annotations
- Interpreting agreement statistics
- Resolving disagreements in a joint session

**Centralized server** (§9–13): Host an HTTPS server — curators open a URL.

- Writing a server config (curators, TLS, timespan)
- Starting and monitoring the centralized server
- Security model (HMAC tokens, rate limiting, TLS)
- Merging results after submission

**Prerequisites**: Enriched patterns from Phase 1 or Phase 2
(`coalesced_fields.tsv`). Familiarity with the
[Curation Guide](../curation-guide.md) decision framework.

**Related documentation**:

- [Curation Guide](../curation-guide.md) — decision guidelines, checklist, and pitfalls
- [TSV Editor Quickstart](../tsv-editor-cheatsheet.md) — keyboard shortcuts and editor workflow
- [pattern_util reference](../help/pattern_util.md) — init-curation, merge-curation, editor commands
- [Quickstart](quickstart.md) — end-to-end pipeline walkthrough

---

## 1. Build the Standalone Editor

The TSV editor runs as a self-contained `.pyz` archive. Curators need
only Python 3.8+ — no pip packages, no `cde-analyzer` installation.

```bash
python scripts/build_editor_zipapp.py
# → dist/cde_editor.pyz (~59 KB)
```

Test it:

```bash
python dist/cde_editor.pyz --version
# cde_editor 0.7.0
```

The build script bundles `tsv_editor.html` (the browser-based editor) and
a minimal HTTP server into a single archive.

---

## 2. Initialize Per-Curator Files

Use `--init-curation` to create one annotated copy per curator:

```bash
cde-analyzer pattern_util --init-curation phase1_output/coalesced_fields.tsv \
    --curators "alice,bob,carol" \
    -o curation_round/
```

This creates:

```
curation_round/
  coalesced_fields.alice.tsv
  coalesced_fields.bob.tsv
  coalesced_fields.carol.tsv
```

Each file contains all original columns plus four curation columns:

| Column | Curator fills | Example |
|--------|---------------|---------|
| `decision` | Required: `strip`, `skip`, or `modify` | `strip` |
| `modification` | Optional: replacement text (when decision = modify) | `PHQ-9 Total` |
| `notes` | Optional: commentary | `Only in designations` |
| `curator` | Pre-filled with curator name | `alice` |

---

## 3. Distribute and Curate

Send each curator their file plus the standalone editor:

```
To: alice@example.com
Attachments: cde_editor.pyz, coalesced_fields.alice.tsv
```

### Curator instructions

1. Open a terminal and run:

   ```bash
   python cde_editor.pyz coalesced_fields.alice.tsv
   ```

2. The browser opens with the pattern table loaded.

3. For each pattern, fill in the `decision` column:
   - **`strip`** — recognized instrument / valid pattern
   - **`skip`** — false positive / sentence fragment
   - **`modify`** — valid pattern but needs text correction (enter the
     corrected text in `modification`)

4. Optionally add notes explaining the decision.

5. Click **Save** (or Ctrl+S) to write changes back to the file.

6. Press **Ctrl-C** in the terminal to stop the server.

7. Send the annotated file back.

---

## 4. Merge Annotations

Once all curators have returned their files:

```bash
cde-analyzer pattern_util --merge-curation \
    curation_round/coalesced_fields.alice.tsv \
    curation_round/coalesced_fields.bob.tsv \
    curation_round/coalesced_fields.carol.tsv \
    -o curation_round/results/
```

This produces four output files:

| File | Contents |
|------|----------|
| `consensus.tsv` | Every pattern with its majority decision |
| `discrepancies.tsv` | Only patterns where curators disagree |
| `inter_rater_report.md` | Agreement statistics and interpretation |
| `discrepancies.html` | Interactive visual diff viewer |

### Consensus decisions

Each pattern gets a `consensus_decision` based on majority vote:

| Agreement level | Meaning |
|----------------|---------|
| `unanimous` | All curators chose the same decision |
| `majority` | >50% chose the same decision |
| `split` | No majority; tie-break order: strip > modify > skip |
| `single` | Only one curator reviewed this pattern |

---

## 5. Interpret Agreement Statistics

Open `inter_rater_report.md` for the full report. Key metrics:

### Cohen's Kappa (pairwise)

Computed for each pair of curators. Measures agreement beyond chance.

| Range | Interpretation |
|-------|---------------|
| > 0.80 | Almost perfect agreement |
| 0.60 – 0.80 | Substantial agreement |
| 0.40 – 0.60 | Moderate agreement |
| < 0.40 | Fair to poor agreement |

### Krippendorff's Alpha (overall)

A single reliability metric across all curators. Handles missing data
(when not all curators review every pattern).

| Range | Interpretation |
|-------|---------------|
| > 0.80 | Reliable |
| 0.67 – 0.80 | Tentatively acceptable |
| < 0.67 | Unreliable — consider refining guidelines |

### Per-category agreement

Shows which decisions are most consistent. Typical pattern: `strip` has
high agreement, `modify` has lower agreement (subjective edit choices).

---

## 6. Resolve Disagreements

### Interactive diff viewer

Open `discrepancies.html` in a browser. The viewer shows:

- Pattern text with curator decisions color-coded
- Agreement level badges (yellow = majority, pink = split)
- Modifications and notes from each curator
- Filters by text, agreement level, and consensus decision

### Joint curation session

For split decisions, host a joint session using the standalone editor
shared via screen share during a telecom meeting:

```bash
python cde_editor.pyz curation_round/results/discrepancies.tsv
```

One curator controls the editor while others discuss. Resolve each
disagreement, then save the final adjudicated file.

### Finalize

After resolution, produce the final curated file:

- **Option A**: Use `consensus.tsv` directly as `curated.tsv` (when
  agreement is high and few splits exist)
- **Option B**: Merge the adjudicated discrepancies back into
  `consensus.tsv` manually
- **Option C**: Re-run a focused curation round on the discrepancies only

Then continue the pipeline:

```bash
cde-analyzer workflow resume \
    --state-file phase1_output/.workflow_state.json
```

---

## 7. Complete Workflow Diagram

```
Master curator:
  ┌─────────────────────────────────────────────────────────┐
  │ 1. python scripts/build_editor_zipapp.py                │
  │    → dist/cde_editor.pyz                                │
  │                                                         │
  │ 2. cde-analyzer pattern_util --init-curation ...        │
  │    → per-curator .tsv files                             │
  │                                                         │
  │ 3. Send cde_editor.pyz + curator TSV to each reviewer   │
  └──────────────┬──────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
  Alice        Bob         Carol
  python       python      python
  cde_editor   cde_editor  cde_editor
  .pyz ...     .pyz ...    .pyz ...
  (curate)     (curate)    (curate)
    │            │            │
    └────────────┼────────────┘
                 │  send back files
                 ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 4. cde-analyzer pattern_util --merge-curation ...       │
  │    → consensus.tsv, discrepancies.tsv,                  │
  │      inter_rater_report.md, discrepancies.html          │
  │                                                         │
  │ 5. Open discrepancies.html (review statistics)          │
  │                                                         │
  │ 6. python cde_editor.pyz discrepancies.tsv              │
  │    (joint session via screen share)                     │
  │                                                         │
  │ 7. Save final curated.tsv → resume pipeline             │
  └─────────────────────────────────────────────────────────┘
```

---

## Centralized Server Mode

When curators have network access to a shared machine (e.g., a lab server
or cloud VM), you can skip file distribution entirely. A centralized
curation server hosts per-curator editor sessions — each curator opens a
unique URL in their browser.

### 9. Write a Server Config

Create `curation_server.yaml`:

```yaml
curators:
  - name: Alice Smith
    email: alice@example.com
  - name: Bob Jones
    email: bob@example.com
  - name: Carol Lee
    email: carol@example.com

server:
  host: 0.0.0.0        # listen on all interfaces
  port: 8443            # HTTPS port
  output_dir: ./curation_output
  timespan: 24h         # curation window

tls:
  mode: auto            # auto-generate self-signed cert

security:
  secret_key: auto      # auto-generated per session
  max_attempts: 5       # lockout after 5 failed attempts
```

**TLS modes:**

- **`auto`** — generates a self-signed certificate on first run
  (stored in `{output_dir}/.tls/`). Curators see a browser warning once.
- **`custom`** — provide your own cert/key (e.g., Let's Encrypt):
  ```yaml
  tls:
    mode: custom
    cert: /etc/letsencrypt/live/example.com/fullchain.pem
    key: /etc/letsencrypt/live/example.com/privkey.pem
  ```
- **`proxy`** — plain HTTP behind nginx/caddy with TLS termination
  (see [§14](#14-reverse-proxy-setup-optional)).

### 10. Start the Server

```bash
cde-analyzer pattern_util --serve-curation curation_server.yaml \
    --curation-source phase1_output/coalesced_fields.tsv
```

Output:

```
CDE Centralized Curation Server
  Admin:    https://127.0.0.1:8443/admin/
  Source:   phase1_output/coalesced_fields.tsv
  Output:   ./curation_output
  Expires:  2026-02-25 10:00 UTC
  TLS:      auto

  Curator URLs:
    Alice Smith: https://127.0.0.1:8443/c/alice_smith_67BD.../
    Bob Jones:   https://127.0.0.1:8443/c/bob_jones_67BD.../
    Carol Lee:   https://127.0.0.1:8443/c/carol_lee_67BD.../

  Press Ctrl-C to stop.
```

Send each curator their personal URL. The admin dashboard opens
automatically in your browser.

### 11. Monitor Progress

The admin dashboard at `/admin/` shows real-time curator statuses
with auto-refresh every 10 seconds.

| Status | Meaning |
|--------|---------|
| `pending` | Curator has not accessed their URL yet |
| `in_progress` | Curator has opened the editor |
| `submitted` | Curator has saved their work |
| `expired` | Curation window ended before submission |

Check status from the CLI:

```bash
cde-analyzer pattern_util --curation-status ./curation_output
```

When all curators submit, the server prints:

```
All curators have submitted. Ready for merge.
```

### 12. Security Model

**Token authentication**: Each curator URL contains an HMAC-authenticated
token with format `{slug}_{expiry_hex}_{hmac_hex}`:

- Bound to the curator's name and email
- Time-limited (expiry embedded in the token)
- Verified on every request via HMAC-SHA256
- 5-minute grace period after expiry for a final save

**Rate limiting**: After `max_attempts` failed authentication attempts
from an IP, progressive lockout kicks in (`lockout_base` seconds,
doubling each cycle).

**Directory isolation**: Each curator can only read/write their own
designated TSV file. No file listing or directory traversal is possible.

### 13. Collect and Merge

After all curators submit (or the timespan expires), press **Ctrl-C** to
stop the server. Then merge:

```bash
cde-analyzer pattern_util --merge-curation \
    curation_output/*.tsv \
    -o curation_output/results/
```

This produces the same output as the file-based workflow (§4):
`consensus.tsv`, `discrepancies.tsv`, `inter_rater_report.md`, and
`discrepancies.html`. Continue with [§5](#5-interpret-agreement-statistics)
to review agreement and [§6](#6-resolve-disagreements) to resolve splits.

### 14. Reverse Proxy Setup (Optional)

For production deployments with `tls.mode: proxy`, put the server behind
nginx:

```nginx
server {
    listen 443 ssl;
    server_name curation.example.com;
    ssl_certificate /etc/letsencrypt/live/.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

With this setup, use `port: 8080` and `tls.mode: proxy` in your config.

### Centralized vs File-Based

| Aspect | File-based (§1–7) | Centralized (§9–13) |
|--------|-------------------|---------------------|
| Curator setup | Install Python + receive zipapp | Open a URL |
| File exchange | Email/share files back and forth | None — server manages files |
| Real-time monitoring | No | Admin dashboard with auto-refresh |
| Network required | No — fully offline | Yes — curators need server access |
| TLS/security | N/A | HMAC tokens, rate limiting, TLS |
| Best for | Remote curators, air-gapped environments | Lab/team settings, cloud VMs |

---

## 8. Tips

- **Two curators minimum**, three recommended for Krippendorff's alpha
- **Pilot round**: Run a small sample (50 patterns) first to calibrate
  curation guidelines before the full set
- **Decision consistency**: Agree on definitions of "strip" vs "modify"
  before starting — ambiguity here drives most disagreements
- **Instrument vs phrase**: If Phase 1 patterns include sentence fragments,
  document this in your guidelines so all curators handle them consistently
- **Version the zipapp**: The `--version` flag shows the editor version;
  ensure all curators use the same build
