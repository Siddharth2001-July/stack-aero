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
  return cachedTemplateBuffer.slice(0);
}

function imageBytesFromModel(image) {
  const base64 = image?.data;
  if (!base64) {
    throw new Error("Missing base64 image data in quote data.");
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

function stringValue(value, fallback = "") {
  return value == null || value === "" ? fallback : String(value);
}

function replaceMarkers(xml, values) {
  return xml.replace(/\[\[([a-z_]+)\]\]/g, (match, key) => {
    if (!(key in values)) return match;
    return escapeXmlText(values[key]);
  });
}

function expandRows(documentXml, marker, items, valuesForItem) {
  return documentXml.replace(/<w:tr\b[\s\S]*?<\/w:tr>/g, (rowXml) => {
    if (!rowXml.includes(marker)) return rowXml;
    return items.map((item) => replaceMarkers(rowXml, valuesForItem(item))).join("");
  });
}

function segmentValues(segment) {
  return {
    segment_date: `${stringValue(segment.stackng__DepartDay__c)} ${stringValue(
      segment.stackng__DepartDateLocal_text__c,
    )}`.trim(),
    segment_depart_time: segment.stackng__DepartTimeTBC__c
      ? "--:--"
      : stringValue(segment.stackng__DepartTimeLocal__c),
    segment_from_route: `${stringValue(segment.stackng__FromCity__c)} - ${stringValue(
      segment.stackng__FromCodes__c,
    )}`,
    segment_from_airport: stringValue(
      segment.stackng__From__r?.stackng__LocalName__c,
    ),
    segment_arrive_time: segment.stackng__ArriveTimeTBC__c
      ? "--:--"
      : stringValue(segment.stackng__ArriveTimeLocal__c),
    segment_to_route: `${stringValue(segment.stackng__ToCity__c)} - ${stringValue(
      segment.stackng__ToCodes__c,
    )}`,
    segment_to_airport: stringValue(segment.stackng__To__r?.stackng__LocalName__c),
    segment_flight_time: stringValue(segment.stackng__EBT_formula__c),
  };
}

function quoteValues(quote) {
  return {
    quote_index: stringValue(quote.indexString ?? quote.index),
    quote_model_name: stringValue(quote.stackng__Model__r?.Name),
    quote_model_category: stringValue(
      quote.stackng__Model__r?.stackng__Category__c,
      "Category TBC",
    ),
    quote_seats: stringValue(quote.stackng__Seats__c),
    quote_price: stringValue(quote.stackng__GrossPrice_SellCurrText__c),
  };
}

function quotePageSpecValues(quote) {
  const cabinDimensions = stringValue(
    quote.stackng__CabinDimensions__c,
    "To be confirmed",
  );
  const seatConfig = stringValue(quote.stackng__SeatConfig__c);
  return {
    quote_page_baggage_capacity:
      stringValue(quote.stackng__BaggageSummary__c) || "\u00A0",
    quote_page_cabin_dimensions: `${cabinDimensions} ${seatConfig}`.trim(),
  };
}

function optionalLabel(quote, key, label) {
  return stringValue(quote[key]) ? label : "";
}

function optionalValue(quote, key) {
  return stringValue(quote[key]);
}

function quotePageValues(quote) {
  const specValues = quotePageSpecValues(quote);
  const safetyRatings = quote.stackng__Operator__r?.stackng__SafetyRatings__c;
  return {
    ...specValues,
    quote_page_vertical_model: stringValue(
      quote.stackng__Model__r?.Name,
      "Aircraft",
    ),
    quote_page_category_label: "Category",
    quote_page_category_value: stringValue(
      quote.stackng__Model__r?.stackng__Category__c,
      "Category TBC",
    ),
    quote_page_seating_label: "Seating",
    quote_page_seating_value: stringValue(quote.stackng__Seats__c),
    quote_page_year_of_make_label: optionalLabel(
      quote,
      "stackng__YOM__c",
      "Year of Make",
    ),
    quote_page_year_of_make_value: optionalValue(quote, "stackng__YOM__c"),
    quote_page_refurbished_value: stringValue(quote.stackng__YOR__c)
      ? `Refurbished in ${quote.stackng__YOR__c}`
      : "",
    quote_page_wifi_label: optionalLabel(quote, "stackng__WiFi__c", "Wi-Fi"),
    quote_page_wifi_value: optionalValue(quote, "stackng__WiFi__c"),
    quote_page_owner_approval_label: optionalLabel(
      quote,
      "stackng__OwnerApproval__c",
      "Owners Approval",
    ),
    quote_page_owner_approval_value: optionalValue(
      quote,
      "stackng__OwnerApproval__c",
    ),
    quote_page_catering_label: optionalLabel(
      quote,
      "stackng__CateringAvailable__c",
      "Catering",
    ),
    quote_page_catering_value: optionalValue(
      quote,
      "stackng__CateringAvailable__c",
    ),
    quote_page_cabin_crew_label: optionalLabel(
      quote,
      "stackng__CabinCrew__c",
      "Cabin Crew",
    ),
    quote_page_cabin_crew_value: optionalValue(quote, "stackng__CabinCrew__c"),
    quote_page_pets_label: optionalLabel(quote, "stackng__PetsAllowed__c", "Pets"),
    quote_page_pets_value: optionalValue(quote, "stackng__PetsAllowed__c"),
    quote_page_smoking_label: optionalLabel(
      quote,
      "stackng__Smoking__c",
      "Smoking",
    ),
    quote_page_smoking_value: optionalValue(quote, "stackng__Smoking__c"),
    quote_page_safety_ratings_label: stringValue(safetyRatings)
      ? "Safety Ratings"
      : "",
    quote_page_safety_ratings_value: stringValue(safetyRatings),
  };
}

function patchLegacyTableRows(documentXml, data) {
  let patchedXml = expandRows(
    documentXml,
    "[[segment_date]]",
    data.stackng__Segments__r ?? [],
    segmentValues,
  );
  patchedXml = expandRows(
    patchedXml,
    "[[quote_index]]",
    data.stackng__FlightQuotes__r ?? [],
    quoteValues,
  );
  return patchedXml;
}

function extractQuoteDetailRow(templateDocumentXml) {
  const tables = templateDocumentXml.match(/<w:tbl\b[\s\S]*?<\/w:tbl>/g) ?? [];
  const detailTable = tables.find((tableXml) =>
    tableXml.includes("[[quote_page_category_label]]"),
  );
  const detailRow = detailTable?.match(/<w:tr\b[\s\S]*?<\/w:tr>/)?.[0];
  if (!detailRow) {
    throw new Error("Could not find quote detail table row in template.");
  }
  return detailRow;
}

function patchEmptyQuoteDetailTables(documentXml, data, detailRowXml) {
  let detailTableIndex = 0;
  const quoteCount = data.stackng__FlightQuotes__r?.length ?? 0;
  return documentXml.replace(/<w:tbl\b[\s\S]*?<\/w:tbl>/g, (tableXml) => {
    if (detailTableIndex >= quoteCount || tableXml.includes("<w:tr")) {
      return tableXml;
    }

    detailTableIndex += 1;
    return tableXml.replace("</w:tbl>", `${detailRowXml}</w:tbl>`);
  });
}

function patchSequentialQuoteMarkers(documentXml, data) {
  const quotes = data.stackng__FlightQuotes__r ?? [];
  const markerIndexes = new Map();
  const parser = new DOMParser();
  const document = parser.parseFromString(documentXml, "application/xml");
  const textNamespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const paragraphs = Array.from(
    document.getElementsByTagNameNS(textNamespace, "p"),
  );

  for (const paragraph of paragraphs) {
    const nestedParagraph = Array.from(
      paragraph.getElementsByTagNameNS(textNamespace, "p"),
    ).some((child) => child !== paragraph);
    if (nestedParagraph) continue;

    const textNodes = Array.from(
      paragraph.getElementsByTagNameNS(textNamespace, "t"),
    );
    if (!textNodes.some((textNode) => textNode.textContent?.includes("[["))) {
      const paragraphText = textNodes
        .map((textNode) => textNode.textContent ?? "")
        .join("")
        .trim();
      if (
        textNodes.some((textNode) => textNode.textContent?.includes("{{")) ||
        paragraphText === "Inclusions" ||
        paragraphText === "Exclusions"
      ) {
        paragraph.parentNode?.removeChild(paragraph);
      }
      continue;
    }

    const originalParagraphText = textNodes
      .map((textNode) => textNode.textContent ?? "")
      .join("");
    let hasMarker = false;
    let hasNonEmptyReplacement = false;
    for (const textNode of textNodes) {
      textNode.textContent = textNode.textContent.replace(
        /\[\[(quote_page_[a-z_]+)\]\]/g,
        (match, key) => {
          hasMarker = true;
          const index = markerIndexes.get(key) ?? 0;
          markerIndexes.set(key, index + 1);
          const quote = quotes[Math.min(index, quotes.length - 1)];
          const values = quotePageValues(quote ?? {});
          const value = values[key] ?? "";
          if (value !== "") hasNonEmptyReplacement = true;
          return value;
        },
      );
    }

    const markerOnlyParagraph =
      originalParagraphText.trim().match(/^\[\[quote_page_[a-z_]+\]\]$/) !== null;
    if (hasMarker && markerOnlyParagraph && !hasNonEmptyReplacement) {
      paragraph.parentNode?.removeChild(paragraph);
    }
  }

  return new XMLSerializer().serializeToString(document);
}

async function patchAnchoredQuoteImages(docxBuffer, data, templateBuffer) {
  const zip = await JSZip.loadAsync(docxBuffer);
  const templateZip = await JSZip.loadAsync(templateBuffer);
  const documentPath = "word/document.xml";
  const relsPath = "word/_rels/document.xml.rels";
  const contentTypesPath = "[Content_Types].xml";
  let documentXml = await zip.file(documentPath).async("string");
  const templateDocumentXml = await templateZip.file(documentPath).async("string");
  let relsXml = await zip.file(relsPath).async("string");
  let contentTypesXml = await zip.file(contentTypesPath).async("string");
  const detailRowXml = extractQuoteDetailRow(templateDocumentXml);
  const quoteIndexes = { exterior: 0, interior: 0 };
  const quotes = data.stackng__FlightQuotes__r ?? [];
  let imageCounter = 0;

  documentXml = patchLegacyTableRows(documentXml, data);
  documentXml = patchEmptyQuoteDetailTables(documentXml, data, detailRowXml);
  documentXml = documentXml.replace(
    /<w:drawing[\s\S]*?<\/w:drawing>/g,
    (drawingXml) => {
      const isExterior = drawingXml.includes("stackng__ImageExterior__c");
      const isInterior = drawingXml.includes("stackng__ImageInterior__c");
      if (!isExterior && !isInterior) return drawingXml;

      const kind = isExterior ? "exterior" : "interior";
      const quote = quotes[quoteIndexes[kind]];
      quoteIndexes[kind] += 1;
      const image =
        kind === "exterior"
          ? quote?.nutrient__ImageExterior
          : quote?.nutrient__ImageInterior;
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
  documentXml = patchSequentialQuoteMarkers(documentXml, data);

  contentTypesXml = ensureJpgContentType(contentTypesXml);
  zip.file(documentPath, documentXml);
  zip.file(relsPath, relsXml);
  zip.file(contentTypesPath, contentTypesXml);

  return zip.generateAsync({ type: "arraybuffer" });
}

export async function generateQuoteDocx(NutrientViewer, data = quoteData) {
  const template = await loadTemplateBuffer();
  const templateForPatching = template.slice(0);
  const docxBuffer = await NutrientViewer.populateDocumentTemplate(
    { document: template, useCDN: true, licenseKey: NUTRIENT_LICENSE_KEY },
    {
      config: { delimiter: { start: "{{", end: "}}" } },
      model: data,
    },
  );
  return patchAnchoredQuoteImages(docxBuffer, data, templateForPatching);
}

export async function generateQuotePdf(NutrientViewer, data = quoteData) {
  const docxBuffer = await generateQuoteDocx(NutrientViewer, data);
  const pdfBuffer = await NutrientViewer.convertToPDF({
    document: docxBuffer.slice(0),
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
