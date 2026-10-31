# Home Stock

A single-user, fully manual record of what the household has at home, used to remind the user what is running out and what is about to expire.

## Stock

**Product**:
A kind of thing kept at home, such as "Mleko 2%" or "Papier toaletowy", counted in one Unit and belonging to one Category.
_Avoid_: Item, article, good

**Batch**:
One purchase of a Product: a whole-number Quantity and an optional Expiry Date.
_Avoid_: Lot, entry, purchase, stock item

**Unit**:
The countable piece a Product is counted in, such as sztuka, rolka or opakowanie; never a weight or volume.
_Avoid_: Measure, UOM

**Pack Size**:
An optional note of what one Unit of a Product holds, such as 1 kg or 500 ml; informative only, never what is counted.
_Avoid_: Weight, volume, capacity

**Quantity**:
A whole number of Units; a Product's Quantity is the sum of its Batches' Quantities.
_Avoid_: Amount, stock level, count

**Expiry Date**:
The best-before or use-by date printed on a Batch; Batches of things that do not go off have none.
_Avoid_: Shelf life, best-before, deadline

**Minimum Stock**:
The Quantity of a Product below which it counts as Running Low.
_Avoid_: Threshold, reorder point, alarm level

**Running Low**:
The state of a Product whose Quantity is at or below its Minimum Stock; a Product with no Minimum Stock is never Running Low.
_Avoid_: Low stock, shortage, ending

**Use**:
Recording that one Unit of a Product was used up, which takes it off the Batch with the nearest Expiry Date (Batches with none last).
_Avoid_: Consume, decrement, take

**Discard**:
Removing a whole Batch that went off or was thrown away, as opposed to Using it up.
_Avoid_: Delete, waste, write off

**Purchase**:
Adding a new Batch to a Product, typically from the Shopping List.
_Avoid_: Restock, buy, add stock

**Archived Product**:
A Product the user no longer keeps, hidden from every list with its Batches but restorable with its settings.
_Avoid_: Deleted product, inactive, hidden

**Category**:
A user-editable group of Products, such as Spożywcze or Chemia i środki czystości; every Product is in exactly one.
_Avoid_: Type, tag, group

## Reminders

**Warning Window**:
The number of days before an Expiry Date at which a Batch starts Expiring Soon; each Category has its own.
_Avoid_: Notice period, lead time, alert days

**Expiring Soon**:
The state of a Batch whose Expiry Date falls within its Product's Category's Warning Window.
_Avoid_: About to expire, near expiry

**Expired**:
The state of a Batch whose Expiry Date has passed.
_Avoid_: Out of date, spoiled

**Shopping List**:
The Products currently Running Low, derived from Minimum Stock rather than kept by hand.
_Avoid_: To-buy list, cart, order

## Data

**Backup**:
A copy of the database taken at every start before migrations run, of which the newest 30 are kept; restored by hand.
_Avoid_: Snapshot, export, dump
