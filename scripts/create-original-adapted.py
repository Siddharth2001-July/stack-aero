from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import json
from xml.etree import ElementTree as ET

SRC_DOCX = Path("assets/stackaero-quote-studiojazzy.docx")
SRC_DATA = Path("assets/stackaero-quotejson-sample.json")
OUT_DIR = Path("assets/nutrient-quote-original-adapted")
OUT_DOCX = OUT_DIR / "stackaero-quote-template.docx"
OUT_JSON = OUT_DIR / "stackaero-quote-data.json"

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("w", W)


def qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


W_P = qn(W, "p")
W_R = qn(W, "r")
W_T = qn(W, "t")
W_BODY = qn(W, "body")
W_PPR = qn(W, "pPr")
W_RPR = qn(W, "rPr")
W_PAGE_BREAK_BEFORE = qn(W, "pageBreakBefore")
W_DRAWING = qn(W, "drawing")


def para_text(paragraph: ET.Element) -> str:
    texts: list[str] = []
    for run in paragraph.findall(f"./{W_R}"):
        for text_node in run.findall(f"./{W_T}"):
            texts.append(text_node.text or "")
    return "".join(texts)


def first_rpr(paragraph: ET.Element) -> ET.Element | None:
    for run in paragraph.findall(f"./{W_R}"):
        rpr = run.find(f"./{W_RPR}")
        if rpr is not None:
            return deepcopy(rpr)
    return None


def set_para_text(paragraph: ET.Element, text: str) -> None:
    ppr = paragraph.find(f"./{W_PPR}")
    ppr_copy = deepcopy(ppr) if ppr is not None else None
    rpr_copy = first_rpr(paragraph)
    paragraph.clear()
    if ppr_copy is not None:
        paragraph.append(ppr_copy)
    run = ET.SubElement(paragraph, W_R)
    if rpr_copy is not None:
        run.append(rpr_copy)
    text_node = ET.SubElement(run, W_T)
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        text_node.set(qn(XML, "space"), "preserve")
    text_node.text = text


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def remove_element(parents: dict[ET.Element, ET.Element], element: ET.Element) -> None:
    parent = parents.get(element)
    if parent is not None:
        try:
            parent.remove(element)
        except ValueError:
            pass


def rewrite_remaining_quote_model_markers(root: ET.Element) -> None:
    source_marker = "{{stackng__Model__r.Name}}"
    for paragraph in root.iter(W_P):
        text_nodes = list(paragraph.iter(W_T))
        if "".join(text_node.text or "" for text_node in text_nodes) == source_marker * 2:
            text_nodes[0].text = "[[quote_page_vertical_model]]"
            for text_node in text_nodes[1:]:
                text_node.text = ""
            continue
        for text_node in text_nodes:
            if text_node.text == source_marker:
                text_node.text = "[[quote_page_vertical_model]]"


def split_vertical_rail_page_breaks(root: ET.Element) -> None:
    parents = parent_map(root)
    for paragraph in list(root.iter(W_P)):
        if not any(
            text_node.text == "[[quote_page_vertical_model]]"
            for text_node in paragraph.iter(W_T)
        ):
            continue
        if not any(True for _ in paragraph.iter(W_DRAWING)):
            continue

        ppr = paragraph.find(f"./{W_PPR}")
        page_break = ppr.find(f"./{W_PAGE_BREAK_BEFORE}") if ppr is not None else None
        if page_break is None:
            continue

        ppr.remove(page_break)
        parent = parents.get(paragraph)
        if parent is None:
            continue

        break_paragraph = ET.Element(W_P)
        break_ppr = ET.SubElement(break_paragraph, W_PPR)
        ET.SubElement(break_ppr, W_PAGE_BREAK_BEFORE)
        parent.insert(list(parent).index(paragraph), break_paragraph)


def format_trip_date_long(value: str) -> str:
    date = datetime.strptime(value, "%Y-%m-%d")
    return f"{date.strftime('%A')} {date.day:02d}-{MONTHS[date.month - 1]}-{date.year}"


def format_generated_on(value: str) -> str:
    date = datetime.strptime(value, "%d-%b-%Y %H:%M:%S %z").astimezone(timezone.utc)
    return f"{MONTHS[date.month - 1]} {date.day}, {date.year} {date.hour:02d}:{date.minute:02d}"


