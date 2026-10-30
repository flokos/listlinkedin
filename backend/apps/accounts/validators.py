"""Password rules beyond Django's (docs/v2/21-SECURITY-REVIEW.md, ASVS V6.1.2 and V6.2.11)."""

from django.core.exceptions import ValidationError

# Words that make a password easy to guess for this service: its own name.
CONTEXT_WORDS = ("listlinkedin",)


class ContextWordsValidator:
    """Refuses passwords containing the service's name, in any case or spacing."""

    def validate(self, password: str, user=None) -> None:
        squashed = "".join(password.lower().split())
        if any(word in squashed for word in CONTEXT_WORDS):
            raise ValidationError(
                "Choose a password that doesn't contain the name of this site.",
                code="password_context_word",
            )

    def get_help_text(self) -> str:
        return "Your password can't contain the name of this site."
