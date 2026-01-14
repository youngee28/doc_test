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

def modify_xml_with_ai(xml_path, ai_modifications):
    """
    Directly modifies the XML file as a string to preserve formatting.
    Supports both traditional string-match replacements and anchor-based positional replacements.
    """
    try:
        with open(xml_path, "r", encoding="UTF-8") as f:
            content = f.read()

        original_content = content
        
        positional_mods = [m for m in ai_modifications if "anchor" in m and "offset" in m]
        if positional_mods:
            # 모든 문단 추출
            p_pattern = re.compile(r"(<hp:p.*?>)(.*?)(</hp:p>)", re.DOTALL)
            paragraphs = list(p_pattern.finditer(content))
            
            pending_replacements = [] # list of (start, end, new_full_p)
            
            for mod in positional_mods:
                anchor = mod["anchor"]
                offset = mod["offset"]
                new_val = mod["modified"]
                
                # Anchor가 있는 문단 찾기
                anchor_idx = -1
                for i, p_match in enumerate(paragraphs):
                    p_body = p_match.group(2)
                    if anchor in p_body:
                        anchor_idx = i
                        break
                
                if anchor_idx != -1 and anchor_idx + offset < len(paragraphs):
                    target_idx = anchor_idx + offset
                    target_match = paragraphs[target_idx]
                    
                    p_start = target_match.group(1)
                    p_body = target_match.group(2)
                    p_end = target_match.group(3)
                    
                    # 텍스트 태그가 있는지 확인
                    t_tags = list(re.finditer(r"<hp:t.*?>.*?</hp:t>", p_body, re.DOTALL))
                    if not t_tags:
                        run_match = re.search(r"(<hp:run.*?>)", p_body, re.DOTALL)
                        if run_match:
                            new_p_body = p_body.replace(run_match.group(1), run_match.group(1) + f"<hp:t>{new_val}</hp:t>")
                        else:
                            new_p_body = f"<hp:run><hp:t>{new_val}</hp:t></hp:run>" + p_body
                    else:
                        new_p_body_parts = []
                        last_end = 0
                        for i, tag in enumerate(t_tags):
                            new_p_body_parts.append(p_body[last_end:tag.start()])
                            cur_s_tag = re.match(r"(<hp:t.*?>)", tag.group(0), re.DOTALL).group(1)
                            if i == 0:
                                new_p_body_parts.append(f"{cur_s_tag}{new_val}</hp:t>")
                            else:
                                new_p_body_parts.append(f"{cur_s_tag}</hp:t>")
                            last_end = tag.end()
                        new_p_body_parts.append(p_body[last_end:])
                        new_p_body = "".join(new_p_body_parts)

                    new_p_body = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", new_p_body, flags=re.DOTALL)
                    new_full_p = p_start + new_p_body + p_end
                    
                    pending_replacements.append((target_match.start(), target_match.end(), new_full_p))
                    print(f"[*] Positional Update Target (Anchor: '{anchor}', Offset: {offset}): -> '{new_val}'")

            # 인덱스 역순으로 정렬하여 문자열 치환 (뒤쪽부터 바꿔야 앞쪽 인덱스가 유지됨)
            pending_replacements.sort(key=lambda x: x[0], reverse=True)
            for start, end, new_p in pending_replacements:
                content = content[:start] + new_p + content[end:]

        # 2. 일반 텍스트 기반 치환 처리
        # ... (생략 또는 기존 로직 유지)
        p_pattern = re.compile(r"(<hp:p.*?>)(.*?)(</hp:p>)", re.DOTALL)
        
        def replace_p(match):
            # (기존 replace_p 로직)
            p_start = match.group(1)
            p_body = match.group(2)
            p_end = match.group(3)
            
            p_body_normalized = re.sub(r"<hp:tab[^>]*?/>", "\t", p_body)
            t_pattern = re.compile(r"<hp:t.*?> (.*?) </hp:t>".replace(" ", ""), re.DOTALL)
            t_contents = t_pattern.findall(p_body_normalized)
            combined_text = "".join(t_contents)
            
            updated_text = combined_text
            modified = False
            
            for mod in ai_modifications:
                if "anchor" in mod: continue # 위치 기반은 PASS
                
                orig = mod.get('original', '').strip()
                new_val = mod.get('modified', '').strip()
                if not orig: continue
                
                if orig in updated_text:
                    updated_text = updated_text.replace(orig, new_val)
                    modified = True
                else:
                    escaped_orig = "".join([re.escape(c) + r"\s*" for c in orig]).strip(r"\s*")
                    if re.search(escaped_orig, updated_text):
                        updated_text = re.sub(escaped_orig, new_val, updated_text)
                        modified = True
            
            if modified:
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
                new_p_body = "".join(parts)
                new_p_body = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", new_p_body, flags=re.DOTALL)
                
                print(f"[*] Text Updated in XML: '{combined_text.strip()}' -> '{updated_text.strip()}'")
                return p_start + new_p_body + p_end
            
            return match.group(0)

        content = p_pattern.sub(replace_p, content)

        if content != original_content:
            with open(xml_path, "w", encoding="UTF-8") as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error AI-string-modifying {xml_path}: {e}")
        return False
