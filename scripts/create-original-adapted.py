from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import json
import shutil

SRC_DOCX = Path('assets/stackaero-quote-studiojazzy.docx')
SRC_DATA = Path('assets/nutrient-quote-original-adapted/stackaero-quote-data.json')
OUT_DIR = Path('assets/nutrient-quote-original-adapted')
OUT_DOCX = OUT_DIR / 'stackaero-quote-template.docx'
OUT_JSON = OUT_DIR / 'stackaero-quote-data.json'

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML = 'http://www.w3.org/XML/1998/namespace'

ET.register_namespace('w', W)

def qn(ns: str, tag: str) -> str:
    return f'{{{ns}}}{tag}'

W_P = qn(W, 'p')
W_R = qn(W, 'r')
W_T = qn(W, 't')
W_BR = qn(W, 'br')
W_BODY = qn(W, 'body')
W_PPR = qn(W, 'pPr')
W_PAGE_BREAK_BEFORE = qn(W, 'pageBreakBefore')
W_RPR = qn(W, 'rPr')
W_DRAWING = qn(W, 'drawing')


def para_text(p: ET.Element) -> str:
    # Only read text from runs that are direct children of this paragraph.
    # Outer paragraphs can contain anchored drawings with nested text-box
    # paragraphs; including those nested texts causes us to delete the drawing.
    texts: list[str] = []
    for run in p.findall(f'./{W_R}'):
        for text_node in run.findall(f'./{W_T}'):
            texts.append(text_node.text or '')
    return ''.join(texts)


def element_text(el: ET.Element) -> str:
    return ''.join(text_node.text or '' for text_node in el.iter(W_T))


def first_rpr(p: ET.Element) -> ET.Element | None:
    for r in p.findall(f'./{W_R}'):
        rpr = r.find(f'./{W_RPR}')
        if rpr is not None:
            return deepcopy(rpr)
    return None


def set_para_text(p: ET.Element, text: str, style_source: ET.Element | None = None) -> None:
    ppr = p.find(f'./{W_PPR}')
    ppr_copy = deepcopy(ppr) if ppr is not None else None
    rpr_copy = first_rpr(style_source or p)
    p.clear()
    if ppr_copy is not None:
        p.append(ppr_copy)
    r = ET.SubElement(p, W_R)
    if rpr_copy is not None:
        r.append(rpr_copy)
    t = ET.SubElement(r, W_T)
    if text.startswith(' ') or text.endswith(' ') or '  ' in text:
        t.set(qn(XML, 'space'), 'preserve')
    t.text = text


def remove_element(parent_map: dict[ET.Element, ET.Element], el: ET.Element) -> None:
    parent = parent_map.get(el)
    if parent is not None:
        parent.remove(el)


def text_from_specs(quote: dict, label: str, default: str = '') -> str:
    for spec in quote.get('specs', []):
        if spec.get('label') == label:
            return str(spec.get('value') or default)
    return default


def quote_model(quote: dict) -> dict:
    year = text_from_specs(quote, 'Year of Make')
    wifi = text_from_specs(quote, 'Wi-Fi')
    owner_approval = text_from_specs(quote, 'Owners Approval')
    catering = text_from_specs(quote, 'Catering')
    cabin_crew = text_from_specs(quote, 'Cabin Crew')
    pets = text_from_specs(quote, 'Pets')
    smoking = text_from_specs(quote, 'Smoking')
    safety = text_from_specs(quote, 'Safety Ratings')
    inclusions = str(quote.get('inclusions') or '')
    exclusions = str(quote.get('exclusions') or '')
    return {
        'option_number': str(quote.get('option_number') or ''),
        'model_name': str(quote.get('model_name') or ''),
        'model_category': str(quote.get('model_category') or text_from_specs(quote, 'Category', 'Category TBC')),
        'seats': str(quote.get('seats') or text_from_specs(quote, 'Seating')),
        'price': str(quote.get('price') or ''),
        'baggage_capacity': text_from_specs(quote, 'Baggage Capacity', 'To be confirmed'),
        'cabin_dimensions': text_from_specs(quote, 'Cabin Dimensions', 'To be confirmed'),
        'seat_config': text_from_specs(quote, 'Seat Config'),
        'year_of_make': year,
        'refurbished_year': text_from_specs(quote, 'Refurbished'),
        'wifi': wifi,
        'owner_approval': owner_approval,
        'catering': catering,
        'cabin_crew': cabin_crew,
        'pets': pets,
        'smoking': smoking,
        'safety_ratings': safety,
        'has_year_of_make': bool(year),
        'has_refurbished_year': bool(text_from_specs(quote, 'Refurbished')),
        'has_wifi': bool(wifi),
        'has_owner_approval': bool(owner_approval),
        'has_catering': bool(catering),
        'has_cabin_crew': bool(cabin_crew),
        'has_pets': bool(pets),
        'has_smoking': bool(smoking),
        'has_safety_ratings': bool(safety),
        'has_inclusions': bool(inclusions),
        'inclusions': inclusions,
        'has_exclusions': bool(exclusions),
        'exclusions': exclusions,
        'exterior_image': quote['exterior_image'],
        'interior_image': quote['interior_image'],
    }


