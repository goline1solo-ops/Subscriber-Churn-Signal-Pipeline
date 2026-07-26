# GUIDE — Containerized ELT + AI Enrichment Pattern

Everything you'd need to reacquaint yourself with this pattern after months
away, without re-deriving it from scratch. Read this before touching code if
anything feels unfamiliar.

---

## 1. The architecture, in one picture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Python    │────▶│  Postgres   │◀────│     dbt     │
│  (extract + │     │  (staging + │     │ (transform) │
│  AI scoring)│     │   modeled)  │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
    all three on one Docker network, via docker-compose
```

- **Python** pulls/generates raw records, calls an LLM to enrich one field
  (a score, a label, a sentiment) from unstructured text, loads everything
  into a Postgres staging table.
- **Postgres** just holds data - staging (raw + AI-scored) and modeled
  (dbt's output).
- **dbt** transforms staging data into a clean, business-ready table. This
  is the "T" in **ELT** - Transform happens *after* loading, inside the
  warehouse, using the warehouse's own SQL - not a separate step before
  loading (that's the older "ETL" pattern). `extract_load.py` is named that
  way on purpose: it only does E and L. dbt does T, separately, afterward.

---

## 2. Prerequisites checklist (do these BEFORE anything else)

- [ ] **Docker Desktop installed AND running** (open the app, wait for the
      whale icon to go solid in the system tray - `docker ps` failing with
      "cannot connect to the Docker API" almost always means Docker Desktop
      just isn't open yet, not a real config problem).
- [ ] **WSL2 enabled** (Windows only) - Docker Desktop's installer usually
      handles this, but if it didn't, run `wsl --install` in an
      **administrator** PowerShell, then restart your machine.
- [ ] If your AI step uses **Ollama locally**: it's installed and running
      natively on your machine (`ollama list` should show a model). Ollama
      is *not* containerized in this pattern - it stays on the host, and
      containers reach it via `host.docker.internal` (see gotcha below).
- [ ] `cp .env.example .env` and fill in real values.

---

## 3. THE recurring gotcha - read this twice

**One question decides every `POSTGRES_HOST` / `OLLAMA_HOST` value you'll
ever set: is the code about to run ON MY MACHINE DIRECTLY, or IS A DOCKER
CONTAINER RUNNING IT?**

Picture a small office campus: Postgres, Python, and dbt each have their own
building, connected by a private internal phone extension system (that's
the Docker network, `app_net`). You, working from home in your own terminal,
are not on that internal extension system at all.

| Where the code actually executes | What `POSTGRES_HOST` / `OLLAMA_HOST` needs to be |
|---|---|
| You run `python script.py` yourself, in your own terminal (native) | `localhost` - the only address that reaches a container's published port from outside Docker |
| A container runs it automatically (e.g. `extract_load.py` via `docker-compose up`) | The **sibling container's service name** (e.g. `postgres`) to reach another container, or `host.docker.internal` to reach something running on your host machine (like local Ollama) |

`localhost` **inside a container** always means that container itself -
never a sibling container, never your host machine. This single fact
explains nearly every "connection refused" error you'll hit with this stack.
**Whenever you switch between running something natively vs. via
`docker-compose up`, you need to flip `.env` to match** - it will not work
both ways at once.

---

## 4. Docker concepts, recap

- **Image vs. container**: an image is a frozen recipe (built once,
  `docker build`); a container is a *running instance* of that image.
  `image: postgres:16` pulls an already-built image from Docker Hub;
  `build: ./python` constructs a custom one from a local `Dockerfile`.
- **Two different names per container**: the **service name**
  (`postgres`, under `services:` in `docker-compose.yml`) is what sibling
  containers use to reach each other over the network. The
  **`container_name`** (e.g. `app_postgres`) is a separate, human-facing
  label used from your own terminal (`docker ps`, `docker exec`,
  `docker logs`). Both are made-up strings - neither is a Docker keyword.
- **`healthcheck` + `depends_on: condition: service_healthy`**: stops
  dependent containers from starting before a service (usually Postgres)
  can *actually* accept connections, not just "has started." A container
  being "up" and a database being "ready" are two different moments.
- **Volumes** (`pgdata:/var/lib/postgresql/data`): containers are disposable
  by default; a named volume is what makes the database's data survive a
  restart (`docker-compose down` alone won't wipe it; `docker-compose
  down -v` will, since `-v` explicitly removes volumes too).
- **`docker-compose up` vs. `docker-compose run`**: `up` starts the defined
  services as-is (long-running or one-shot per their `CMD`). `run --rm
  <service> <command>` spins up a *temporary* one-off container from that
  service's image, runs a different command than its default `CMD`, then
  removes itself. Useful for running a one-off script inside the exact
  container environment without disturbing the running stack.
- **`docker ps -a`**: `-a` includes *stopped/exited* containers too (plain
  `docker ps` only shows running ones). A one-shot job container (like
  `python`, whose job is to run once and exit) will disappear from plain
  `docker ps` the moment it finishes - `Exited (0)` means it finished
  successfully, not that something broke.
- **Only ONE file auto-runs per container**: whatever's named in that
  service's `Dockerfile` `CMD` (e.g. `CMD ["python", "extract_load.py"]`).
  Every other file in that folder gets copied in (`COPY . .`) but never
  executes on its own - a one-off exploration/analysis script just sits
  there until a human deliberately runs it (natively, or via
  `docker-compose run`).

---

## 5. Docker Compose command reference

| Command | What it does |
|---|---|
| `docker-compose up -d` | Start every service in the background |
| `docker-compose up -d --build` | Rebuild images first (needed after code/Dockerfile changes), then start |
| `docker-compose up -d <service>` | Start just one service (e.g. `postgres`) |
| `docker-compose run --rm <service> <command>` | One-off: fresh temporary container from that service's image, runs `<command>` instead of its default `CMD`, removes itself after |
| `docker-compose logs -f <service>` | Follow that service's logs live (`Ctrl+C` to stop watching - doesn't stop the container) |
| `docker-compose ps` | List this project's containers and their status |
| `docker-compose stop` | Pause containers, keep them (and the network) around - resume with `docker-compose start` |
| `docker-compose down` | Stop **and remove** containers + network. Data survives (it's in the named volume) |
| `docker-compose down -v` | Same as `down`, **plus deletes volumes** - this is the one that actually wipes Postgres data. Only reach for it deliberately |

**Rule of thumb for day-to-day use**: `up -d` to start, `logs -f <service>`
to watch something run, `down` when you're done for the session (safe -
your data's still in the volume next time), `down -v` only when you
genuinely want a clean slate.

---

## 6. Postgres, recap (+ T-SQL cheat sheet)

Postgres is a **server** your code connects to as a **client** - not a
library you `import`. That's why a connection needs host/port/user/password
instead of just being available.

| T-SQL (SQL Server) | Postgres |
|---|---|
| `SELECT TOP 10 ...` | `SELECT ... LIMIT 10` |
| `GETDATE()` | `NOW()` / `CURRENT_DATE` |
| `DATEDIFF(day, d1, d2)` | `d2 - d1` (direct subtraction), or `AGE(d2, d1)` |
| `SELECT ... INTO #temp` | `CREATE TEMP TABLE temp AS SELECT ...` |
| (implicit statement splitting, lenient) | **semicolons are required** between statements - a missing one silently merges two statements into one, and the error shows up at whatever comes *after* the missing semicolon, not at the semicolon itself |
| `IF OBJECT_ID(...) IS NOT NULL DROP TABLE ...` | `DROP TABLE IF EXISTS name;` |

