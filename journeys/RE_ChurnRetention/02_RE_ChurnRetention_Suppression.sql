/* Query activity: RE_ChurnRetention_Suppression (automation RE_ChurnRetention, step 2)
   Target DE: RE_ChurnRetention_History_AF_10202026 (Append). Records every entry so a contact is handled
   once per term. RatingVersion added in v2 (2026-10-21) so results split legacy vs TDLI. Primary key: Id + TermEndAtEntry. */
SELECT
    e.Id,
    e.TermEndAtEntry,
    e.EntryDate,
    e.Band,
    e.Track,
    e.Score,
    e.Arm,
    e.RatingVersion
FROM [RE_ChurnRetention_Entry_AF_10202026] e
WHERE NOT EXISTS (
    SELECT 1 FROM [RE_ChurnRetention_History_AF_10202026] h
    WHERE h.Id = e.Id AND h.TermEndAtEntry = e.TermEndAtEntry)
