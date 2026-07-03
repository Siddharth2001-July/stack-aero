# Nutrient quote template adapted from original DOCX

This folder keeps the original `stackaero-quote-studiojazzy.docx` layout and rewrites the old markers to Nutrient Web SDK template syntax.

- `stackaero-quote-template.docx` — original-based Nutrient DOCX template using direct nested loops over `stackng__Segments__r` and `stackng__FlightQuotes__r`.
- `stackaero-quote-data.json` — nested quote data in the old payload shape, with small `nutrient__*` helpers for formatted dates and base64 image payloads.

The app passes this JSON directly to `populateDocumentTemplate()`. A small post-population patch preserves legacy Word table rows and anchored aircraft image frames that live outside normal Nutrient template text.