**Where the database name/user actually get created**: the official
`postgres` image's own startup script reads `POSTGRES_DB`/`POSTGRES_USER`/
`POSTGRES_PASSWORD` **only the first time it starts against an empty data
volume**. After that, the volume's real contents are the source of truth -
changing `.env` afterward does nothing until the volume is wiped
(`docker-compose down -v`).

**Temp tables are scoped to one session/connection.** A temp table created
in one DBeaver tab won't be visible from a different tab/connection, and
`DROP TABLE IF EXISTS` printing "does not exist, skipping" the first time
you run a script in a fresh session is completely normal, not an error.

**Common script-debugging traps** (both hit while building this the first
time):
- A **trailing comma** right before `FROM` in a `SELECT` list is a syntax
  error - Postgres won't tell you it's a comma problem, it'll complain about
  `FROM` itself.
- A **missing semicolon** between two statements gets them silently merged
  into one - the resulting error often shows up several statements later
  (e.g. "relation X does not exist" when X's `CREATE` never actually ran
  because an earlier, merged statement failed).

**Indexes**: without one, a lookup scans every row. Irrelevant at a few
hundred rows; essential at millions. Good, honest answer if asked about
scaling: "at this size I didn't need one; at production scale I'd index
whatever columns get joined/filtered on most."

