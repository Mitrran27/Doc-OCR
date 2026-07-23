import re


def slugify(text: str, max_words: int = 6) -> str:
    """'Standby Battery Capacity Requirements for NAC Circuits' -> 'standby-battery-capacity-requirements-for-nac'"""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    words = text.split()[:max_words]
    slug = "-".join(words).strip("-")
    return slug or "untitled"
