import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).parent.parent
GLOSSARY = ROOT / "GLOSSARY.md"
SRC = ROOT / "src" / "home_stock"

# Avoided words too common in code to mean the glossary's concept (a SQL count, a dict entry, a database
# transaction); the reviewer judges these
EVERYDAY = {
    "amount", "build", "buy", "count", "delete", "entry", "group", "log", "measure", "order", "tag", "transaction",
    "type",
    "weight",  # Flet's font weight, not a Product's
}  # fmt: skip


def _words(text: str) -> tuple[str, ...]:
    """A name or a term as lowercase words: "DemoRestock", "demo_restock" and "Demo restock" all give demo, restock."""
    return tuple(word.lower() for word in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", text))


def _contains(words: tuple[str, ...], part: tuple[str, ...]) -> bool:
    return any(words[i : i + len(part)] == part for i in range(len(words) - len(part) + 1))


def _avoided_terms() -> set[tuple[str, ...]]:
    """Every _Avoid_ word of GLOSSARY.md, except one inside a glossary term ("purchase" under Batch, but Purchase is a
    term) and the EVERYDAY ones."""
    lines = GLOSSARY.read_text(encoding="utf-8").splitlines()
    terms = [_words(match[1]) for line in lines if (match := re.match(r"\*\*(.+?)\*\*", line))]
    avoided = {
        _words(word)
        for line in lines
        if line.startswith("_Avoid_:")
        for word in line.removeprefix("_Avoid_:").split(",")
    }
    return {
        word
        for word in avoided
        if word and " ".join(word) not in EVERYDAY and not any(_contains(term, word) for term in terms)
    }


def test_the_glossary_has_avoided_words_to_check() -> None:
    assert ("restock",) in _avoided_terms()


def test_no_name_in_the_code_uses_a_word_the_glossary_avoids() -> None:
    avoided = _avoided_terms()
    found = []
    for path in SRC.rglob("*.py"):
        with path.open("rb") as source:
            for token in tokenize.tokenize(source.readline):
                if token.type == tokenize.NAME:
                    words = _words(token.string)
                    found += [
                        f"{path.relative_to(ROOT)}:{token.start[0]} {token.string} ({' '.join(word)})"
                        for word in avoided
                        if _contains(words, word)
                    ]
    assert not found, (
        "GLOSSARY.md says to avoid these words: use its term instead, or add a word that means something else here "
        "(a library's API) to EVERYDAY:\n" + "\n".join(sorted(set(found)))
    )