def build_model() -> dict:
    clean = json.loads(SRC_DATA.read_text())
    model = {
        'trip_name': clean['trip_name'],
        'trip_date_long': clean['trip_date_long'],
        'trip_number': clean['trip_number'],
        'generated_on': clean['generated_on'],
        'passenger_count': clean['passenger_count'],
        'pricing_note': clean['pricing_note'],
        'route_city_names': clean['route_city_names'],
        'route_airport_codes': clean['route_airport_codes'],
        'never': False,
        'segments': clean['segments'],
        'quotes': [quote_model(q) for q in clean['quotes']],
    }
    for quote_index, quote in enumerate(model['quotes'], 1):
        for key, value in quote.items():
            if key.endswith('_image'):
                continue
            model[f'quote_{quote_index}_{key}'] = value
    return model


def apply_text_replacements(el: ET.Element, replacements: dict[str, str]) -> None:
    for text_node in el.iter(W_T):
        if not text_node.text:
            continue
        text = text_node.text
        for old, new in replacements.items():
            text = text.replace(old, new)
        text_node.text = text


def find_body_child_index(children: list[ET.Element], needle: str, start: int = 0) -> int:
    for index, child in enumerate(children[start:], start):
        if element_text(child) == needle:
            return index
    raise RuntimeError(f'could not find body child: {needle}')


def quote_replacements(quote_index: int) -> dict[str, str]:
    prefix = f'quote_{quote_index}_'
    return {
        'Quote Ref.: {{stackng__TripNumber__c}}': 'Quote Ref.: {{trip_number}}',
        'Generated on March 2, 2026 07:50': 'Generated on {{generated_on}}',
        '{{`stackng__Model__r`.Name}}': '{{' + prefix + 'model_name}}',
        '{{`stackng__Model__r`.Name}}{{`stackng__Model__r`.Name}}': '{{' + prefix + 'model_name}}',
        '({{`stackng__Model__r`.`stackng__Category__c`}})': '({{' + prefix + 'model_category}})',
        'Option – {{index}}': 'Option – {{' + prefix + 'option_number}}',
        '{{stackng__GrossPrice_SellCurrText__c}}': '{{' + prefix + 'price}}',
        '{{stackng__Model__r.stackng__Category__c:default-val(Category TBC)}}': '{{' + prefix + 'model_category}}',
        '{{`stackng__Seats__c`}}': '{{' + prefix + 'seats}}',
        '{{`stackng__BaggageSummary__c`:default-val(“To be confirmed”)}}': '{{' + prefix + 'baggage_capacity}}',
        '{{`stackng__CabinDimensions__c`:default-val(“To be confirmed”)}}  {{` stackng__SeatConfig__c`:default-val(“”)}}': '{{' + prefix + 'cabin_dimensions}} {{' + prefix + 'seat_config}}',
        '{{`stackng__YOM__c`}}': '{{' + prefix + 'year_of_make}}',
        'Refurbished in {{`stackng__YOR__c`}}': 'Refurbished in {{' + prefix + 'refurbished_year}}',
        '{{stackng__WiFi__c}}': '{{' + prefix + 'wifi}}',
        '{{`stackng__OwnerApproval__c`}}': '{{' + prefix + 'owner_approval}}',
        '{{`stackng__CateringAvailable__c`}}': '{{' + prefix + 'catering}}',
        '{{`stackng__CabinCrew__c`}}': '{{' + prefix + 'cabin_crew}}',
        '{{`stackng__PetsAllowed__c`}}': '{{' + prefix + 'pets}}',
        '{{`stackng__Smoking__c`}}': '{{' + prefix + 'smoking}}',
        '{{`stackng__Operator__r`.stackng__SafetyRatings__c}}': '{{' + prefix + 'safety_ratings}}',
        '{{stackng__Inclusions__c}}': '{{' + prefix + 'inclusions}}',
        '{{stackng__Exclusions__c}}': '{{' + prefix + 'exclusions}}',
    }


