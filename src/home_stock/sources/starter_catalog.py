"""The Starter Catalog: Products a small household usually keeps, which a new user adds in one go instead of typing
each (GLOSSARY.md)."""

from collections.abc import Iterable, Sequence
from typing import NamedTuple

from sqlalchemy import Engine

from home_stock.domain.formatting import parse_pack_size
from home_stock.domain.stock import Category, ProductDraft, Unit, name_key
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.products import list_products


class StarterProduct(NamedTuple):
    name: str
    # The seeded Category and Unit by name; one the user renamed or deleted leaves the Product out
    category: str
    unit: str
    # As typed in the Product form ("1 kg"), or None
    pack_size: str | None = None
    usual_shelf_life_days: int | None = None


SPOZYWCZE, NAPOJE, CHEMIA = "Spożywcze", "Napoje", "Chemia i środki czystości"
HIGIENA, APTECZKA, ZWIERZETA, DOM = "Higiena i kosmetyki", "Apteczka", "Zwierzęta", "Dom i inne"

# In Ustawienia's order of the seeded Categories; Usual Shelf Life only for what goes off within a few years
STARTER_CATALOG = [
    StarterProduct("Mleko", SPOZYWCZE, "opakowanie", "1 l", 7),
    StarterProduct("Masło", SPOZYWCZE, "opakowanie", "200 g", 30),
    StarterProduct("Jogurt naturalny", SPOZYWCZE, "sztuka", None, 14),
    StarterProduct("Śmietana", SPOZYWCZE, "sztuka", None, 14),
    StarterProduct("Ser żółty", SPOZYWCZE, "opakowanie", None, 14),
    StarterProduct("Twaróg", SPOZYWCZE, "opakowanie", None, 7),
    StarterProduct("Jajka", SPOZYWCZE, "opakowanie", None, 21),
    StarterProduct("Szynka", SPOZYWCZE, "opakowanie", None, 5),
    StarterProduct("Chleb", SPOZYWCZE, "sztuka", None, 3),
    StarterProduct("Mąka pszenna", SPOZYWCZE, "opakowanie", "1 kg", 365),
    StarterProduct("Cukier", SPOZYWCZE, "opakowanie", "1 kg"),
    StarterProduct("Sól", SPOZYWCZE, "opakowanie", "1 kg"),
    StarterProduct("Ryż", SPOZYWCZE, "opakowanie", "1 kg", 365),
    StarterProduct("Makaron", SPOZYWCZE, "opakowanie", "500 g", 365),
    StarterProduct("Kasza gryczana", SPOZYWCZE, "opakowanie", None, 365),
    StarterProduct("Płatki owsiane", SPOZYWCZE, "opakowanie", "500 g", 270),
    StarterProduct("Płatki śniadaniowe", SPOZYWCZE, "opakowanie", None, 270),
    StarterProduct("Bułka tarta", SPOZYWCZE, "opakowanie", None, 180),
    StarterProduct("Olej rzepakowy", SPOZYWCZE, "butelka", "1 l", 365),
    StarterProduct("Oliwa z oliwek", SPOZYWCZE, "butelka", "500 ml", 540),
    StarterProduct("Ocet", SPOZYWCZE, "butelka"),
    StarterProduct("Kawa", SPOZYWCZE, "opakowanie", "500 g", 365),
    StarterProduct("Herbata", SPOZYWCZE, "opakowanie", None, 730),
    StarterProduct("Miód", SPOZYWCZE, "słoik", None, 730),
    StarterProduct("Dżem", SPOZYWCZE, "słoik", None, 270),
    StarterProduct("Czekolada", SPOZYWCZE, "sztuka", None, 270),
    StarterProduct("Pomidory w puszce", SPOZYWCZE, "puszka", "400 g", 730),
    StarterProduct("Koncentrat pomidorowy", SPOZYWCZE, "słoik", None, 365),
    StarterProduct("Fasola w puszce", SPOZYWCZE, "puszka", None, 730),
    StarterProduct("Kukurydza w puszce", SPOZYWCZE, "puszka", None, 730),
    StarterProduct("Tuńczyk w puszce", SPOZYWCZE, "puszka", None, 1095),
    StarterProduct("Ketchup", SPOZYWCZE, "butelka", None, 365),
    StarterProduct("Majonez", SPOZYWCZE, "słoik", None, 180),
    StarterProduct("Musztarda", SPOZYWCZE, "słoik", None, 180),
    StarterProduct("Bulion w kostkach", SPOZYWCZE, "opakowanie", None, 365),
    StarterProduct("Pieprz", SPOZYWCZE, "opakowanie"),
    StarterProduct("Papryka słodka", SPOZYWCZE, "opakowanie"),
    StarterProduct("Mrożone warzywa", SPOZYWCZE, "opakowanie", "450 g", 365),
    StarterProduct("Ziemniaki", SPOZYWCZE, "opakowanie", "2 kg", 30),
    StarterProduct("Cebula", SPOZYWCZE, "opakowanie", "1 kg", 30),
    StarterProduct("Czosnek", SPOZYWCZE, "sztuka", None, 60),
    StarterProduct("Marchew", SPOZYWCZE, "opakowanie", "1 kg", 21),
    StarterProduct("Pomidory", SPOZYWCZE, "opakowanie", None, 7),
    StarterProduct("Jabłka", SPOZYWCZE, "opakowanie", "1 kg", 14),
    StarterProduct("Banany", SPOZYWCZE, "sztuka", None, 5),
    StarterProduct("Woda mineralna", NAPOJE, "butelka", "1,5 l", 365),
    StarterProduct("Sok pomarańczowy", NAPOJE, "opakowanie", "1 l", 180),
    StarterProduct("Napój gazowany", NAPOJE, "butelka", "1,5 l", 180),
    StarterProduct("Piwo", NAPOJE, "puszka", "500 ml", 180),
    StarterProduct("Płyn do naczyń", CHEMIA, "butelka"),
    StarterProduct("Tabletki do zmywarki", CHEMIA, "opakowanie"),
    StarterProduct("Sól do zmywarki", CHEMIA, "opakowanie"),
    StarterProduct("Nabłyszczacz do zmywarki", CHEMIA, "butelka"),
    StarterProduct("Proszek do prania", CHEMIA, "opakowanie"),
    StarterProduct("Płyn do płukania tkanin", CHEMIA, "butelka"),
    StarterProduct("Płyn do mycia podłóg", CHEMIA, "butelka"),
    StarterProduct("Płyn do czyszczenia łazienki", CHEMIA, "butelka"),
    StarterProduct("Żel do WC", CHEMIA, "butelka"),
    StarterProduct("Płyn do szyb", CHEMIA, "butelka"),
    StarterProduct("Mleczko do czyszczenia", CHEMIA, "butelka"),
    StarterProduct("Gąbki do naczyń", CHEMIA, "opakowanie"),
    StarterProduct("Ściereczki z mikrofibry", CHEMIA, "opakowanie"),
    StarterProduct("Rękawice gumowe", CHEMIA, "para"),
    StarterProduct("Mydło w płynie", HIGIENA, "butelka"),
    StarterProduct("Żel pod prysznic", HIGIENA, "butelka"),
    StarterProduct("Szampon", HIGIENA, "butelka"),
    StarterProduct("Odżywka do włosów", HIGIENA, "butelka"),
    StarterProduct("Pasta do zębów", HIGIENA, "tubka"),
    StarterProduct("Szczoteczka do zębów", HIGIENA, "sztuka"),
    StarterProduct("Nić dentystyczna", HIGIENA, "opakowanie"),
    StarterProduct("Płyn do płukania ust", HIGIENA, "butelka"),
    StarterProduct("Dezodorant", HIGIENA, "sztuka"),
    StarterProduct("Krem do rąk", HIGIENA, "tubka"),
    StarterProduct("Balsam do ciała", HIGIENA, "butelka"),
    StarterProduct("Maszynki do golenia", HIGIENA, "opakowanie"),
    StarterProduct("Pianka do golenia", HIGIENA, "sztuka"),
    StarterProduct("Patyczki higieniczne", HIGIENA, "opakowanie"),
    StarterProduct("Płatki kosmetyczne", HIGIENA, "opakowanie"),
    StarterProduct("Podpaski", HIGIENA, "opakowanie"),
    StarterProduct("Chusteczki higieniczne", HIGIENA, "opakowanie"),
    StarterProduct("Chusteczki nawilżane", HIGIENA, "opakowanie"),
    StarterProduct("Paracetamol", APTECZKA, "opakowanie"),
    StarterProduct("Ibuprofen", APTECZKA, "opakowanie"),
    StarterProduct("Tabletki na ból gardła", APTECZKA, "opakowanie"),
    StarterProduct("Krople do nosa", APTECZKA, "butelka"),
    StarterProduct("Węgiel leczniczy", APTECZKA, "opakowanie"),
    StarterProduct("Elektrolity", APTECZKA, "opakowanie"),
    StarterProduct("Plastry", APTECZKA, "opakowanie"),
    StarterProduct("Bandaż", APTECZKA, "sztuka"),
    StarterProduct("Gaza jałowa", APTECZKA, "opakowanie"),
    StarterProduct("Środek do dezynfekcji ran", APTECZKA, "butelka"),
    StarterProduct("Żel na oparzenia", APTECZKA, "tubka"),
    StarterProduct("Karma mokra dla kota", ZWIERZETA, "puszka"),
    StarterProduct("Karma sucha dla kota", ZWIERZETA, "opakowanie"),
    StarterProduct("Żwirek dla kota", ZWIERZETA, "opakowanie"),
    StarterProduct("Karma mokra dla psa", ZWIERZETA, "puszka"),
    StarterProduct("Karma sucha dla psa", ZWIERZETA, "opakowanie"),
    StarterProduct("Woreczki na psie odchody", ZWIERZETA, "rolka"),
    StarterProduct("Papier toaletowy", DOM, "rolka"),
    StarterProduct("Ręczniki papierowe", DOM, "rolka"),
    StarterProduct("Serwetki", DOM, "opakowanie"),
    StarterProduct("Worki na śmieci", DOM, "rolka"),
    StarterProduct("Folia spożywcza", DOM, "rolka"),
    StarterProduct("Folia aluminiowa", DOM, "rolka"),
    StarterProduct("Papier do pieczenia", DOM, "rolka"),
    StarterProduct("Woreczki śniadaniowe", DOM, "opakowanie"),
    StarterProduct("Worki do odkurzacza", DOM, "opakowanie"),
    StarterProduct("Wkład filtrujący do dzbanka", DOM, "sztuka"),
    StarterProduct("Baterie AA", DOM, "opakowanie"),
    StarterProduct("Baterie AAA", DOM, "opakowanie"),
    StarterProduct("Żarówki", DOM, "sztuka"),
    StarterProduct("Zapałki", DOM, "opakowanie"),
]


def starter_drafts(
    categories: Sequence[Category], units: Sequence[Unit], taken_names: Iterable[str]
) -> list[ProductDraft]:
    """The Starter Catalog as drafts, in its order, without Minimum Stock: each whose name no Product (active or
    Archived) has taken and whose Category and Unit, matched by name, still exist."""
    category_ids = {name_key(category.name): category.id for category in categories}
    unit_ids = {name_key(unit.name): unit.id for unit in units}
    taken = {name_key(name) for name in taken_names}
    return [
        ProductDraft(
            product.name,
            category_ids[name_key(product.category)],
            unit_ids[name_key(product.unit)],
            parse_pack_size(product.pack_size),
            None,
            product.usual_shelf_life_days,
        )
        for product in STARTER_CATALOG
        if name_key(product.name) not in taken
        and name_key(product.category) in category_ids
        and name_key(product.unit) in unit_ids
    ]


def available_starter_drafts(engine: Engine) -> list[ProductDraft]:
    """starter_drafts for the database as it is now."""
    products = list_products(engine) + list_products(engine, archived=True)
    return starter_drafts(list_categories(engine), list_units(engine), (product.name for product in products))