def read_model() -> dict:
    model = json.loads(SRC_DATA.read_text())
    existing = json.loads(OUT_JSON.read_text()) if OUT_JSON.exists() else {}
    existing_quotes = existing.get("stackng__FlightQuotes__r", [])

    model["never"] = False
    model["nutrient__TripDateLong__c"] = format_trip_date_long(
        model["stackng__StartDateLocal__c"],
    )
    model["nutrient__GeneratedOn__c"] = format_generated_on(model["CurrentDateTime"])

    for quote, existing_quote in zip(model.get("stackng__FlightQuotes__r", []), existing_quotes):
        quote["nutrient__TripNumber__c"] = model["stackng__TripNumber__c"]
        quote["nutrient__GeneratedOn__c"] = model["nutrient__GeneratedOn__c"]
        quote["nutrient__ImageExterior"] = existing_quote.get("nutrient__ImageExterior")
        quote["nutrient__ImageInterior"] = existing_quote.get("nutrient__ImageInterior")

    return model


INLINE_REPLACEMENTS = {
    "{{$fromMillis($toMillis(stackng__StartDateLocal__c, \"[Y0001]-[M01]-[D01]\"), \"[FNn] [D01]-[MNn]-[Y0001]\")}}": "{{nutrient__TripDateLong__c}}",
    "{% conditional-section expr(stackng__DepartTimeTBC__c = true) %}--:--{% end-section %}{% conditional-section expr(stackng__DepartTimeTBC__c = false) %}{{`stackng__DepartTimeLocal__c`}}{% end-section %}": "{{#stackng__DepartTimeTBC__c}}--:--{{/stackng__DepartTimeTBC__c}}{{^stackng__DepartTimeTBC__c}}{{stackng__DepartTimeLocal__c}}{{/stackng__DepartTimeTBC__c}}",
    "{% conditional-section expr(stackng__DepartTimeTBC__c = true) %}--:--{% end-section %}{% conditional-section expr(stackng__DepartTimeTBC__c = false) %}{{`stackng__ArriveTimeLocal__c`}}{% end-section %}": "{{#stackng__ArriveTimeTBC__c}}--:--{{/stackng__ArriveTimeTBC__c}}{{^stackng__ArriveTimeTBC__c}}{{stackng__ArriveTimeLocal__c}}{{/stackng__ArriveTimeTBC__c}}",
    "{{`stackng__FromCity__c`}}  - {{`stackng__FromCodes__c`}}": "{{stackng__FromCity__c}} - {{stackng__FromCodes__c}}",
    "{{`stackng__From__r`.`stackng__LocalName__c`}}": "{{stackng__From__r.stackng__LocalName__c}}",
    "{{`stackng__ToCity__c`}} - {{`stackng__ToCodes__c`}}": "{{stackng__ToCity__c}} - {{stackng__ToCodes__c}}",
    "{{`stackng__To__r`.`stackng__LocalName__c`}}": "{{stackng__To__r.stackng__LocalName__c}}",
    "{{`stackng__EBT_formula__c`}}": "{{stackng__EBT_formula__c}}",
    "Option – {{index}}": "Option – {{index}} / {{stackng__Model__r.Name}}",
    "Pricing based on {{ `stackng__PAXest__c`}} passengers": "Pricing based on {{stackng__PAXest__c}} passengers",
    "*Pricing based on {{`stackng__PAXest__c`}} passengers on each segment.": "*Pricing based on {{stackng__PAXest__c}} passengers on each segment.",
    "{{`stackng__Model__r`.Name}}{{`stackng__Model__r`.Name}}": "{{stackng__Model__r.Name}}",
    "{{`stackng__Model__r`.Name}}": "{{stackng__Model__r.Name}}",
    "({{`stackng__Model__r`.`stackng__Category__c`}})": "({{#stackng__Model__r.stackng__Category__c}}{{stackng__Model__r.stackng__Category__c}}{{/stackng__Model__r.stackng__Category__c}}{{^stackng__Model__r.stackng__Category__c}}Category TBC{{/stackng__Model__r.stackng__Category__c}})",
    "{{stackng__Model__r.stackng__Category__c:default-val(Category TBC)}}": "{{#stackng__Model__r.stackng__Category__c}}{{stackng__Model__r.stackng__Category__c}}{{/stackng__Model__r.stackng__Category__c}}{{^stackng__Model__r.stackng__Category__c}}Category TBC{{/stackng__Model__r.stackng__Category__c}}",
    "{{`stackng__Seats__c`}}": "{{stackng__Seats__c}}",
    "{{`stackng__BaggageSummary__c`:default-val(“To be confirmed”)}}": "{{#stackng__BaggageSummary__c}}{{stackng__BaggageSummary__c}}{{/stackng__BaggageSummary__c}}{{^stackng__BaggageSummary__c}}To be confirmed{{/stackng__BaggageSummary__c}}",
    "{{`stackng__CabinDimensions__c`:default-val(“To be confirmed”)}}  {{` stackng__SeatConfig__c`:default-val(“”)}}": "{{#stackng__CabinDimensions__c}}{{stackng__CabinDimensions__c}}{{/stackng__CabinDimensions__c}}{{^stackng__CabinDimensions__c}}To be confirmed{{/stackng__CabinDimensions__c}} {{stackng__SeatConfig__c}}",
    "{{`stackng__YOM__c`}}": "{{stackng__YOM__c}}",
    "Refurbished in {{`stackng__YOR__c`}}": "Refurbished in {{stackng__YOR__c}}",
    "{{stackng__WiFi__c}}": "{{stackng__WiFi__c}}",
    "{{`stackng__OwnerApproval__c`}}": "{{stackng__OwnerApproval__c}}",
    "{{`stackng__CateringAvailable__c`}}": "{{stackng__CateringAvailable__c}}",
    "{{`stackng__CabinCrew__c`}}": "{{stackng__CabinCrew__c}}",
    "{{`stackng__PetsAllowed__c`}}": "{{stackng__PetsAllowed__c}}",
    "{{`stackng__Smoking__c`}}": "{{stackng__Smoking__c}}",
    "{{`stackng__Operator__r`.stackng__SafetyRatings__c}}": "{{stackng__Operator__r.stackng__SafetyRatings__c}}",
}

