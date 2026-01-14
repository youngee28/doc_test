import re
import json

# 공통 정규표현식 패턴 정의
# 키 사이에 임의의 공백(\s*)을 허용하도록 설계
FIELD_PATTERNS = {
    "신청인": r"신\s*청\s*인\s*[:：]\s*([^\n]*)",
    "주민등록번호": r"주민등록번호\s*[:：]\s*([0-9\-\s]*)",
    "주소지": r"주\s*소\s*지\s*[:：]\s*([^\n]*)",
    "용역기간": r"용\s*역\s*기\s*간\s*[:：]\s*([^\n]*)",
    "용역내용": r"용\s*역\s*내\s*용\s*[:：]\s*([^\n]*)",
    "용도": r"용\s*도\s*[:：]\s*([^\n]*)",
    "작성날짜": r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일|20XX년\s*X월\s*X일)"
}

def extract_kv_data(text_list):
    """
    문단 텍스트 리스트에서 키-값 데이터를 추출합니다.
    """
    extracted_data = {}
    
    # 모든 텍스트를 하나로 합침 (줄바꿈 포함)
    full_text = "\n".join(text_list)
    
    for key, pattern in FIELD_PATTERNS.items():
        if key == "작성날짜":
            matches = re.findall(pattern, full_text)
            if matches:
                extracted_data[key] = matches[-1].strip()
            continue

        match = re.search(pattern, full_text, re.MULTILINE)
        if match:
            value = match.group(1).strip() if match.groups() else match.group(0).strip()
            # 만약 추출된 값이 다른 필드명을 포함하고 있다면 (Greedy Match 방지)
            for other_key in FIELD_PATTERNS.keys():
                if other_key != key and other_key in value:
                    # 다음 필드명 이전까지만 잘라냄
                    value = value.split(other_key)[0].strip()
                    break
            extracted_data[key] = value
            
    return extracted_data

