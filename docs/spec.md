# Home Stock: spec

A single-user Windows desktop app for keeping a fully manual record of what the household has at home, reminding the user what is Running Low and what is Expiring Soon or Expired. Terms are defined in `GLOSSARY.md`; decisions in `docs/adr/`.

## Model

- A **Product** has a unique name (case-insensitive, Archived Products included), one **Category**, one **Unit**, an optional **Pack Size**, an optional **Minimum Stock** and an optional **Usual Shelf Life** (a whole number of days, 1 to 3650).
- **Usual Shelf Life** ("zwykle ważne 7 dni") pre-fills a new Batch's Expiry Date with today plus that many days, in the Purchase dialog and for a new Product's first Batch; the date stays editable. A Product without one leaves the Expiry Date blank.
- **Pack Size** (e.g. 1 kg of sugar per opakowanie) is shown next to the Quantity ("2 opak. (2 kg)") but never counted: Quantity and Minimum Stock stay in Units (ADR-0001).
- A Product holds **Batches**: a whole-number Quantity and an optional Expiry Date each (ADR-0001). The Product's Quantity is their sum.
- **Running Low**: Quantity at or below Minimum Stock. No Minimum Stock means never Running Low (Expiry reminders still apply).
- **Running Out**: Days Left at or below the **Buffer** ("Zapas dni"), a whole number of days above zero set in Ustawienia, 7 by default. A Product without a Consumption Rate never Runs Out.
- The **Shopping List** holds the active Products Running Low or Running Out, by Category and name; each line says why: "poniżej minimum" or "wystarczy na ok. N dni" (a Product both Running Low and Out reads "poniżej minimum"). Start's "Do kupienia", "Kopiuj listę", "Drukuj" and Unpacking list the same Products.
- **Expiring Soon**: a Batch's Expiry Date is within its Category's Warning Window; **Expired**: the date has passed.

## Actions

- **Use** ("−1"): takes one Unit off the Batch with the nearest Expiry Date, Batches without one last. A Batch at 0 disappears; the Product stays at 0. The Product card's "Zużyj" Uses several Units at once in the same order, refusing more than the Product's Quantity; one "Cofnij" restores every Batch it touched.
- **Purchase**: a new Batch. From the Shopping List a dialog asks for the Quantity (suggested: Minimum Stock + 1 − current Quantity) and an optional Expiry Date.
- **Unpacking** ("Rozpakuj zakupy" on Lista zakupów): one dialog lists every Product on the Shopping List in its order, each with a tick, a Quantity (the suggested Purchase) and an Expiry Date (from the Usual Shelf Life, else blank). "Zapisz" validates every ticked row first, showing each error under its row and saving nothing while one remains; then it records a Purchase for every ticked row in one transaction. Unticked rows are ignored. One "Cofnij" removes exactly the Batches it created, all or none: when one is already gone, nothing changes and the toast says so. With an empty Shopping List the dialog says there is nothing to Unpack.
- **Discard**: removes a whole Batch.
- Editing a Batch's Quantity or Expiry Date by hand, on the Product's card.
- **Archive** a Product (hidden with its Batches) and restore it from Ustawienia.
- After a Use, Purchase, Discard or Archive a toast offers "Cofnij" for a few seconds. Undoing a Purchase removes the Batch it added; when that Batch is already gone (e.g. removed in another window), the toast says so and nothing changes.

## Stock History

- Every Use, Purchase (single or from Unpacking), Discard and **Correction** records a **Stock Event** with the Product, its kind, the signed change in Units and the date, in the same transaction as the change. A Product's first Batch, entered with the Product, is its starting stock, not a Purchase.
- A Discard records the Batch's Quantity and whether the Batch was Expired that day ("Wyrzucenie (przeterminowane)").
- A hand edit of a Batch's Quantity is a Correction by the difference; setting it to 0 removes the Batch as a Correction, not a Discard. Changing only the Expiry Date records nothing.
- A "Cofnij" removes exactly the Stock Events of the action it takes back.
- The history starts empty on the update that brings it; no past is made up. An Archived Product keeps its events.
- The Product card lists its latest Stock Events, newest first ("02.11.2026 · Zużycie · −2 szt.").
- **Consumption Rate** ("Tempo zużycia"): the Units Used in the last 90 days divided by the days from the later of (the Product's first Stock Event, 90 days ago) to today. No rate below 3 Uses in that window or below 14 days of history. Purchases, Discards and Corrections never count.
- **Days Left**: Quantity ÷ Consumption Rate, rounded down. Produkty and the Product card show "wystarczy na ok. N dni" for a Product with a rate, and nothing extra without one; a Product at 0 shows 0 days.

## Adding a Product

A form with name, Category, Unit, optional Pack Size, Minimum Stock (pre-filled with 1; clearing it leaves the Product without one), optional Usual Shelf Life and, optionally, a first Batch. A name that already exists offers to add a Batch to that Product instead; if it is archived, to restore it.

## Tabs

1. **Start**: Przeterminowane, Kończy się termin, Do kupienia; clicking a line opens that Product's card.
2. **Produkty**: grouped by Category, with search; each row shows Quantity, Unit, Days Left when there is a Consumption Rate and a "−1" button; clicking opens the Product's card with its Batches.
3. **Lista zakupów**: the Shopping List, each line with its reason; ticking a Product records a Purchase.
4. **Historia**: the latest 200 Stock Events of all Products, newest first, with a name filter.
5. **Ustawienia**: the Buffer, Categories with their Warning Windows, Units, the archive.

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
