import json
import os
import re
from data_extractor import FIELD_PATTERNS


def load_json_replacements(json_source, is_file=True):
    """
    JSON 소스(파일 경로 또는 문자열)에서 치환 규칙을 로드합니다.
    """
    try:
        if is_file:
            if not os.path.exists(json_source):
                print(f"[!] JSON 파일을 찾을 수 없습니다: {json_source}")
                return []
            with open(json_source, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json.loads(json_source)
        
        # 형식 변환: {"필드": "값"} -> [{"field": "필드", "value": "값"}]
        if isinstance(data, dict) and "replacements" not in data:
            return [{"field": k, "value": str(v)} for k, v in data.items()]
        elif isinstance(data, dict) and "replacements" in data:
            return data["replacements"]
        elif isinstance(data, list):
            return data
        return []
            
    except Exception as e:
        print(f"[!] JSON 로드 오류: {e}")
        return []


def create_smart_replacements(user_replacements, template_mappings):
    """
    템플릿 매핑 정보를 기반으로 스마트한 {원본문장: 수정문장} 쌍을 생성합니다.
    """
    final_replacements = []
    
    # 템플릿 키 정규화 (표준 비교용)
    normalized_template_keys = {k.replace(" ", ""): k for k in template_mappings.keys()}
    
    for item in user_replacements:
        field_name = item.get("field", "")
        new_value = item.get("value", "")
        
        norm_field = field_name.replace(" ", "")
        
        if norm_field in normalized_template_keys:
            actual_key = normalized_template_keys[norm_field]
            original_text = template_mappings[actual_key]
            
            # 패턴 기반 스마트 검색 (정규화된 표준 키 사용)
            pattern_key = norm_field
            modified_text = None
            
            if pattern_key in FIELD_PATTERNS:
                pattern = FIELD_PATTERNS[pattern_key]
                match = re.search(pattern, original_text)
                if match:
                    # 매칭된 값 추출 (그룹이 있으면 1번 그룹, 없으면 전체)
                    original_value = match.group(1).strip() if match.groups() else match.group(0).strip()
                    
                    if original_value:
                        modified_text = original_text.replace(original_value, str(new_value), 1)
                    else:
                        # 값이 비어있다면 콜론 삽입
                        sep = ":" if ":" in original_text else ("：" if "：" in original_text else None)
                        if sep:
                            parts = original_text.split(sep, 1)
                            modified_text = f"{parts[0]}{sep} {new_value}"
            
            # 패턴 매칭이 안 된 경우 기본 콜론 치환 시도
            if modified_text is None:
                if ":" in original_text or "：" in original_text:
                    sep = ":" if ":" in original_text else "："
                    parts = original_text.split(sep, 1)
                    modified_text = f"{parts[0]}{sep} {new_value}"
                else:
                    # 최후의 수단: 전체 교체
                    modified_text = str(new_value)
            
            final_replacements.append({
                "original": original_text,
                "modified": modified_text,
                "field": field_name
            })
        else:
            print(f"[!] Warning: Field '{field_name}' not found in template.")
            
    return final_replacements


def get_json_modifications(json_source, is_file=True, template_mappings=None):
    """
    JSON 소스에서 최종 치환 데이터 리스트를 반환합니다.
    """
    replacements = load_json_replacements(json_source, is_file)
    
    if not replacements:
        return []
        
    # 이미 original/modified 형식이면 그대로 반환
    if replacements and "original" in replacements[0]:
        return replacements
        
    # 필드명 기반이면 템플릿 정보를 활용해 스마트 매칭
    if template_mappings:
        return create_smart_replacements(replacements, template_mappings)
    
    # 템플릿 정보가 없으면 원본 리스트 그대로 반환 (마스터 템플릿 모드 등을 위함)
    # print("[!] 경고: 템플릿 정보가 없어 스마트 매칭을 수행할 수 없습니다.")
    return replacements