SECTION_STARTS = {
    "{% repeating-section `stackng__FlightQuotes__r` %}": "stackng__FlightQuotes__r",
    "{% conditional-section expr($length(stackng__YOM__c) > 0) %}": "stackng__YOM__c",
    "{% conditional-section expr($length(stackng__YOR__c) > 0) %}": "stackng__YOR__c",
    "{% conditional-section expr($length(stackng__WiFi__c) > 0) %}": "stackng__WiFi__c",
    "{% conditional-section expr($length(stackng__OwnerApproval__c) > 0) %}": "stackng__OwnerApproval__c",
    "{% conditional-section expr($length(stackng__CateringAvailable__c) > 0) %}": "stackng__CateringAvailable__c",
    "{% conditional-section expr($length(stackng__CabinCrew__c) > 0) %}": "stackng__CabinCrew__c",
    "{% conditional-section expr($length(stackng__PetsAllowed__c) > 0) %}": "stackng__PetsAllowed__c",
    "{% conditional-section expr($length(stackng__Smoking__c) > 0) %}": "stackng__Smoking__c",
    "{% conditional-section expr($length(`stackng__Operator__r`.stackng__SafetyRatings__c) > 0) %}": "stackng__Operator__r.stackng__SafetyRatings__c",
    "{% conditional-section expr(stackng__renderInclusions__c = true) %}": "stackng__renderInclusions__c",
    "{% conditional-section expr(stackng__renderExclusions__c = true) %}": "stackng__renderExclusions__c",
    "{% conditional-section expr(true = false) %}": "never",
}

TABLE_STARTS = {
    "{% table-start `stackng__Segments__r` %}",
    "{% table-start stackng__FlightQuotes__r %}",
}

STRING_CONDITIONAL_SECTIONS = {
    "stackng__YOM__c",
    "stackng__YOR__c",
    "stackng__WiFi__c",
    "stackng__OwnerApproval__c",
    "stackng__CateringAvailable__c",
    "stackng__CabinCrew__c",
    "stackng__PetsAllowed__c",
    "stackng__Smoking__c",
    "stackng__Operator__r.stackng__SafetyRatings__c",
}

