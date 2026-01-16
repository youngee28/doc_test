import os
import xml.etree.ElementTree as ET
import logging
import re

logger = logging.getLogger(__name__)

# HWPX 표준 네임스페이스 정의
NAMESPACES = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hw": "http://www.hancom.co.kr/hwpml/2011/word",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}

# ET 전역 네임스페이스 등록 (ns0 부여 방지 및 HWPX 호환성 유지)
for prefix, uri in NAMESPACES.items():
    if not prefix.startswith("ns"): 
        ET.register_namespace(prefix, uri)

def update_xml_text_content(xml_path, modifications, xml_base_path=None):
    """
    XML 내의 텍스트를 수정합니다.
    레이아웃 보정 로직을 제거하고 원본 스타일을 유지합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False

        all_paragraphs = root.findall(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}p")
        for p in all_paragraphs:
            res, _ = _modify_paragraph_with_precision(p, modifications)
            if res:
                modified_any = True

        if modified_any:
            _save_xml(xml_path, root)
            return True
        return False
        
    except Exception as e:
        logger.error(f"XML 수정 중 오류 발생 ({xml_path}): {e}")
        return False

def substitute_fonts(xml_base_path, font_mapping):
    """header.xml의 폰트를 시스템 호환 폰트로 교체"""
    header_path = os.path.join(xml_base_path, "Contents", "header.xml")
    if not os.path.exists(header_path):
        return False
    try:
        tree = ET.parse(header_path)
        root = tree.getroot()
        ns_head = "{http://www.hancom.co.kr/hwpml/2011/head}"
        refList = root.find(f"{ns_head}refList")
        if refList is None: return False
        fontfaces = refList.find(f"{ns_head}fontfaces")
        if fontfaces is None: return False
        
        modified_count = 0
        for fontface in fontfaces.findall(f"{ns_head}fontface"):
            for font in fontface.findall(f"{ns_head}font"):
                face = font.get('face')
                if face in font_mapping:
                    font.set('face', font_mapping[face])
                    font.set('type', 'TTF')
                    modified_count += 1
        if modified_count > 0:
            _save_xml(header_path, root)
            print(f"[*] Font Substitution: Replaced {modified_count} fonts.")
            return True
        return False
    except Exception as e:
        logger.error(f"폰트 교체 오류: {e}")
        return False

def _save_xml(path, root):
    """공통 XML 저장 로직"""
    xml_str = ET.tostring(root, encoding="unicode")
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    xml_str = re.sub(r'<\?xml.*?\?>', '', xml_str).strip()
    with open(path, "w", encoding="UTF-8") as f:
        f.write(header + xml_str)

def _merge_paragraphs(p1, p2):
    """p2의 내용을 p1의 끝에 합칩니다."""
    runs2 = p2.findall("./{http://www.hancom.co.kr/hwpml/2011/paragraph}run")
    for run in runs2:
        p1.append(run)

def _modify_paragraph_with_precision(p_node, modifications, is_address_candidate=False):
    """문단 내 텍스트 치환 및 구조 복원"""
    runs = p_node.findall("./{http://www.hancom.co.kr/hwpml/2011/paragraph}run")
    if not runs: return False, False

    parts = []
    for run in runs:
        for child in run:
            tag = child.tag
            if tag == "{http://www.hancom.co.kr/hwpml/2011/paragraph}t":
                parts.append(child.text or "")
            elif tag == "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab":
                parts.append("\t")
            elif tag == "{http://www.hancom.co.kr/hwpml/2011/paragraph}br":
                parts.append("\n")

    combined_text = "".join(parts)
    if not combined_text.strip(): return False, False

    updated_text = combined_text
    is_modified = False
    was_address_updated = False
    
    for mod in modifications:
        orig = mod.get('original', '').strip()
        new_val = mod.get('modified', '').strip()
        if orig and orig in updated_text:
            updated_text = updated_text.replace(orig, new_val)
            is_modified = True
            if is_address_candidate: was_address_updated = True

    if is_modified:
        segments = re.split(r'(\t|\n)', updated_text)
        first_run = runs[0]
        for run in runs:
            for child in list(run):
                if child.tag in ("{http://www.hancom.co.kr/hwpml/2011/paragraph}t", 
                                 "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab", 
                                 "{http://www.hancom.co.kr/hwpml/2011/paragraph}br"):
                    run.remove(child)

        for seg in segments:
            if not seg: continue
            if seg == '\t': ET.SubElement(first_run, "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab")
            elif seg == '\n': ET.SubElement(first_run, "{http://www.hancom.co.kr/hwpml/2011/paragraph}br")
            else:
                t_node = ET.SubElement(first_run, "{http://www.hancom.co.kr/hwpml/2011/paragraph}t")
                t_node.text = seg

        lsa = p_node.find("./{http://www.hancom.co.kr/hwpml/2011/paragraph}linesegarray")
        if lsa is not None: p_node.remove(lsa)
            
        print(f"[*] Text Updated: '{combined_text[:15].strip()}...' -> '{updated_text[:15].strip()}...'")
        return True, was_address_updated

    return False, False
