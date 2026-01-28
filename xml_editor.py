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
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
}

# ET 전역 네임스페이스 등록 (ns0 부여 방지 및 HWPX 호환성 유지)
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

def update_xml_text_content(xml_path, modifications):
    """
    XML 내의 텍스트를 수정합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False

        all_paragraphs = root.findall(".//{http://www.hancom.co.kr/hwpml/2011/paragraph}p")
        for p in all_paragraphs:
            if _modify_paragraph_with_precision(p, modifications):
                modified_any = True

        if modified_any:
            _save_xml(xml_path, root)
            return True
        return False
        
    except Exception as e:
        logger.error(f"XML 수정 중 오류 발생 ({xml_path}): {e}")
        return False

def update_paragraph_style(xml_path, para_id, style_modifications):
    """
    특정 paraPr(문단 스타일)의 속성(예: horizontal align)을 수정합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False

        # hh 네임스페이스 정의
        ns_hh = "{http://www.hancom.co.kr/hwpml/2011/head}"
        
        # 모든 paraPr 요소 중 id가 일치하는 것 탐색
        for para_pr in root.findall(f".//{ns_hh}paraPr"):
            if para_pr.get("id") == str(para_id):
                # hh:align 요소 찾기
                align_node = para_pr.find(f"{ns_hh}align")
                if align_node is None:
                    align_node = ET.SubElement(para_pr, f"{ns_hh}align")
                
                for attr, value in style_modifications.items():
                    old_val = align_node.get(attr)
                    if old_val != value:
                        align_node.set(attr, value)
                        modified_any = True
                        print(f"[*] Style Updated (ID:{para_id}): {attr}='{old_val}' -> '{value}'")

        if modified_any:
            _save_xml(xml_path, root)
            return True
        return False

    except Exception as e:
        logger.error(f"스타일 수정 중 오류 발생 ({xml_path}): {e}")
        return False

def update_paragraph_margin_direct(xml_path, para_id, margin_hwpunit):
    """
    특정 paraPr의 왼쪽 여백을 HWPUNIT 수치로 직접 수정합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False
        ns_hh = "{http://www.hancom.co.kr/hwpml/2011/head}"
        ns_hc = "{http://www.hancom.co.kr/hwpml/2011/core}"
        
        val_str = str(int(margin_hwpunit))

        for para_pr in root.findall(f".//{ns_hh}paraPr"):
            if para_pr.get("id") == str(para_id):
                margins = para_pr.findall(f".//{ns_hh}margin")
                for margin in margins:
                    # 왼쪽 여백 설정
                    left_node = margin.find(f"{ns_hc}left")
                    if left_node is not None:
                        left_node.set("value", val_str)
                        left_node.set("unit", "HWPUNIT")
                        modified_any = True
                    
                    # 들여쓰기를 0으로 초기화하여 정확한 시작 위치 보장
                    intent_node = margin.find(f"{ns_hc}intent")
                    if intent_node is not None:
                        intent_node.set("value", "0")
                        intent_node.set("unit", "HWPUNIT")
                        modified_any = True
                
                if modified_any:
                    print(f"[*] Margin Updated (ID:{para_id}): value={val_str} HWPUNIT")

        if modified_any:
            _save_xml(xml_path, root)
            return True
        return False

    except Exception as e:
        logger.error(f"여백 수치 주입 중 오류 발생 ({xml_path}): {e}")
        return False

def clear_paragraph_layout(xml_path, para_id):
    """
    특정 스타일을 사용하는 문단의 레이아웃 캐시(linesegarray)를 삭제합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False
        ns_hp = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

        for p in root.findall(f".//{ns_hp}p"):
            if p.get("paraPrIDRef") == str(para_id):
                lsa = p.find(f"{ns_hp}linesegarray")
                if lsa is not None:
                    p.remove(lsa)
                    modified_any = True

        if modified_any:
            _save_xml(xml_path, root)
            print(f"[*] Layout Cache Cleared (Style:{para_id}, File:{os.path.basename(xml_path)})")
            return True
        return False

    except Exception as e:
        logger.error(f"레이아웃 삭제 중 오류 발생 ({xml_path}): {e}")
        return False

def fix_image_position_absolute(xml_path, target_para_id, target_x_hwpunit, target_y_hwpunit=None):
    """
    특정 문단 내의 이미지(hp:pic) 위치를 종이(PAPER) 기준으로 고정합니다.
    문단 여백 변화에 영향을 받지 않게 하기 위함입니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False

        tree = ET.parse(xml_path)
        root = tree.getroot()
        modified_any = False
        ns_hp = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

        for p in root.findall(f".//{ns_hp}p"):
            if p.get("paraPrIDRef") == str(target_para_id):
                # 문단 내 모든 이미지 탐색
                pics = p.findall(f".//{ns_hp}pic")
                for pic in pics:
                    pos = pic.find(f"{ns_hp}pos")
                    if pos is not None:
                        # 기준을 '종이(PAPER)'로 변경 (문단 여백 무시)
                        pos.set("horzRelTo", "PAPER")
                        # horzAlign이 'LEFT' 등이면 오프셋이 무시될 수 있으므로 'NONE'으로 설정
                        pos.set("horzAlign", "NONE")
                        # 지정된 절대 좌표 주입 (예: 기존 35578 + 여백 고려한 적절한 절대 위치)
                        pos.set("horzOffset", str(int(target_x_hwpunit)))
                        
                        if target_y_hwpunit is not None:
                            # 필요시 수직 위치도 고정
                            pos.set("vertRelTo", "PAPER")
                            pos.set("vertOffset", str(int(target_y_hwpunit)))
                        
                        # 텍스트와의 관계를 '글 앞으로' 설정하여 레이아웃 충돌 방지
                        pic.set("textWrap", "IN_FRONT_OF_TEXT")
                        
                        modified_any = True
                        print(f"[*] Image Position Locked (Para:{target_para_id}): X={target_x_hwpunit} PAPER")

        if modified_any:
            _save_xml(xml_path, root)
            return True
        return False

    except Exception as e:
        logger.error(f"이미지 위치 고정 중 오류 발생 ({xml_path}): {e}")
        return False



def _save_xml(path, root):
    """공통 XML 저장 로직"""
    xml_str = ET.tostring(root, encoding="unicode")
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    xml_str = re.sub(r'<\?xml.*?\?>', '', xml_str).strip()
    with open(path, "w", encoding="UTF-8") as f:
        f.write(header + xml_str)


def _modify_paragraph_with_precision(p_node, modifications):
    """문단 내 텍스트 치환 및 구조 복원"""
    runs = p_node.findall("./{http://www.hancom.co.kr/hwpml/2011/paragraph}run")
    if not runs: return False

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
    if not combined_text.strip(): return False

    updated_text = combined_text
    is_modified = False
    
    for mod in modifications:
        orig = mod.get('original', '').strip()
        new_val = mod.get('modified', '').strip()
        if orig and orig in updated_text:
            updated_text = updated_text.replace(orig, new_val)
            is_modified = True

    if is_modified:
        segments = re.split(r'(\t|\n)', updated_text)
        first_run = runs[0]
        # 기존 모든 런의 텍스트 노드 제거
        for run in runs:
            for child in list(run):
                if child.tag in ("{http://www.hancom.co.kr/hwpml/2011/paragraph}t", 
                                 "{http://www.hancom.co.kr/hwpml/2011/paragraph}tab", 
                                 "{http://www.hancom.co.kr/hwpml/2011/paragraph}br"):
                    run.remove(child)

        # 첫 번째 런에 수정된 텍스트 재조립
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
        return True

    return False