QUOTE_PAGE_REPLACEMENTS = {
    "Category": "[[quote_page_category_label]]",
    "{{stackng__Model__r.stackng__Category__c:default-val(Category TBC)}}": "[[quote_page_category_value]]",
    "Seating": "[[quote_page_seating_label]]",
    "{{`stackng__Seats__c`}}": "[[quote_page_seating_value]]",
    "Year of Make": "[[quote_page_year_of_make_label]]",
    "{{`stackng__YOM__c`}}": "[[quote_page_year_of_make_value]]",
    "Refurbished in {{`stackng__YOR__c`}}": "[[quote_page_refurbished_value]]",
    "Wi-Fi": "[[quote_page_wifi_label]]",
    "{{stackng__WiFi__c}}": "[[quote_page_wifi_value]]",
    "Owners Approval": "[[quote_page_owner_approval_label]]",
    "{{`stackng__OwnerApproval__c`}}": "[[quote_page_owner_approval_value]]",
    "Catering": "[[quote_page_catering_label]]",
    "{{`stackng__CateringAvailable__c`}}": "[[quote_page_catering_value]]",
    "Cabin Crew": "[[quote_page_cabin_crew_label]]",
    "{{`stackng__CabinCrew__c`}}": "[[quote_page_cabin_crew_value]]",
    "Pets": "[[quote_page_pets_label]]",
    "{{`stackng__PetsAllowed__c`}}": "[[quote_page_pets_value]]",
    "Smoking": "[[quote_page_smoking_label]]",
    "{{`stackng__Smoking__c`}}": "[[quote_page_smoking_value]]",
    "Safety Ratings": "[[quote_page_safety_ratings_label]]",
    "{{`stackng__Operator__r`.stackng__SafetyRatings__c}}": "[[quote_page_safety_ratings_value]]",
}


def in_quote_loop(stack: list[str]) -> bool:
    return "stackng__FlightQuotes__r" in stack