QUOTE_CONDITIONALS = {
    '{% conditional-section expr($length(stackng__YOM__c) > 0) %}': 'has_year_of_make',
    '{% conditional-section expr($length(stackng__YOR__c) > 0) %}': 'has_refurbished_year',
    '{% conditional-section expr($length(stackng__WiFi__c) > 0) %}': 'has_wifi',
    '{% conditional-section expr($length(stackng__OwnerApproval__c) > 0) %}': 'has_owner_approval',
    '{% conditional-section expr($length(stackng__CateringAvailable__c) > 0) %}': 'has_catering',
    '{% conditional-section expr($length(stackng__CabinCrew__c) > 0) %}': 'has_cabin_crew',
    '{% conditional-section expr($length(stackng__PetsAllowed__c) > 0) %}': 'has_pets',
    '{% conditional-section expr($length(stackng__Smoking__c) > 0) %}': 'has_smoking',
    '{% conditional-section expr($length(`stackng__Operator__r`.stackng__SafetyRatings__c) > 0) %}': 'has_safety_ratings',
    '{% conditional-section expr(stackng__renderInclusions__c = true) %}': 'has_inclusions',
    '{% conditional-section expr(stackng__renderExclusions__c = true) %}': 'has_exclusions',
}


def prune_quote_conditionals(block: list[ET.Element], quote: dict) -> None:
    wrapper = ET.Element('wrapper')
    for child in block:
        wrapper.append(child)
    parent_map = {child: parent for parent in wrapper.iter() for child in parent}
    stack: list[bool] = []
    for paragraph in list(wrapper.iter(W_P)):
        text = element_text(paragraph)
        if text in QUOTE_CONDITIONALS:
            stack.append(bool(quote.get(QUOTE_CONDITIONALS[text])))
            remove_element(parent_map, paragraph)
            continue
        if text == '{% end-section %}' and stack:
            stack.pop()
            remove_element(parent_map, paragraph)
            continue
        if stack and not all(stack):
            remove_element(parent_map, paragraph)


def normalize_quote_page_break(block: list[ET.Element]) -> None:
    for index, child in enumerate(block):
        page_break = child.find(f'.//{W_PAGE_BREAK_BEFORE}')
        if page_break is None:
            continue
        parent_map = {node: parent for parent in child.iter() for node in parent}
        remove_element(parent_map, page_break)
        page_break_paragraph = ET.Element(W_P)
        run = ET.SubElement(page_break_paragraph, W_R)
        br = ET.SubElement(run, W_BR)
        br.set(qn(W, 'type'), 'page')
        block.insert(index, page_break_paragraph)
        return


def rewrite_quote_block(block: list[ET.Element], quote_index: int, quote: dict) -> None:
    normalize_quote_page_break(block)
    prune_quote_conditionals(block, quote)
    replacements = quote_replacements(quote_index)
    wrapper = ET.Element('wrapper')
    for child in block:
        wrapper.append(child)
    for paragraph in list(wrapper.iter(W_P)):
        text = para_text(paragraph)
        if text in replacements:
            set_para_text(paragraph, replacements[text])
    apply_text_replacements(wrapper, replacements)


