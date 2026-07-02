import templateUrl from "../../assets/nutrient-quote-original-adapted/stackaero-quote-template.docx?url";
import quoteData from "../../assets/nutrient-quote-original-adapted/stackaero-quote-data.json";
import JSZip from "jszip";
import { NUTRIENT_LICENSE_KEY } from "./nutrientLicense.js";

export { quoteData };

let cachedTemplateBuffer = null;

async function loadTemplateBuffer() {
  if (!cachedTemplateBuffer) {
    const response = await fetch(templateUrl);
    cachedTemplateBuffer = await response.arrayBuffer();
  }
  return cachedTemplateBuffer;
}

function imageBytesFromModel(image) {
  const base64 = image?.data;
  if (!base64) {
    throw new Error("Missing base64 image data in quote model.");
  }

  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function ensureJpgContentType(contentTypesXml) {
  if (contentTypesXml.includes('Extension="jpg"')) return contentTypesXml;
  return contentTypesXml.replace(
    "</Types>",
    '<Default Extension="jpg" ContentType="image/jpeg"/></Types>',
  );
}

function escapeXmlText(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function buildPlaceholderValues(data) {
  const values = new Map();
  Object.entries(data).forEach(([key, value]) => {
    if (typeof value === "string" || typeof value === "number") {
      values.set(key, value);
    }
  });
  data.quotes?.forEach((quote, index) => {
    Object.entries(quote).forEach(([key, value]) => {
      if (typeof value === "string" || typeof value === "number") {
        values.set(`quote_${index + 1}_${key}`, value);
      }
    });
  });
  return values;
}

function patchSimpleTextBoxPlaceholders(documentXml, data) {
  const values = buildPlaceholderValues(data);
  return documentXml.replace(/\{\{([A-Za-z0-9_]+)\}\}/g, (match, key) => {
    if (!values.has(key)) return match;
    return escapeXmlText(values.get(key));
  });
}

async function patchAnchoredQuoteImages(docxBuffer, data) {
  const zip = await JSZip.loadAsync(docxBuffer);
  const documentPath = "word/document.xml";
  const relsPath = "word/_rels/document.xml.rels";
  const contentTypesPath = "[Content_Types].xml";
  let documentXml = await zip.file(documentPath).async("string");
  let relsXml = await zip.file(relsPath).async("string");
  let contentTypesXml = await zip.file(contentTypesPath).async("string");
  const quoteIndexes = { exterior: 0, interior: 0 };
  let imageCounter = 0;

  documentXml = patchSimpleTextBoxPlaceholders(documentXml, data);
  documentXml = documentXml.replace(
    /<w:drawing[\s\S]*?<\/w:drawing>/g,
    (drawingXml) => {
      const isExterior = drawingXml.includes("stackng__ImageExterior__c");
      const isInterior = drawingXml.includes("stackng__ImageInterior__c");
      if (!isExterior && !isInterior) return drawingXml;

      const kind = isExterior ? "exterior" : "interior";
      const quote = data.quotes?.[quoteIndexes[kind]];
      quoteIndexes[kind] += 1;
      const image = quote?.[`${kind}_image`];
      if (!image) return drawingXml;

      imageCounter += 1;
      const relationshipId = `rIdNutrientQuoteImage${imageCounter}`;
      const mediaPath = `media/nutrient-quote-image-${imageCounter}.jpg`;
      zip.file(`word/${mediaPath}`, imageBytesFromModel(image));
      relsXml = relsXml.replace(
        "</Relationships>",
        `<Relationship Id="${relationshipId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="${mediaPath}"/></Relationships>`,
      );

      let patchedDrawingXml = drawingXml
        .replace(
          /(<[^:>\s]+:anchor\b[^>]*\bbehindDoc=")1("[^>]*>)/,
          (_, start, end) => `${start}0${end}`,
        )
        .replace(
          /(<[^:>\s]+:anchor\b[^>]*\ballowOverlap=")0("[^>]*>)/,
          (_, start, end) => `${start}1${end}`,
        );
      if (kind === "interior") {
        patchedDrawingXml = patchedDrawingXml.replace(
          /(<[^:>\s]+:positionV\b[^>]*\brelativeFrom=")page("[^>]*>)/,
          (_, start, end) => `${start}margin${end}`,
        ).replace(
          /(<[^:>\s]+:positionV\b[^>]*\brelativeFrom="margin"[^>]*>\s*<[^:>\s]+:posOffset>)[^<]+(<\/[^:>\s]+:posOffset>)/,
          (_, start, end) => `${start}4400000${end}`,
        );
      }

      return patchedDrawingXml
        .replace(
          /(<[^:>\s]+:blip\b[^>]*\b(?:r|ns\d+):embed=")[^"]+("[^>]*>)/,
          `$1${relationshipId}$2`,
        );
    },
  );

  contentTypesXml = ensureJpgContentType(contentTypesXml);
  zip.file(documentPath, documentXml);
  zip.file(relsPath, relsXml);
  zip.file(contentTypesPath, contentTypesXml);

  return zip.generateAsync({ type: "arraybuffer" });
}

export async function generateQuoteDocx(NutrientViewer, data = quoteData) {
  const template = await loadTemplateBuffer();
  const docxBuffer = await NutrientViewer.populateDocumentTemplate(
    { document: template, useCDN: true, licenseKey: NUTRIENT_LICENSE_KEY },
    {
      config: { delimiter: { start: "{{", end: "}}" } },
      model: data,
    },
  );
  return patchAnchoredQuoteImages(docxBuffer, data);
}

export async function generateQuotePdf(NutrientViewer, data = quoteData) {
  const docxBuffer = await generateQuoteDocx(NutrientViewer, data);
  const pdfBuffer = await NutrientViewer.convertToPDF({
    document: docxBuffer,
    useCDN: true,
    licenseKey: NUTRIENT_LICENSE_KEY,
  });
  return { docxBuffer, pdfBuffer };
}

export function downloadBuffer(buffer, filename, mimeType) {
  const blob = new Blob([buffer], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
