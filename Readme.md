# Stack Aero Quote Generation — Nutrient Migration

This project uses [Nutrient Web SDK](https://www.nutrient.io/guides/web/llms.txt) to populate the existing DOCX quote template and convert it to PDF. The sample is intentionally close to the old payload and template structure so the migration path is easy to see.

## Kept Assets

- `assets/stackaero-quote-studiojazzy.docx` — original old-generation DOCX template.
- `assets/stackaero-quote-outputresult.pdf` — original PDF target for visual comparison.
- `assets/stackaero-quotejson-sample.json` — original sample quote data.
- `assets/nutrient-quote-original-adapted/stackaero-quote-template.docx` — original DOCX rewritten with Nutrient template markers.
- `assets/nutrient-quote-original-adapted/stackaero-quote-data.json` — nested old-style quote data, with small `nutrient__*` helpers for formatted dates and base64 image payloads.

## Main Structural Changes

- **Template syntax:** Old markers are rewritten to Nutrient placeholders, loops, inverse sections, and object paths such as `{{stackng__Model__r.Name}}`.
- **Nested data:** The app passes `stackaero-quote-data.json` directly as the Nutrient `model`; there is no runtime quote-model adapter.
- **Repeating sections:** `stackng__Segments__r` and `stackng__FlightQuotes__r` stay as arrays and are rendered with `{{#...}}` / `{{/...}}` loops in the DOCX.
- **Legacy Word objects:** The original template keeps a few table-row/image placeholders outside normal Nutrient text flow. `src/lib/generateQuote.js` patches those preserved Word structures after Nutrient population.
- **Option headings:** Aircraft model names are shown in the option heading and preserved in the original vertical model rail.
- **Images:** Remote aircraft URLs are represented as base64 image payloads to avoid browser CORS failures while keeping the original anchored image frames.
- **Runtime flow:** `src/lib/generateQuote.js` loads the DOCX, calls `populateDocumentTemplate()`, applies the legacy Word-object patch, then converts to PDF.

## Nutrient References

- [Word template PDF generation](https://www.nutrient.io/guides/web/pdf-generation/from-word-template/) — placeholders, loops, images, and DOCX-to-PDF flow.
- [`NutrientViewer.populateDocumentTemplate`](https://www.nutrient.io/api/web/modules/NutrientViewer.html#.populateDocumentTemplate) — API reference for DOCX population.
- [React + Vite setup](https://www.nutrient.io/sdk/web/getting-started/react-vite/) — Web SDK setup for this app style.
- [Web SDK guide index](https://www.nutrient.io/guides/web/llms.txt) — official Nutrient Web SDK documentation index.

## Local Commands

```bash
npm install
cp .env.example .env.local
npm run dev
```