def patch_template() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        with ZipFile(SRC_DOCX) as zin:
            zin.extractall(tmp)
        doc_xml = tmp / 'word' / 'document.xml'
        tree = ET.parse(doc_xml)
        root = tree.getroot()
        model = build_model()
        body = root.find(f'.//{W_BODY}')
        if body is None:
            raise RuntimeError('document body not found')

        children = list(body)
        repeat_start = find_body_child_index(children, '{% repeating-section `stackng__FlightQuotes__r` %}')
        repeat_end = find_body_child_index(children, '{% end-section %}', repeat_start + 1)
        quote_block_source = children[repeat_start + 1:repeat_end]
        rebuilt_children = children[:repeat_start]
        for quote_index, quote in enumerate(model['quotes'], 1):
            quote_block = [deepcopy(child) for child in quote_block_source]
            rewrite_quote_block(quote_block, quote_index, quote)
            rebuilt_children.extend(quote_block)
        rebuilt_children.extend(children[repeat_end + 1:])

        body.clear()
        for child in rebuilt_children:
            body.append(child)

        # Keep the original anchored picture placeholders. Nutrient image markers
        # reflow when placed inline and are not substituted inside Word text boxes,
        # so the app patches these image anchors in the populated DOCX before PDF conversion.
        parent_map = {child: parent for parent in root.iter() for child in parent}
        stack: list[str] = []
        price_seen = 0
        summary_index_done = False

        replacements = {
            '{{$fromMillis($toMillis(stackng__StartDateLocal__c, "[Y0001]-[M01]-[D01]"), "[FNn] [D01]-[MNn]-[Y0001]")}}': '{{trip_date_long}}',
            'Quote Ref.: {{stackng__TripNumber__c}}': 'Quote Ref.: {{trip_number}}',
            '{{stackng__DepartDay__c}} {{stackng__DepartDateLocal_text__c}}': '{{#segments}}{{segment_date}}',
            '{% conditional-section expr(stackng__DepartTimeTBC__c = true) %}--:--{% end-section %}{% conditional-section expr(stackng__DepartTimeTBC__c = false) %}{{`stackng__DepartTimeLocal__c`}}{% end-section %}': '{{depart_time}}',
            '{{`stackng__FromCity__c`}}  - {{`stackng__FromCodes__c`}}': '{{depart_route}}',
            '{{`stackng__From__r`.`stackng__LocalName__c`}}': '{{depart_airport}}',
            '{% conditional-section expr(stackng__DepartTimeTBC__c = true) %}--:--{% end-section %}{% conditional-section expr(stackng__DepartTimeTBC__c = false) %}{{`stackng__ArriveTimeLocal__c`}}{% end-section %}': '{{arrive_time}}',
            '{{`stackng__ToCity__c`}} - {{`stackng__ToCodes__c`}}': '{{arrive_route}}',
            '{{`stackng__To__r`.`stackng__LocalName__c`}}': '{{arrive_airport}}',
            '{{`stackng__EBT_formula__c`}}': '{{flight_time}}{{/segments}}',
            'Pricing based on {{ `stackng__PAXest__c`}} passengers': 'Pricing based on {{passenger_count}} passengers',
            '*Pricing based on {{`stackng__PAXest__c`}} passengers on each segment.': '*Pricing based on {{passenger_count}} passengers on each segment.',
            '{{`stackng__Model__r`.Name}}': '{{model_name}}',
            '{{`stackng__Model__r`.Name}}{{`stackng__Model__r`.Name}}': '{{model_name}}',
            '({{`stackng__Model__r`.`stackng__Category__c`}})': '({{model_category}})',
            '{{`stackng__Seats__c`}}': '{{seats}}',
            'Option – {{index}}': 'Option – {{option_number}}',
            '{{stackng__Model__r.stackng__Category__c:default-val(Category TBC)}}': '{{model_category}}',
            '{{`stackng__BaggageSummary__c`:default-val(“To be confirmed”)}}': '{{baggage_capacity}}',
            '{{`stackng__CabinDimensions__c`:default-val(“To be confirmed”)}}  {{` stackng__SeatConfig__c`:default-val(“”)}}': '{{cabin_dimensions}} {{seat_config}}',
            'Refurbished in {{`stackng__YOR__c`}}': 'Refurbished in {{refurbished_year}}',
            '{{`stackng__YOM__c`}}': '{{year_of_make}}',
            '{{stackng__WiFi__c}}': '{{wifi}}',
            '{{`stackng__OwnerApproval__c`}}': '{{owner_approval}}',
            '{{`stackng__CateringAvailable__c`}}': '{{catering}}',
            '{{`stackng__CabinCrew__c`}}': '{{cabin_crew}}',
            '{{`stackng__PetsAllowed__c`}}': '{{pets}}',
            '{{`stackng__Smoking__c`}}': '{{smoking}}',
            '{{`stackng__Operator__r`.stackng__SafetyRatings__c}}': '{{safety_ratings}}',
            '{{stackng__Inclusions__c}}': '{{inclusions}}',
            '{{stackng__Exclusions__c}}': '{{exclusions}}',
            'Generated on March 2, 2026 07:50': 'Generated on {{generated_on}}',
        }
        conditional_starts = {
            '{% conditional-section expr($length(stackng__YOM__c) > 0) %}': 'has_year_of_make',
            '{% conditional-section expr($length(stackng__YOR__c) > 0) %}': 'has_refurbished_year',
            '{% conditional-section expr($length(stackng__WiFi__c) > 0) %}': 'has_wifi',
            '{% conditional-section expr($length(stackng__OwnerApproval__c) > 0) %}': 'has_owner_approval',
            '{% conditional-section expr($length(stackng__CateringAvailable__c) > 0) %}': 'has_catering',
            '{% conditional-section expr($length(stackng__CabinCrew__c) > 0) %}': 'has_cabin_crew',
            '{% conditional-section expr($length(stackng__PetsAllowed__c) > 0) %}': 'has_pets',
            '{% conditional-section expr($length(stackng__Smoking__c) > 0) %}': 'has_smoking',
            '{% conditional-section expr($length(`stackng__Operator__r`.stackng__SafetyRatings__c) > 0) %}': 'has_safety_ratings',
            '{% conditional-section expr(stackng__renderInclusions__c = true) %}': 'has_inclusions',
            '{% conditional-section expr(stackng__renderExclusions__c = true) %}': 'has_exclusions',
            '{% conditional-section expr(true = false) %}': 'never',
        }

        for p in list(root.iter(W_P)):
            text = para_text(p)
            if not text:
                continue
            if text in ('{% table-start `stackng__Segments__r` %}', '{% table-start stackng__FlightQuotes__r %}', '{% table-end %}'):
                remove_element(parent_map, p)
                continue
            if text == '{% repeating-section `stackng__FlightQuotes__r` %}':
                remove_element(parent_map, p)
                continue
            if text in conditional_starts:
                name = conditional_starts[text]
                set_para_text(p, '{{#' + name + '}}')
                stack.append(name)
                continue
            if text == '{% end-section %}':
                name = stack.pop() if stack else 'unused_section'
                set_para_text(p, '{{/' + name + '}}')
                continue
            if text == '{{index}}' and not summary_index_done:
                set_para_text(p, '{{#quotes}}{{option_number}}')
                summary_index_done = True
                continue
            if text == '{{stackng__GrossPrice_SellCurrText__c}}':
                price_seen += 1
                set_para_text(p, '{{price}}{{/quotes}}' if price_seen == 1 else '{{price}}')
                continue
            if text in replacements:
                set_para_text(p, replacements[text])

        if stack:
            raise RuntimeError(f'unclosed template stack: {stack}')

        ET.ElementTree(root).write(doc_xml, encoding='UTF-8', xml_declaration=True)
        with ZipFile(OUT_DOCX, 'w', ZIP_DEFLATED) as zout:
            for file in sorted(tmp.rglob('*')):
                if file.is_file():
                    zout.write(file, file.relative_to(tmp).as_posix())


