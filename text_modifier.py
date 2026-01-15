import json
import os
import re
from data_extractor import FIELD_PATTERNS


def load_json_replacements(json_path):
    """
    JSON 파일에서 치환 규칙을 로드합니다.
    
    Args:
        json_path: JSON 파일 경로
        
    Returns:
        list: [{original: "...", modified: "..."}, ...] 형식의 치환 규칙 리스트
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 옵션 1: 필드명 기반 ({"신청인": "가나디", ...})
        if isinstance(data, dict) and "replacements" not in data:
            return convert_fields_to_replacements(data)
        
        # 옵션 2: replacements 배열 ([{original: ..., modified: ...}, ...])
        elif isinstance(data, dict) and "replacements" in data:
            return data["replacements"]
        
        # 옵션 3: 직접 배열
        elif isinstance(data, list):
            return data
        
        else:
            print("[!] 지원하지 않는 JSON 형식입니다.")
            return []
            
    except FileNotFoundError:
        print(f"[!] JSON 파일을 찾을 수 없습니다: {json_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"[!] JSON 파싱 오류: {e}")
        return []
    except Exception as e:
        print(f"[!] JSON 로드 중 오류: {e}")
        return []


def convert_fields_to_replacements(field_dict):
    """
    필드명 기반 딕셔너리를 치환 규칙 리스트로 변환합니다.
    
    예: {"신청인": "가나디"} -> [{"field": "신청인", "value": "가나디"}]
    
    Args:
        field_dict: 필드명-값 딕셔너리
        
    Returns:
        list: 치환 규칙 리스트
    """
    replacements = []
    
    for field_name, new_value in field_dict.items():
        replacements.append({
            "field": field_name,
            "value": str(new_value)
        })
    
    return replacements


def parse_json_string(json_string):
    """
    JSON 문자열을 파싱하여 치환 규칙을 생성합니다.
    
    Args:
        json_string: JSON 형식 문자열
        
    Returns:
        list: 치환 규칙 리스트
    """
    try:
        data = json.loads(json_string)
        
        if isinstance(data, dict) and "replacements" not in data:
            return convert_fields_to_replacements(data)
        elif isinstance(data, dict) and "replacements" in data:
            return data["replacements"]
        elif isinstance(data, list):
            return data
        else:
            return []
            
    except json.JSONDecodeError as e:
        print(f"[!] JSON 문자열 파싱 오류: {e}")
        return []

# json 필드명 기반 치환 쌍 생성
def create_smart_replacements(replacements, extracted_texts):
    """
    필드명 기반 치환을 스마트하게 원본-수정 쌍으로 변환합니다.
    
    문서에서 실제 텍스트를 찾아 매칭합니다.
    
    Args:
        replacements: 필드명 기반 치환 규칙
        extracted_texts: 문서에서 추출한 텍스트 리스트
        
    Returns:
        list: [{original: "...", modified: "..."}, ...] 형식
    """
    smart_replacements = []
    
    import re
    
    # data_extractor에서 정의한 패턴 사용
    field_patterns = FIELD_PATTERNS
    
    for replacement in replacements:
        field_name = replacement.get("field", "")
        new_value = replacement.get("value", "")
        
        # 필드명 패턴이 있으면 스마트 매칭
        if field_name in field_patterns:
            pattern = field_patterns[field_name]
            
            for text in extracted_texts:
                match = re.search(pattern, text)
                if match:
                    original_value = match.group(1).strip()
                    original_text = text
                    
                    if original_value:
                        modified_text = text.replace(original_value, new_value, 1)
                    else:
                        # 값이 비어있는 경우 (양식 파일 등), 콜론 뒤에 값을 삽입
                        if ":" in text:
                            parts = text.split(":", 1)
                            modified_text = f"{parts[0]}: {new_value}"
                        elif "：" in text:
                            parts = text.split("：", 1)
                            modified_text = f"{parts[0]}： {new_value}"
                        else:
                            modified_text = f"{text} {new_value}"
                            
                    smart_replacements.append({
                        "original": original_text,
                        "modified": modified_text
                    })
                    break
        else:
            # 패턴이 없으면 직접 값으로 사용 (하위 호환성)
            # original 필드가 있으면 그대로 사용
            if "original" in replacement:
                smart_replacements.append({
                    "original": replacement.get("original", ""),
                    "modified": replacement.get("modified", new_value)
                })
    
    return smart_replacements


# 템플릿 맵핑을 기반으로 즉시 치환 쌍 생성
def create_replacements_from_template(user_replacements, template_mappings):
    """
    템플릿에 저장된 원본 문장 정보를 바탕으로 치환 쌍을 생성합니다.
    분석 과정(Regex 검색)을 건너뛰고 템플릿 정보를 직접 신뢰합니다.
    """
    final_replacements = []
    
    # 공백을 무시하고 매칭하기 위한 정규화된 맵
    normalized_template_keys = {k.replace(" ", ""): k for k in template_mappings.keys()}
    
    for item in user_replacements:
        field_name = item.get("field", "")
        new_value = item.get("value", "")
        
        norm_field = field_name.replace(" ", "")
        
        if norm_field in normalized_template_keys:
            actual_key = normalized_template_keys[norm_field]
            original_text = template_mappings[actual_key]
            
            # [추가] 위치 기반 매핑(dict)인 경우 그대로 반환하여 main.py에서 처리하게 함
            if not isinstance(original_text, str):
                # If original_text is not a string (e.g., a dictionary for positional mapping),
                # we cannot perform string replacements. Store it as is for later processing.
                # The 'original' key will hold the non-string value, and 'modified' will be the new_value.
                final_replacements.append({
                    "original": original_text,
                    "modified": new_value, # Store new_value here, main.py will handle how to apply it
                    "field": field_name # Keep field name for context
                })
                continue
                
            # 템플릿의 실제 키가 아닌, 공백이 제거된 표준 키(norm_field)로 패턴 검색
            pattern_key = norm_field
            
            if pattern_key in FIELD_PATTERNS:
                pattern = FIELD_PATTERNS[pattern_key]
                match = re.search(pattern, original_text)
                if match:
                    # 매칭된 전체 텍스트 중 첫 번째 그룹을 값으로 간주
                    # 그룹이 없으면 전체 매치를 값으로 간주
                    original_value = match.group(1).strip() if match.groups() else match.group(0).strip()
                    
                    if original_value:
                        modified_text = original_text.replace(original_value, str(new_value), 1)
                    else:
                        # 값이 비어있는 경우
                        if ":" in original_text:
                            parts = original_text.split(":", 1)
                            modified_text = f"{parts[0]}: {new_value}"
                        elif "：" in original_text:
                            parts = original_text.split("：", 1)
                            modified_text = f"{parts[0]}： {new_value}"
                        else:
                            modified_text = str(new_value)
                    
                    final_replacements.append({
                        "original": original_text,
                        "modified": modified_text,
                        "field": field_name
                    })
                    continue

            # 패턴 매칭이 안 되거나 패턴이 없는 경우 (fallback)
            # 콜론 기반의 기본 치환 시도
            if ":" in original_text or "：" in original_text:
                sep = ":" if ":" in original_text else "："
                parts = original_text.split(sep, 1)
                modified_text = f"{parts[0]}{sep} {new_value}"
                final_replacements.append({
                    "original": original_text,
                    "modified": modified_text,
                    "field": field_name
                })
            else:
                # 최후의 수단: 전체 교체
                final_replacements.append({
                    "original": original_text,
                    "modified": str(new_value),
                    "field": field_name
                })
        else:
            print(f"[!] Warning: Field '{field_name}' not found in template.")
            
    return final_replacements

# json 처리 및 최종 수정 리스트 반환
def get_json_modifications(json_source, extracted_texts=None, is_file=True, template_mappings=None):
    """
    JSON 소스에서 치환 규칙을 가져옵니다.
    템플릿 맵핑이 제공되면 이를 우선적으로 사용합니다.
    """
    if is_file:
        replacements = load_json_replacements(json_source)
    else:
        replacements = parse_json_string(json_source)
    
    if not replacements:
        return []
        
    # 1. 템플릿 맵핑이 있는 경우 (최고속 모드)
    if template_mappings and replacements and "field" in replacements[0]:
        return create_replacements_from_template(replacements, template_mappings)
    
    # 2. 실시간 추출 텍스트가 있는 경우 (일반 스마트 모드)
    if replacements and "field" in replacements[0]:
        if extracted_texts:
            return create_smart_replacements(replacements, extracted_texts)
        else:
            print("[!] 경고: 스마트 매칭을 위해서는 extracted_texts가 필요합니다.")
            return []
    
    # 3. 이미 original-modified 형식이면 그대로 반환
    return replacements
