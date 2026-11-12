# Home Stock: spec

A single-user Android app for keeping a fully manual record of what the household has at home, reminding the user what is Running Low and what is Expiring Soon or Expired. Terms are defined in `GLOSSARY.md`; decisions in `docs/adr/`.

## Model

- A **Product** has a unique name (case-insensitive, Archived Products included), one **Category**, one **Unit**, an optional **Pack Size**, an optional **Minimum Stock** and an optional **Usual Shelf Life** (a whole number of days, 1 to 3650).
- **Usual Shelf Life** ("zwykle ważne 7 dni") pre-fills a new Batch's Expiry Date with today plus that many days, in the Purchase dialog and for a new Product's first Batch; the date stays editable. A Product without one leaves the Expiry Date blank.
- **Pack Size** (e.g. 1 kg of sugar per opakowanie) is shown next to the Quantity ("2 opak. (2 kg)") but never counted: Quantity and Minimum Stock stay in Units (ADR-0001).
- A Product holds **Batches**: a whole-number Quantity and an optional Expiry Date each (ADR-0001). The Product's Quantity is their sum.
- **Running Low**: Quantity at or below Minimum Stock. No Minimum Stock means never Running Low (Expiry reminders still apply).
- **Running Out**: Days Left at or below the **Buffer** ("Zapas dni"), a whole number of days above zero set in Ustawienia, 7 by default. A Product without a Consumption Rate never Runs Out.
- The **Shopping List** holds the active Products Running Low or Running Out, by Category and name; each line says why: "poniżej minimum" or "wystarczy na ok. N dni" (a Product both Running Low and Out reads "poniżej minimum"). Start's "Do kupienia", "Kopiuj listę", "Udostępnij" and Unpacking list the same Products.
- **Expiring Soon**: a Batch's Expiry Date is within its Category's Warning Window; **Expired**: the date has passed.

## Actions

- **Use** ("−1"): takes one Unit off the Batch with the nearest Expiry Date, Batches without one last. A Batch at 0 disappears; the Product stays at 0. The Product card's "Zużyj" Uses several Units at once in the same order, refusing more than the Product's Quantity; one "Cofnij" restores every Batch it touched.
- **Purchase**: a new Batch. From the Shopping List a dialog asks for the Quantity and an optional Expiry Date. The suggested Quantity, the same on the Shopping List, in this dialog and in Unpacking, is at least 1: for a Product with a Consumption Rate, Minimum Stock (0 without one) + the Suggested Minimum Stock − current Quantity, so the Buffer is covered above Minimum Stock, and more if needed for Days Left to pass the Buffer, so buying it takes the Product off the Shopping List; without a rate, Minimum Stock + 1 − current Quantity.
- **Unpacking** ("Rozpakuj zakupy" on Zakupy): one dialog lists every Product on the Shopping List in its order, each with a tick, a Quantity (the suggested Purchase) and an Expiry Date (from the Usual Shelf Life, else blank). "Zapisz" validates every ticked row first, showing each error under its row and saving nothing while one remains; then it records a Purchase for every ticked row in one transaction. Unticked rows are ignored. One "Cofnij" removes exactly the Batches it created, all or none: when one is already gone, nothing changes and the toast says so. With an empty Shopping List the dialog says there is nothing to Unpack.
- **Discard**: removes a whole Batch.
- Editing a Batch's Quantity or Expiry Date by hand, on the Product's card.
- **Archive** a Product (hidden with its Batches) and restore it from Ustawienia.
- After a Use, Purchase, Discard or Archive a toast offers "Cofnij" for a few seconds. Undoing a Purchase removes the Batch it added; when that Batch is already gone (e.g. removed meanwhile), the toast says so and nothing changes.

## Custom Lists

A **Custom List** ("Lista własna") is kept by hand for an occasion, beside the Shopping List, which it never changes (ADR-0006).

