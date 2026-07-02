# Nutrient quote template adapted from original DOCX

This folder keeps the original `stackaero-quote-studiojazzy.docx` layout, embedded fonts, text boxes, and artwork. The old template markers were rewritten to Nutrient Web SDK compatible placeholders.

- `stackaero-quote-template.docx` — original-based Nutrient DOCX template.
- `stackaero-quote-data.json` — flattened model passed to `populateDocumentTemplate()`.

The aircraft option pages are intentionally unrolled from the original repeating section. This avoids Nutrient/Word floating-object drift with page-break text boxes and anchored aircraft images. The app still uses Nutrient for template population and PDF conversion, then patches the preserved DOCX image anchors with base64 image bytes so browser CORS does not affect generation.

Nutrient placeholder names are intentionally simple (`letters`, `numbers`, `_`).