def patch_template() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        with ZipFile(SRC_DOCX) as source_docx:
            source_docx.extractall(tmp)

        doc_xml = tmp / "word" / "document.xml"
        tree = ET.parse(doc_xml)
        root = tree.getroot()
        body = root.find(f".//{W_BODY}")
        if body is None:
            raise RuntimeError("document body not found")

        parents = parent_map(root)
        stack: list[str] = []
        summary_option_done = False
        summary_model_done = False
        summary_category_done = False
        summary_seats_done = False
        summary_price_done = False
        for paragraph in list(root.iter(W_P)):
            text = para_text(paragraph)
            if not text:
                continue

            if text in TABLE_STARTS or text == "{% table-end %}":
                remove_element(parents, paragraph)
                continue

            if text == "{{stackng__DepartDay__c}} {{stackng__DepartDateLocal_text__c}}":
                set_para_text(paragraph, "[[segment_date]]")
                continue

            if text == "{% conditional-section expr(stackng__DepartTimeTBC__c = true) %}--:--{% end-section %}{% conditional-section expr(stackng__DepartTimeTBC__c = false) %}{{`stackng__DepartTimeLocal__c`}}{% end-section %}":
                set_para_text(paragraph, "[[segment_depart_time]]")
                continue

            if text == "{{`stackng__FromCity__c`}}  - {{`stackng__FromCodes__c`}}":
                set_para_text(paragraph, "[[segment_from_route]]")
                continue

            if text == "{{`stackng__From__r`.`stackng__LocalName__c`}}":
                set_para_text(paragraph, "[[segment_from_airport]]")
                continue

            if text == "{% conditional-section expr(stackng__DepartTimeTBC__c = true) %}--:--{% end-section %}{% conditional-section expr(stackng__DepartTimeTBC__c = false) %}{{`stackng__ArriveTimeLocal__c`}}{% end-section %}":
                set_para_text(paragraph, "[[segment_arrive_time]]")
                continue

            if text == "{{`stackng__ToCity__c`}} - {{`stackng__ToCodes__c`}}":
                set_para_text(paragraph, "[[segment_to_route]]")
                continue

            if text == "{{`stackng__To__r`.`stackng__LocalName__c`}}":
                set_para_text(paragraph, "[[segment_to_airport]]")
                continue

            if text == "{{`stackng__EBT_formula__c`}}":
                set_para_text(paragraph, "[[segment_flight_time]]")
                continue

            if text == "{{index}}" and not summary_option_done:
                set_para_text(paragraph, "[[quote_index]]")
                summary_option_done = True
                continue

            if text == "{{`stackng__Model__r`.Name}}" and not stack and not summary_model_done:
                set_para_text(paragraph, "[[quote_model_name]]")
                summary_model_done = True
                continue

            if text == "({{`stackng__Model__r`.`stackng__Category__c`}})" and not stack and not summary_category_done:
                set_para_text(paragraph, "([[quote_model_category]])")
                summary_category_done = True
                continue

            if text == "{{`stackng__Seats__c`}}" and not stack and not summary_seats_done:
                set_para_text(paragraph, "[[quote_seats]]")
                summary_seats_done = True
                continue

            if text == "{{stackng__GrossPrice_SellCurrText__c}}" and not stack and not summary_price_done:
                set_para_text(paragraph, "[[quote_price]]")
                summary_price_done = True
                continue

            if text in QUOTE_PAGE_REPLACEMENTS and in_quote_loop(stack):
                set_para_text(paragraph, QUOTE_PAGE_REPLACEMENTS[text])
                continue

            if text == "{{`stackng__BaggageSummary__c`:default-val(“To be confirmed”)}}" and stack:
                set_para_text(paragraph, "[[quote_page_baggage_capacity]]")
                continue

            if text == "{{`stackng__CabinDimensions__c`:default-val(“To be confirmed”)}}  {{` stackng__SeatConfig__c`:default-val(“”)}}" and stack:
                set_para_text(paragraph, "[[quote_page_cabin_dimensions]]")
                continue

            if text in SECTION_STARTS:
                name = SECTION_STARTS[text]
                if in_quote_loop(stack) and name in STRING_CONDITIONAL_SECTIONS:
                    remove_element(parents, paragraph)
                    stack.append(f"__removed__:{name}")
                    continue
                set_para_text(paragraph, "{{#" + name + "}}")
                stack.append(name)
                continue

            if text == "{% end-section %}":
                if not stack:
                    raise RuntimeError(f"orphan section end near {text!r}")
                name = stack.pop()
                if name.startswith("__removed__:"):
                    remove_element(parents, paragraph)
                    continue
                set_para_text(paragraph, "{{/" + name + "}}")
                continue

            if text == "Generated on March 2, 2026 07:50":
                field = "nutrient__GeneratedOn__c"
                set_para_text(paragraph, "Generated on {{" + field + "}}")
                continue

            if text == "Quote Ref.: {{stackng__TripNumber__c}}":
                field = (
                    "nutrient__TripNumber__c"
                    if "stackng__FlightQuotes__r" in stack
                    else "stackng__TripNumber__c"
                )
                set_para_text(paragraph, "Quote Ref.: {{" + field + "}}")
                continue

            if text in INLINE_REPLACEMENTS:
                set_para_text(paragraph, INLINE_REPLACEMENTS[text])

        if stack:
            raise RuntimeError(f"unclosed template stack: {stack}")

        rewrite_remaining_quote_model_markers(root)
        split_vertical_rail_page_breaks(root)
        tree.write(doc_xml, encoding="UTF-8", xml_declaration=True)
        with ZipFile(OUT_DOCX, "w", ZIP_DEFLATED) as output_docx:
            for file in sorted(tmp.rglob("*")):
                if file.is_file():
                    output_docx.write(file, file.relative_to(tmp).as_posix())


def write_model() -> None:
    OUT_JSON.write_text(json.dumps(read_model(), indent=2) + "\n")


def write_readme() -> None:
    (OUT_DIR / "README.md").write_text(
        "# Nutrient quote template adapted from original DOCX\n\n"
        "This folder keeps the original `stackaero-quote-studiojazzy.docx` layout and rewrites the old markers to Nutrient Web SDK template syntax.\n\n"
        "- `stackaero-quote-template.docx` — original-based Nutrient DOCX template using direct nested loops over `stackng__Segments__r` and `stackng__FlightQuotes__r`.\n"
        "- `stackaero-quote-data.json` — nested quote data in the old payload shape, with small `nutrient__*` helpers for formatted dates and base64 image payloads.\n\n"
        "The app passes this JSON directly to `populateDocumentTemplate()`. A small post-population patch preserves legacy Word table rows and anchored aircraft image frames that live outside normal Nutrient template text.\n"
    )


if __name__ == "__main__":
    patch_template()
    write_model()
    write_readme()
    print(f"wrote {OUT_DOCX}")
    print(f"wrote {OUT_JSON}")
