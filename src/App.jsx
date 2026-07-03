import { useEffect, useRef, useState } from "react";
import Viewer from "./components/Viewer.jsx";
import {
  generateQuoteDocx,
  generateQuotePdf,
  downloadBuffer,
  quoteData,
} from "./lib/generateQuote.js";
import "./App.css";

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export default function App() {
  const nutrientRef = useRef(null);
  const [sdkReady, setSdkReady] = useState(false);
  const [pdfDocument, setPdfDocument] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const tripName = quoteData.stackng__TripName_formula__c;

  useEffect(() => {
    let cancelled = false;
    import("@nutrient-sdk/viewer").then(({ default: NutrientViewer }) => {
      if (cancelled) return;
      nutrientRef.current = NutrientViewer;
      setSdkReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleDownloadDocx() {
    if (!nutrientRef.current) return;
    setBusy(true);
    setError(null);
    setStatus("Populating DOCX template…");
    try {
      const buffer = await generateQuoteDocx(nutrientRef.current);
      downloadBuffer(buffer, `${tripName}.docx`, DOCX_MIME);
      setStatus("DOCX downloaded.");
    } catch (err) {
      console.error(err);
      setError(err.message ?? String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreviewPdf() {
    if (!nutrientRef.current) return;
    setBusy(true);
    setError(null);
    setStatus("Generating DOCX and converting to PDF…");
    try {
      const { pdfBuffer } = await generateQuotePdf(nutrientRef.current);
      setPdfDocument(pdfBuffer);
      setStatus("Preview ready.");
    } catch (err) {
      console.error(err);
      setError(err.message ?? String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>StackAero Quote Generator</h1>
        <p className="app__subtitle">
          Powered by Nutrient Web SDK &mdash; populates{" "}
          <code>stackaero-quote-template.docx</code> with{" "}
          <code>stackaero-quote-data.json</code>
        </p>
      </header>

      <div className="app__body">
        <aside className="app__sidebar">
          <h2>{tripName}</h2>
          <p className="app__meta">
            Trip #{quoteData.stackng__TripNumber__c} &middot;{" "}
            {quoteData.stackng__RouteCityNames__c}
          </p>

          <button
            id="generate-preview"
            disabled={busy || !sdkReady}
            onClick={handlePreviewPdf}
          >
            Generate &amp; Preview PDF
          </button>
          <button
            id="download-docx"
            disabled={busy || !sdkReady}
            onClick={handleDownloadDocx}
          >
            Download DOCX
          </button>

          {!sdkReady && <p className="app__status">Loading Nutrient SDK…</p>}
          {status && <p className="app__status">{status}</p>}
          {error && <p className="app__error">Error: {error}</p>}
        </aside>

        <main className="app__viewer">
          {pdfDocument ? (
            <Viewer document={pdfDocument} />
          ) : (
            <div className="app__placeholder">
              Click &ldquo;Generate &amp; Preview PDF&rdquo; to render the
              quote.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
