/* Query activity: RE_ChurnRetention_Suppression (automation RE_ChurnRetention, step 2)
   Target DE: RE_ChurnRetention_History (Append). Records every entry so a contact is handled
   once per term and the 120-day re-contact rule can be enforced. Primary key: Id + TermEndAtEntry. */
SELECT
    e.Id,
    e.TermEndAtEntry,
    e.EntryDate,
    e.Band,
    e.Track,
    e.Score,
    e.TopFactors
FROM [RE_ChurnRetention_Entry] e
WHERE NOT EXISTS (
    SELECT 1 FROM [RE_ChurnRetention_History] h
    WHERE h.Id = e.Id AND h.TermEndAtEntry = e.TermEndAtEntry)