def write_model() -> None:
    model = build_model()
    OUT_JSON.write_text(json.dumps(model, indent=2) + '\n')


def write_readme() -> None:
    (OUT_DIR / 'README.md').write_text(
        '# Nutrient quote template adapted from original DOCX\n\n'
        'This folder keeps the original `stackaero-quote-studiojazzy.docx` layout, embedded fonts, text boxes, and artwork. '
        'The old template markers were rewritten to Nutrient Web SDK compatible placeholders.\n\n'
        '- `stackaero-quote-template.docx` — original-based Nutrient DOCX template.\n'
        '- `stackaero-quote-data.json` — flattened model passed to `populateDocumentTemplate()`.\n\n'
        'The aircraft option pages are intentionally unrolled from the original repeating section. '
        'This avoids Nutrient/Word floating-object drift with page-break text boxes and anchored aircraft images. '
        'The app still uses Nutrient for template population and PDF conversion, then patches the preserved DOCX image anchors with base64 image bytes so browser CORS does not affect generation.\n\n'
        'Nutrient placeholder names are intentionally simple (`letters`, `numbers`, `_`).\n'
    )


if __name__ == '__main__':
    patch_template()
    write_model()
    write_readme()
    print(f'wrote {OUT_DOCX}')
    print(f'wrote {OUT_JSON}')
