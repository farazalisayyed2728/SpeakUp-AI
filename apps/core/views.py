from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

PRACTICE_MODES = [
    {
        "name": "Job interview",
        "blurb": "Role-based questions with follow-ups.",
        "prompt": "Tell me about a time you disagreed with your manager.",
        "bg": "linear-gradient(150deg,#7b5cff,#4a2fd0)",
    },
    {
        "name": "HR round",
        "blurb": "Strengths, salary and notice-period questions.",
        "prompt": "Where do you see yourself in three years?",
        "bg": "linear-gradient(150deg,#1f7a8c,#134e5e)",
    },
    {
        "name": "Self-introduction",
        "blurb": "A clear 60 seconds that sounds like you.",
        "prompt": "Introduce yourself to a new team on day one.",
        "bg": "linear-gradient(150deg,#d9488b,#8b2e63)",
    },
    {
        "name": "Daily conversation",
        "blurb": "Everyday English at a natural pace.",
        "prompt": "Ask a neighbour to turn their music down.",
        "bg": "linear-gradient(150deg,#e08a1e,#a35a0a)",
    },
    {
        "name": "Public speaking",
        "blurb": "Open strong, structure it, land it.",
        "prompt": "Give a two-minute talk on a skill you taught yourself.",
        "bg": "linear-gradient(150deg,#3a5bd9,#22379a)",
    },
    {
        "name": "Group discussion",
        "blurb": "Join in, hold your point, include others.",
        "prompt": "Should offices go back to five days a week?",
        "bg": "linear-gradient(150deg,#2d9d6f,#17604a)",
    },
    {
        "name": "Professional meeting",
        "blurb": "Updates, pushback and clear asks.",
        "prompt": "Explain a delayed deadline to your stakeholders.",
        "bg": "linear-gradient(150deg,#6c4ab6,#3b2679)",
    },
]


class LandingView(TemplateView):
    template_name = "core/landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modes"] = PRACTICE_MODES
        return ctx

@never_cache
@login_required
def dashboard(request):
    """Placeholder landing spot after login. The real dashboard arrives in Phase 3."""
    return render(request, "core/dashboard.html")