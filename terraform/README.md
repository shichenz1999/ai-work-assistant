# Terraform (Render Deployment)

Deploy the orchestrator service to Render using the repo Dockerfile.

## Prerequisites
- Render API key and owner/team ID.
- A Git repo URL Render can access.

## Configure
```bash
cp terraform.tfvars.example terraform.tfvars
```

Required in `terraform.tfvars`:
- `render_api_key`
- `render_owner_id`
- `repo_url`
- `anthropic_api_key`
- `google_oauth_client_id`
- `google_oauth_client_secret`
- `public_base_url`

Optional (defaults apply):
- `repo_branch`
- `service_name`
- `plan`
- `region`

## Deploy
```bash
terraform init
terraform plan
terraform apply
```

## Verify
```bash
curl https://<public_base_url>/health
```

## Notes
- Do not commit `terraform.tfvars`.
- Render builds from the Dockerfile in the repo root.
