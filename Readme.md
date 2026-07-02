# Stack Aero Quote Generation — Nutrient Migration

This project now uses [Nutrient Web SDK](https://www.nutrient.io/guides/web/llms.txt) to populate a DOCX quote template and convert it to PDF. The migration keeps the old Word layout instead of recreating it from scratch.

## Kept Assets

- `assets/stackaero-quote-studiojazzy.docx` — original old-generation DOCX template.
- `assets/stackaero-quote-outputresult.pdf` — original PDF target for visual comparison.
- `assets/stackaero-quotejson-sample.json` — original sample quote data.
- `assets/nutrient-quote-original-adapted/stackaero-quote-template.docx` — Nutrient-ready DOCX adapted from the original.
- `assets/nutrient-quote-original-adapted/stackaero-quote-data.json` — flattened Nutrient model.

## Main Structural Changes

- **Template fields:** Old expressions such as ``{{`stackng__Model__r`.Name}}`` are replaced with simple Nutrient placeholders like `{{quote_1_model_name}}`. Nutrient placeholder names should use letters, numbers, and underscores only.
- **Data shape:** Nested old-generation/Salesforce-style data is flattened before template population, so the DOCX does not need to evaluate expressions or object paths.
- **Option pages:** Aircraft option pages are unrolled into `quote_1_*`, `quote_2_*`, etc. This avoids layout drift from repeating Word sections that contain vertical rails, anchored images, text boxes, and page breaks.
- **Images:** Remote image URLs are converted to base64/data payloads to avoid browser CORS failures. The original DOCX image anchors are preserved and patched during generation.
- **Runtime flow:** `src/lib/generateQuote.js` calls `NutrientViewer.populateDocumentTemplate()`, applies small DOCX anchor/text-box fixes, then calls `NutrientViewer.convertToPDF()`.

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
