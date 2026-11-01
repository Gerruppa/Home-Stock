# Home Stock: spec

A single-user Windows desktop app for keeping a fully manual record of what the household has at home, reminding the user what is Running Low and what is Expiring Soon or Expired. Terms are defined in `GLOSSARY.md`; decisions in `docs/adr/`.

## Model

- A **Product** has a unique name (case-insensitive, Archived Products included), one **Category**, one **Unit**, an optional **Pack Size**, an optional **Minimum Stock** and an optional **Usual Shelf Life** (a whole number of days, 1 to 3650).
- **Usual Shelf Life** ("zwykle ważne 7 dni") pre-fills a new Batch's Expiry Date with today plus that many days, in the Purchase dialog and for a new Product's first Batch; the date stays editable. A Product without one leaves the Expiry Date blank.
- **Pack Size** (e.g. 1 kg of sugar per opakowanie) is shown next to the Quantity ("2 opak. (2 kg)") but never counted: Quantity and Minimum Stock stay in Units (ADR-0001).
- A Product holds **Batches**: a whole-number Quantity and an optional Expiry Date each (ADR-0001). The Product's Quantity is their sum.
- **Running Low**: Quantity at or below Minimum Stock. No Minimum Stock means never Running Low (Expiry reminders still apply).
- **Expiring Soon**: a Batch's Expiry Date is within its Category's Warning Window; **Expired**: the date has passed.

## Actions

- **Use** ("−1"): takes one Unit off the Batch with the nearest Expiry Date, Batches without one last. A Batch at 0 disappears; the Product stays at 0. The Product card's "Zużyj" Uses several Units at once in the same order, refusing more than the Product's Quantity; one "Cofnij" restores every Batch it touched.
- **Purchase**: a new Batch. From the Shopping List a dialog asks for the Quantity (suggested: Minimum Stock + 1 − current Quantity) and an optional Expiry Date.
- **Discard**: removes a whole Batch.
- Editing a Batch's Quantity or Expiry Date by hand, on the Product's card.
- **Archive** a Product (hidden with its Batches) and restore it from Ustawienia.
- After a Use, Purchase, Discard or Archive a toast offers "Cofnij" for a few seconds; there is no history log. Undoing a Purchase removes the Batch it added; when that Batch is already gone (e.g. removed in another window), the toast says so and nothing changes.

## Adding a Product

A form with name, Category, Unit, optional Pack Size, Minimum Stock (pre-filled with 1; clearing it leaves the Product without one), optional Usual Shelf Life and, optionally, a first Batch. A name that already exists offers to add a Batch to that Product instead; if it is archived, to restore it.

## Tabs

1. **Start**: Przeterminowane, Kończy się termin, Do kupienia; clicking a line opens that Product's card.
2. **Produkty**: grouped by Category, with search; each row shows Quantity, Unit and a "−1" button; clicking opens the Product's card with its Batches.
3. **Lista zakupów**: the Shopping List, derived from Minimum Stock; ticking a Product records a Purchase.
4. **Ustawienia**: Categories with their Warning Windows, Units, the archive.

Reminders appear only in the app (ADR-0002).

## Initial data

The first run creates Categories and Units only, no Products. Categories and Units can be added and renamed; only unused ones can be deleted.

| Category | Warning Window (days) |
|---|---|
| Spożywcze | 3 |
| Napoje | 7 |
| Chemia i środki czystości | 30 |
| Higiena i kosmetyki | 30 |
| Apteczka | 30 |
| Zwierzęta | 7 |
| Dom i inne | 30 |

Units: sztuka, opakowanie, rolka, butelka, puszka, tubka, słoik, para.

`--demo` runs the app in the browser on a fresh made-up database in TEMP.
