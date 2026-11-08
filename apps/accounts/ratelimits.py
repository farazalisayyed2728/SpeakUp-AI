from apps.core.ratelimit import Rule

# Tuned per endpoint risk. Per-IP rules stop floods; per-email rules stop targeted guessing,
# and work even when many users share one IP (campus, office) because we use both.
LOGIN_IP = Rule("login_ip", limit=20, window=600)
LOGIN_EMAIL = Rule("login_email", limit=5, window=600)
REGISTER_IP = Rule("register_ip", limit=10, window=3600)
RESET_IP = Rule("reset_ip", limit=10, window=3600)
RESET_EMAIL = Rule("reset_email", limit=3, window=3600)
RESEND_IP = Rule("resend_ip", limit=10, window=3600)
RESEND_EMAIL = Rule("resend_email", limit=3, window=3600)
PASSWORD_CHANGE_USER = Rule("pwchange_user", limit=10, window=3600)