---

## 7. dbt, recap

A dbt **model** is just a `.sql` file containing **one `SELECT` statement**
- nothing to do with machine learning. dbt runs it and materializes the
result as a real table or view. Because it's *one* statement, you can't use
temp tables/multiple `CREATE`s inside a model - use **CTEs** (`WITH name AS
(...)`) instead, chained together, ending in one final `SELECT`.

- **`profiles.yml`**: connection info, kept *outside* the portable project
  logic - same pattern as `.env` vs. `.env.example`, just implemented via
  Jinja templating (`{{ env_var('POSTGRES_PASSWORD') }}`) instead of two
  separate files. Safe to commit, because the actual secret values are
  resolved from environment variables at runtime, never hardcoded here.
  Normally lives at `~/.dbt/profiles.yml`; in a container, set
  `ENV DBT_PROFILES_DIR=/wherever/the/file/is` in the Dockerfile instead.
- **`sources.yml`**: declares a raw table dbt didn't create itself, so
  models can reference it via `{{ source('alias', 'table_name') }}` instead
  of hardcoding the name. Same indirection idea as `{{ ref('other_model') }}`
  for referencing another dbt model - both let dbt build its dependency
  graph automatically by scanning for these calls.
- **`+materialized: table` vs. `view`**: `table` computes once and stores
  the result (fast to query later, needs an explicit re-run to refresh);
  `view` just saves the query and re-runs it live every time it's queried.
- **Layers**: staging (light cleanup of one raw source) -> intermediate
  (joins/logic) -> mart (final, business-ready - what a dashboard actually
  queries). Your model in `dbt/models/` is a mart-layer model.

---

## 8. The AI-enrichment step, and the mistake to avoid

Calling an LLM (Ollama locally, or a cloud API) to turn unstructured text
into a structured signal (a score, a label) is the piece that makes this
"AI-flavored" rather than a plain data pipeline.

**Force structured output** (Ollama's `"format": "json"` option, or
equivalent) so you get parseable JSON back instead of free-form prose you'd
have to regex out yourself.

**Data leakage - the mistake that will quietly invalidate your results**: if
you ever synthesize an input field (like fake text) and you condition what
you generate on the real ground-truth outcome you're eventually trying to
predict, you've leaked the answer into your own input. Any correlation you
later "discover" between your AI's output and the real outcome is
meaningless, because you built it in by construction. Only condition
synthetic inputs on signals that would realistically exist *before* the
outcome is known.

**Validate honestly, don't assume the AI step is the star**: pull the
loaded data into pandas and actually check whether your AI-derived signal
correlates with a real outcome column, and compare it against a simple
model's feature importances trained on the raw underlying signals. It's
common (and fine) to find the AI signal adds *real but modest* value, not
overwhelming predictive power - that's a more credible, defensible finding
than an unchecked assumption that "the AI part is what matters most."
Correlation only catches *linear* relationships - a feature can matter a lot
in a non-linear/threshold way (e.g. random forest feature importance) while
showing weak plain correlation. Both tools tell you something different;
neither alone is the full picture.

