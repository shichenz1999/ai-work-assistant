terraform {
  required_providers {
    render = {
      source  = "render-oss/render"
      version = "1.8.0"
    }
  }
}

provider "render" {
  api_key = var.render_api_key
  owner_id = var.render_owner_id
}

resource "render_web_service" "orchestrator" {
  name          = var.service_name
  plan          = var.plan
  region        = var.region
  start_command = "uvicorn orchestrator.main:app --host 0.0.0.0 --port $PORT"

  runtime_source = {
    docker = {
      auto_deploy = true
      branch      = var.repo_branch
      repo_url    = var.repo_url
    }
  }

  env_vars = {
    ANTHROPIC_API_KEY            = { value = var.anthropic_api_key }
    GOOGLE_OAUTH_CLIENT_ID       = { value = var.google_oauth_client_id }
    GOOGLE_OAUTH_CLIENT_SECRET   = { value = var.google_oauth_client_secret }
    PUBLIC_BASE_URL              = { value = var.public_base_url }
  }
}

resource "render_background_worker" "discord_listener" {
  name          = var.discord_service_name
  plan          = var.plan
  region        = var.region
  start_command = "python -m discord_listener.main"

  runtime_source = {
    docker = {
      auto_deploy = true
      branch      = var.repo_branch
      repo_url    = var.repo_url
    }
  }

  env_vars = {
    DISCORD_BOT_TOKEN = { value = var.discord_bot_token }
    PUBLIC_BASE_URL   = { value = var.public_base_url }
    AUTH_PROVIDERS    = { value = "google" }
  }
}
