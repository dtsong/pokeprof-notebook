# Terraform (Cloud Run: us-central1)

This directory provisions the app infrastructure for PokéProf Notebook.

Scope (per environment):
- Enable required GCP APIs
- Artifact Registry repository for container images
- Runtime service account with least-privilege IAM
- Secret Manager secrets (no secret values)
- Cloud Run v2 service in `us-central1` with `invoker_iam_disabled=true`

Non-goals:
- Building/pushing the container image (do that separately)
- Creating org/folder/projects or org policies (handled in the foundation repo)
- Setting secret *values* (you will add secret versions manually)

## Layout

- `modules/cloudrun_app`: reusable module
- `environments/dev`: deploys to `pokeprof-dev`
- `environments/prod`: deploys to `pokeprof-prod`

## Apply

1) Ensure the project exists and the org policy allows disabling invoker IAM
checks:
- `constraints/run.managed.requireInvokerIam` is NOT enforced at the project level.

2) Add secret values (once) after Terraform creates the secrets:

```bash
gcloud config set project pokeprof-dev

echo -n "<anthropic-key>" | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-
python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY | tr -d '\n' | gcloud secrets versions add POKEPROF_SESSION_SECRET --data-file=-
```

3) Build and push the Docker image, then apply Terraform with the image URI.

Example image URI format:
`us-central1-docker.pkg.dev/<project_id>/pokeprof/pokeprof:<tag>`

When building the image, provide the Firebase web config as Docker build args
(these are compile-time Vite env vars and are NOT secrets):

```bash
docker build \
  --build-arg VITE_FIREBASE_API_KEY="..." \
  --build-arg VITE_FIREBASE_AUTH_DOMAIN="judge-dev.trainerlab.io" \
  --build-arg VITE_FIREBASE_PROJECT_ID="pokeprof-dev" \
  --build-arg VITE_FIREBASE_APP_ID="..." \
  -t us-central1-docker.pkg.dev/pokeprof-dev/pokeprof/pokeprof:TAG .
```

## Notes

- The Cloud Run service is publicly reachable at the network layer (invoker IAM
  checks disabled), but the application enforces Firebase invite-only auth.
- Domain mapping (`judge-dev.trainerlab.io`, `judge.trainerlab.io`) is handled
  outside Terraform for now.