---

## 9. If a step swaps Postgres for BigQuery

BigQuery isn't "Postgres, but managed" - there's no server to connect to at
all. It's reached entirely through Google's API, authenticated by identity
(your own login, or a service account) rather than a password.

- `gcloud auth login` authenticates the **gcloud CLI tool itself**. It does
  **not** set up what Python client libraries read.
- `gcloud auth application-default login` is the separate command that
  creates **Application Default Credentials (ADC)** - this is what
  `bigquery.Client()` (with no credentials passed in) actually finds
  automatically. Both steps are needed; doing only the first one is a
  common trap.
- Locally, ADC uses *your own* identity. In production, a compute resource
  (Cloud Run, GKE) has a **service account** attached instead - same code,
  different identity resolved underneath it automatically.
- In `profiles.yml`, a BigQuery target has no host/port/password at all -
  see the commented-out `prod:` example in this repo's `profiles.yml`.

**Local-vs-production infrastructure mapping**, if this ever comes up:

| Local (this template) | AWS | GCP |
|---|---|---|
| docker-compose (one machine) | ECS / Fargate | Cloud Run / GKE |
| Postgres container | RDS | Cloud SQL |
| Docker's auto-created network | VPC + security groups | VPC + firewall rules |
| Plaintext `.env` | Secrets Manager + IAM role | Secret Manager + service account |

---

## 10. DBeaver quick reference

- **Connect**: New Database Connection -> PostgreSQL -> host `localhost`,
  port `5432`, plus your `.env` values. First connection prompts to
  download the JDBC driver - just let it, one-time, automatic.
- **`F4`** on a selected table - object properties (columns, types,
  constraints) - the DBeaver equivalent of SSMS's Alt+F1.
- **`Ctrl+Enter`** - run the statement your cursor's in (or your selection)
  - equivalent of SSMS's F5.
- **`Alt+X`** - run the *entire* script (every statement), not just one.
- **`Ctrl+\`** - run the current query, results in a new tab (good for
  comparing multiple outputs side by side).

---

## 11. Coming back after months away - the actual checklist

1. Open **Docker Desktop**, wait for it to fully start.
2. `docker ps -a` - see what's already there from last time.
3. Check `.env` - does `POSTGRES_HOST`/`OLLAMA_HOST` match how you're about
   to run things right now (native vs. `docker-compose up`)? See section 3.
4. `docker-compose up -d postgres` - bring the database up first.
5. If iterating on Python code: run it **natively** first (fast feedback
   loop), flip `.env` to `localhost`.
6. Once stable, run the **real** thing through Docker:
   `docker-compose up -d --build python` (flip `.env` back to container
   values first).
7. `docker-compose run --rm --build dbt dbt run` once your model SQL is
   ready - rebuild (`--build`) if the model file changed since the image
   was last built.
8. Verify results in DBeaver or `docker exec <container> psql -U <user> -d <db> -c "..."`.

---

## 12. Glossary - fast recall

- **Container vs. image** - image = frozen recipe; container = a running
  instance of it.
- **ELT vs. ETL** - transform after loading, inside the warehouse; the
  modern pattern, and the reason dbt exists.
- **dbt model** - a `.sql` file dbt turns into a table/view. No relation to
  ML models.
- **ADC** - Application Default Credentials; how Python libraries
  auto-discover a GCP identity without a stored password.
- **Healthcheck / depends_on** - how one container waits for another to be
  truly ready, not just started.
- **Data leakage** - accidentally baking the answer into your own input.
- **`host.docker.internal`** - special DNS name a container uses to reach
  its host machine; only resolves from inside a container.
- **CTE** - `WITH name AS (...)` - a named, scoped sub-query usable within
  one statement; the dbt-model equivalent of a T-SQL temp table.
