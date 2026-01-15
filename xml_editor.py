import os
import glob
import json
import xml.etree.ElementTree as ET
import argparse
import re

NAMESPACES = {
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opf": "http://www.idpf.org/2007/opf/",
    "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",
    "epub": "http://www.idpf.org/2007/ops",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
}

# 출력 xml용 네임스페이스 등록
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

def update_xml_text_content(xml_path, modifications):
    """
    XML 파일 내의 텍스트 내용을 수정합니다.
    형식을 최대한 보존하기 위해 XML을 문자열로 처리하여 치환합니다.
    """
    try:
        if not os.path.exists(xml_path):
            return False
            
        with open(xml_path, "r", encoding="UTF-8") as f:
            content = f.read()

        original_content = content
        
        # 문단 패턴 (hp:p)
        p_pattern = re.compile(r"(<hp:p.*?>)(.*?)(</hp:p>)", re.DOTALL)
        
        def replace_p_content(match):
            p_start = match.group(1)
            p_body = match.group(2)
            p_end = match.group(3)
            
            # 텍스트 추출 및 정규화 (비교용)
            p_body_normalized = re.sub(r"<hp:tab[^>]*?/>", "\t", p_body)
            t_pattern = re.compile(r"<hp:t.*?>(.*?)</hp:t>", re.DOTALL)
            t_contents = t_pattern.findall(p_body_normalized)
            combined_text = "".join(t_contents)
            
            updated_text = combined_text
            modified = False
            
            for mod in modifications:
                orig = mod.get('original', '').strip()
                new_val = mod.get('modified', '').strip()
                if not orig: continue
                
                # 1. 완전 일치 치환
                if orig in updated_text:
                    updated_text = updated_text.replace(orig, new_val)
                    modified = True
                else:
                    # 2. 유연한 공백 매칭 치환 (Regex 활용)
                    escaped_orig = "".join([re.escape(c) + r"\s*" for c in orig]).strip(r"\s*")
                    if re.search(escaped_orig, updated_text):
                        updated_text = re.sub(escaped_orig, new_val, updated_text)
                        modified = True
            
            if modified:
                # hp:t 태그들을 찾아 첫 번째 태그에 모든 텍스트를 몰아넣고 나머지는 비움 (HWPX 특성 반영)
                t_tags = list(re.finditer(r"<hp:t.*?>.*?</hp:t>", p_body, re.DOTALL))
                if not t_tags: return match.group(0)
                
                parts = []
                last_end = 0
                for i, t_tag in enumerate(t_tags):
                    parts.append(p_body[last_end:t_tag.start()])
                    s_tag_match = re.match(r"(<hp:t.*?>)", t_tag.group(0), re.DOTALL)
                    s_tag = s_tag_match.group(1) if s_tag_match else "<hp:t>"
                    
                    if i == 0:
                        parts.append(f"{s_tag}{updated_text}</hp:t>")
                    else:
                        parts.append(f"{s_tag}</hp:t>")
                    last_end = t_tag.end()
                parts.append(p_body[last_end:])
                
                # 불필요한 레이아웃 정보 제거 (치환 시 위치가 틀어질 수 있으므로)
                new_p_body = "".join(parts)
                new_p_body = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", new_p_body, flags=re.DOTALL)
                
                print(f"[*] Text Updated: '{combined_text.strip()}' -> '{updated_text.strip()}'")
                return p_start + new_p_body + p_end
            
            return match.group(0)

        new_content = p_pattern.sub(replace_p_content, content)

        if new_content != original_content:
            with open(xml_path, "w", encoding="UTF-8") as f:
                f.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"[!] XML 수정 오류 ({xml_path}): {e}")
        return False
