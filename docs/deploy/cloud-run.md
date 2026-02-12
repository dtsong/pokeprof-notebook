# Cloud Run Deploy (us-central1)

This project is designed to run as a single Cloud Run service that serves:
- the static SvelteKit SPA (`/`)
- the FastAPI API (`/api/*`, including SSE `/api/query`)

For v1 we run in `us-central1`.

## Prereqs

- A GCP project (`pokeprof-dev` or `pokeprof-prod`)
- Org policy allows disabling invoker IAM checks for the project:
  - `constraints/run.managed.requireInvokerIam` is NOT enforced at the project
    level
- Firebase project exists for the env, with authorized domain set:
  - dev: `judge-dev.trainerlab.io`
  - prod: `judge.trainerlab.io`
- Firestore contains an allowlist document for your email:
  - collection: `allowlist`
  - doc id: your email lowercased
  - fields: `enabled=true`, `role="admin"|"judge"`

## Build + Deploy

1) Build and push the container:

```bash
PROJECT_ID=pokeprof-dev
REGION=us-central1
SERVICE=pokeprof

gcloud config set project "$PROJECT_ID"

gcloud auth configure-docker "$REGION-docker.pkg.dev"

# Create Artifact Registry repo once (if needed)
# gcloud artifacts repositories create pokeprof \
#   --repository-format=docker \
#   --location "$REGION"

IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/pokeprof/$SERVICE:$(git rev-parse --short HEAD)"

docker build -t "$IMAGE" .
docker push "$IMAGE"
```

2) Deploy to Cloud Run:

```bash
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --no-invoker-iam-check \
  --timeout 900 \
  --concurrency 20 \
  --set-env-vars "FIREBASE_PROJECT_ID=$PROJECT_ID" \
  --set-secrets "ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
  --set-secrets "POKEPROF_SESSION_SECRET=POKEPROF_SESSION_SECRET:latest"
```

Notes:
- We intentionally do NOT use `--allow-unauthenticated` because that typically
  adds `allUsers` IAM bindings, which may conflict with org IAM domain
  restrictions. Instead we disable invoker IAM checks.
- Set `min-instances=1` during events if cold starts are a problem.

## Custom Domain

After deploy, map the custom domain in Cloud Run:
- dev: `judge-dev.trainerlab.io`
- prod: `judge.trainerlab.io`

Then add the domain to Firebase Auth "Authorized domains" for the matching
Firebase project.

## Smoke Test

- Visit `https://<domain>/invite`
- Sign in with Google or Email/Password
- If using Email/Password, verify email before retrying
- Confirm query streaming works on `/` (Search tab)
