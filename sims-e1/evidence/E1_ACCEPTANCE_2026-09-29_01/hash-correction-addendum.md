# Historical hash correction addendum

This addendum does not alter the blocked acceptance report or its raw JSONL.

The textual `acceptance.md` report contained an invalid 65-character artifact
SHA transcription ending in `...B8AA3E3`. The actual 1.0.0 artifact identity
must be established from a fresh local `Get-FileHash` result and the build
manifest.

Fresh local identity for the previously accepted 1.0.0 artifact:

`2B78CB40303A0228578BA1205FB6526A026F04B3F466B77A2EE4B4E40B8AA3E`