- A Custom List has a name (not blank; spaces trimmed) and an optional date of the occasion. Zakupy shows a chip per list after "Brakuje" (the Shopping List, selected by default), by date, undated ones last, then by name: "Kolacja · 15.11", or the name alone. "Nowa lista" opens a form with Nazwa and an optional Data; saving selects the new list, and "Cofnij" removes it while it has no List Lines.
- A **List Line** ("Pozycja") is a Product with a Quantity (a whole number, at least 1) or free text (not blank) for something not kept as stock. "Dopisz" adds one: a Product picked by name with a Quantity, or text that names no Product as free text (a Quantity above 1 goes into its text: "wino × 3"). Adding a Product already on the list adds the Quantity to its line instead of a second one. "Cofnij" takes back the line, or the Quantity added.
- Lines show in the order added: a Product line with its Quantity in its Unit ("kup 2 szt."), followed by "(w archiwum)" for an Archived Product; a free-text line as written. An empty list reads "Lista jest pusta."
- Under each Product line to buy, and in "Dopisz" for the Product picked or typed, the app says how much of it is at home: "w domu: 1 szt.", or "w domu: brak". When its nearest Batch is Expiring Soon or Expired, the date follows ("· ważne do 14.11"); when the list has a date and every Batch is Expired by then, "· przed okazją" (a Batch without an Expiry Date always lasts).
- A Product is not removed (the undo of adding it) while a List Line names it.
- A Custom List opens with its name and date ("Kolacja · 15.11.2026") and a menu: "Edytuj listę" (the same form, filled in) and "Usuń listę", which removes it with every line and shows Brakuje; "Cofnij" brings it back as it was, shown again.
- Ticking a line ("Kupione") marks it bought: a free-text line at once, a Product line through the Purchase dialog with the line's Quantity filled in, recording the Purchase and the tick in one transaction (cancelling leaves the line to buy). One "Cofnij" takes back both.
- Bought lines go under "Kupione", crossed out, in the order added, without a tick; when no line is left to buy, the list reads "Wszystko kupione." A line's menu offers "Zmień ilość" (a Product line) or "Zmień tekst" (a free-text line), and "Usuń"; a bought line has "Usuń" only. Each has "Cofnij".
- "Kopiuj listę" and "Udostępnij" on a Custom List, shown while a line is left to buy, copy ("Skopiowano listę: Kolacja") or share it as text: its name and date on the first line ("Kolacja w sobotę · 15.11.2026"), then its lines to buy in the order added, a Product line as name and Quantity in its Unit ("Śmietana 30% — 2 szt."), a free-text line as written.
- "Rozpakuj zakupy" on a Custom List opens Unpacking with a row per Product line to buy of an active Product, by Category, each with the line's Quantity (a Product on two lines, as after a deleted line came back, gets one row with both Quantities, both lines bought with it) and an Expiry Date from the Usual Shelf Life; free-text lines and Archived Products' lines are left out, and "Dodaj produkt spoza listy" works as on Brakuje. "Zapisz" records the Purchases and marks the ticked rows' lines bought in one transaction, nothing when a line was deleted or bought meanwhile; one "Cofnij" removes the Batches and unmarks the lines, all or none.

## Stock History

- Every Use, Purchase (single or from Unpacking), Discard and **Correction** records a **Stock Event** with the Product, its kind, the signed change in Units and the date, in the same transaction as the change. A Product's first Batch, entered with the Product, is its starting stock, not a Purchase.
- A Discard records the Batch's Quantity and whether the Batch was Expired that day ("Wyrzucenie (przeterminowane)").
- A hand edit of a Batch's Quantity is a Correction by the difference; setting it to 0 removes the Batch as a Correction, not a Discard. Changing only the Expiry Date records nothing.
- A "Cofnij" removes exactly the Stock Events of the action it takes back.
- The history starts empty on the update that brings it; no past is made up. An Archived Product keeps its events.
- The Product card lists its latest Stock Events, newest first ("02.11.2026 · Zużycie · −2 szt.").
- **Consumption Rate** ("Tempo zużycia"): the Units Used in the last 90 days divided by the days from the later of (the Product's first Stock Event, 90 days ago) to today. No rate below 3 Uses in that window or below 14 days of history. Purchases, Discards and Corrections never count.
- **Days Left**: Quantity ÷ Consumption Rate, rounded down. Produkty and the Product card show "wystarczy na ok. N dni" for a Product with a rate, and nothing extra without one; a Product at 0 shows 0 days.
- **Suggested Minimum Stock**: Consumption Rate × Buffer, rounded up, at least 1. The Product card shows "Sugerowany stan minimalny: N" only when it differs from the current Minimum Stock; "Zastosuj" sets it in one click, and "Cofnij" puts the old Minimum Stock back.
- **Waste** ("Marnowanie"): the Units each Product had Discarded in the last 30 and the last 90 days (the days counted end today, as for the Consumption Rate), most first, each line saying how many were Expired ("3 szt. (przeterminowane: 2)"). Uses, Purchases and Corrections never count. A period without Discards reads "Nic nie wyrzucono."

## Adding a Product

A form with name, Category, Unit, optional Pack Size, Minimum Stock (pre-filled with 1; clearing it leaves the Product without one), optional Usual Shelf Life and, optionally, a first Batch. A name that already exists offers to add a Batch to that Product instead; if it is archived, to restore it.

The **Starter Catalog** ("Dodaj typowe produkty" in Ustawienia, and in Produkty while it is empty) adds many Products at once: a dialog lists about a hundred a small household keeps, by Category, each ticked, with its Unit, Pack Size and Usual Shelf Life where it has them; a Category's own tick ticks or unticks all its Products. A name already taken (active or Archived) is left out, and so is a Product whose Category or Unit, matched by name, no longer exists. "Zapisz" adds the ticked ones in one transaction without Minimum Stock or Batches, so none lands on the Shopping List. One "Cofnij" removes them all, or none when one has a Batch or a Stock Event by then.

## Tabs

1. **Start**: Przeterminowane, Kończy się termin, Do kupienia; clicking a line opens that Product's card.
2. **Produkty**: grouped by Category, with search; each row shows Quantity, Unit, Days Left when there is a Consumption Rate and a "−1" button; clicking opens the Product's card with its Batches.
3. **Zakupy**: the Shopping List ("Brakuje"), each line with its reason; ticking a Product records a Purchase. It also holds the Custom Lists.
4. **Historia**: Waste over the last 30 and 90 days, then the latest 200 Stock Events of all Products, newest first, with a name filter (which leaves Waste as it is).
5. **Ustawienia**: the Buffer, Categories with their Warning Windows, Units, the Starter Catalog, the archive.

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

`src/android_main.py --demo` runs the app on a fresh made-up database in TEMP.
