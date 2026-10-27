# Products with Batches, counted in whole Units

A Product is a kind of thing; each Purchase adds a Batch with its own whole-number Quantity and optional Expiry Date. One record per Product with a single date breaks as soon as a new pack is bought before the old one is used up, so Batches are needed for expiry reminders. Quantities are whole Units (sztuka, rolka, opakowanie...), never grams or litres: a Use is a single "−1" click, which keeps fully manual tracking cheap enough to keep up, at the cost of not tracking part-used packs.

## Consequences

- Use takes from the Batch with the nearest Expiry Date (Batches without one last), so the user never picks a Batch by hand.
- A Batch whose Quantity reaches 0 disappears; the Product stays, at 0.
