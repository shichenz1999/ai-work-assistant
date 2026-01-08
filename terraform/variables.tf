variable "render_api_key" {
  description = "Render API key (do not commit real value)."
  type        = string
  sensitive   = true
}

variable "render_owner_id" {
  description = "Render owner/team ID."
  type        = string
}

variable "repo_url" {
  description = "Git repository URL Render pulls from."
  type        = string
}

variable "repo_branch" {
  description = "Git branch to deploy."
  type        = string
  default     = "main"
}

variable "service_name" {
  description = "Render service name."
  type        = string
  default     = "ai-orchestrator"
}

variable "discord_service_name" {
  description = "Render service name for the Discord listener."
  type        = string
  default     = "discord-listener"
}

variable "plan" {
  description = "Render plan slug (starter, standard, etc.)."
  type        = string
  default     = "starter"
}

variable "region" {
  description = "Render region slug."
  type        = string
  default     = "oregon"
}

variable "anthropic_api_key" {
  description = "Anthropic API key."
  type        = string
  sensitive   = true
}

variable "google_oauth_client_id" {
  description = "Google OAuth client ID."
  type        = string
}

variable "google_oauth_client_secret" {
  description = "Google OAuth client secret."
  type        = string
  sensitive   = true
}


variable "public_base_url" {
  description = "Base URL for callbacks (e.g., https://your-app.onrender.com)."
  type        = string
}

variable "discord_bot_token" {
  description = "Discord bot token."
  type        = string
  sensitive   = true
}
