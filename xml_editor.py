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

def update_xml_text_content(xml_path, modifications):
    """
    XML 내의 텍스트를 정밀하게 수정합니다.
    탭(<hp:tab/>)과 줄바꿈(<hp:br/>)을 보존하여 PDF 변환 시 정렬이 틀어지지 않게 합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False

        # 모든 문단 순회
        for p in root.findall(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}p"):
            if _modify_paragraph_with_precision(p, modifications):
                modified_any = True

        if modified_any:
            _save_xml(xml_path, root)
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"XML 정밀 수정 중 오류 발생 ({xml_path}): {e}")
        return False

def substitute_fonts(xml_base_path, font_mapping):
    """
    header.xml에 정의된 폰트를 시스템에 설치된 호환 폰트로 교체합니다.
    PDF 변환 시 폰트 깨짐 및 정렬 오류를 근본적으로 해결합니다.
    """
    header_path = os.path.join(xml_base_path, "Contents", "header.xml")
    if not os.path.exists(header_path):
        return False
        
    try:
        tree = ET.parse(header_path)
        root = tree.getroot()
        
        # HWPX 헤더 네임스페이스 (보통 hp/hs 등이 아니라, head/refList 구조를 가짐)
        # 하지만 여기서 ElementTree는 태그 앞의 URL을 보고 파싱하므로, 
        # 위 NAMESPACES에 없는 HWPX 헤더 전용 네임스페이스를 고려해야 할 수도 있음.
        # 보편적으로 refList/fontfaces 구조를 찾기 위해 단순 탐색을 시도.
        
        # header.xml의 root tag는 {http://www.hancom.co.kr/hwpml/2011/head}head
        ns_head = "{http://www.hancom.co.kr/hwpml/2011/head}"
        refList = root.find(f"{ns_head}refList")
        if refList is None:
            return False
            
        fontfaces = refList.find(f"{ns_head}fontfaces")
        if fontfaces is None:
            return False
            
        modified_count = 0
        for fontface in fontfaces.findall(f"{ns_head}fontface"):
            for font in fontface.findall(f"{ns_head}font"):
                current_face = font.get('face')
                if current_face in font_mapping:
                    new_face = font_mapping[current_face]
                    font.set('face', new_face)
                    # 식별 편의를 위해 type도 TTF로 통일할 수 있음
                    font.set('type', 'TTF')
                    modified_count += 1
                    
        if modified_count > 0:
            print(f"[*] Font Substitution: Replaced {modified_count} fonts with system compatible fonts.")
            _save_xml(header_path, root)
            return True
            
        return False

    except Exception as e:
        logger.error(f"폰트 교체 중 오류 발생 ({header_path}): {e}")
        return False

def _save_xml(path, root):
    """공통 XML 저장 로직"""
    xml_str = ET.tostring(root, encoding="unicode")
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    # 중복 헤더 제거
    xml_str = re.sub(r'<\?xml.*?\?>', '', xml_str).strip()
    
    with open(path, "w", encoding="UTF-8") as f:
        f.write(header + xml_str)

def _modify_paragraph_with_precision(p_node, modifications):
    """
    문단 내 텍스트를 치환하되, 탭과 줄바꿈 구조를 완벽하게 복원합니다.
    """
    runs = p_node.findall("./{http://www.hancom.co.kr/hwpml/2011/paragraph}run")
    if not runs:
        return False

    # 1. 문단 전체 텍스트 수집 (탭=\t, 줄바꿈=\n으로 매핑)
    parts = []
    
    for run in runs:
        for child in run:
            tag = child.tag
            if tag == "{http://www.hancom.co.kr/hwpml/2011/paragraph}t":
                txt = child.text or ""
                parts.append(txt)
            elif tag == "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab":
                parts.append("\t")
            elif tag == "{http://www.hancom.co.kr/hwpml/2011/paragraph}br":
                parts.append("\n")

    combined_text = "".join(parts)
    if not combined_text.strip():
        return False

    # 2. 치환 수행
    updated_text = combined_text
    is_modified = False
    for mod in modifications:
        orig = mod.get('original', '').strip()
        new_val = mod.get('modified', '').strip()
        if orig and orig in updated_text:
            updated_text = updated_text.replace(orig, new_val)
            is_modified = True

    if is_modified:
        # 3. 정밀 재구성
        segments = re.split(r'(\t|\n)', updated_text)
        first_run = runs[0]
        
        # 기존 run들에서 텍스트성 노드만 제거
        for run in runs:
            for child in list(run):
                if child.tag in ("{http://www.hancom.co.kr/hwpml/2011/paragraph}t", 
                                 "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab", 
                                 "{http://www.hancom.co.kr/hwpml/2011/paragraph}br"):
                    run.remove(child)

        # 수정된 내용을 첫 번째 run에 삽입
        for seg in segments:
            if not seg: continue
            if seg == '\t':
                ET.SubElement(first_run, "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab")
            elif seg == '\n':
                ET.SubElement(first_run, "{http://www.hancom.co.kr/hwpml/2011/paragraph}br")
            else:
                t_node = ET.SubElement(first_run, "{http://www.hancom.co.kr/hwpml/2011/paragraph}t")
                t_node.text = seg

        # 레이아웃 정보 삭제
        lsa = p_node.find("./{http://www.hancom.co.kr/hwpml/2011/paragraph}linesegarray")
        if lsa is not None:
            p_node.remove(lsa)
            
        print(f"[*] Text Updated with Tabs: '{combined_text[:15].strip()}...' -> '{updated_text[:15].strip()}...'")
        return True

    return False
