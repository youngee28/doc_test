import os
import zipfile
import shutil
import glob
import argparse
import asyncio
import logging
import re
from datetime import datetime
import json as json_lib
import xml.etree.ElementTree as ET

import xml_converter
import xml_editor
import xml_repacker
import text_modifier
import data_extractor
import pdf_repacker

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# 폴더 경로 상수
INPUT_DIR = "input_hwpx"
OUTPUT_DIR = "output_hwpx"
TEMPLATE_DIR = "template_json"

async def process_hwpx_document(input_hwpx, output_hwpx=None, modify_source=None, template_file=None):
    """
    HWPX 파일에서 텍스트를 추출하거나 템플릿을 사용하여 수정합니다.
    """
    file_name = os.path.basename(input_hwpx)
    file_name_no_ext = os.path.splitext(file_name)[0]
    
    # 1. 문서 분석 및 템플릿 준비
    # 1-1. 기존 템플릿 로드 시도
    # --template이 없더라도 파일명 기반의 기본 템플릿이 있으면 자동으로 읽어오도록 개선
    default_template = os.path.join(TEMPLATE_DIR, f"template_{file_name_no_ext}.json")
    template_to_use = template_file if template_file else (default_template if os.path.exists(default_template) else None)
    
    template_mappings = None
    all_text_for_analysis = []
    
    if template_to_use and os.path.exists(template_to_use):
        print(f"[*] [명시적 모드] 템플릿을 사용하여 분석 생략: {template_to_use}")
        try:
            with open(template_to_use, "r", encoding="UTF-8") as f:
                template_data = json_lib.load(f)
                template_mappings = template_data.get("mappings")
                all_text_for_analysis = template_data.get("all_text", [])
        except Exception as e:
            print(f"[!] 템플릿 로드 실패, 직접 분석으로 전환합니다: {e}")
    
    # 1-2. 템플릿 정보가 없는 경우 직접 분석 및 생성
    if not template_mappings:
        print("[*] [분석 모드] 템플릿 정보가 없으므로 문서를 직접 분석합니다.")
        # 분석용 폴더명도 extracted_xml로 통일
        temp_dir = "extracted_xml"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        try:
            await xml_converter.extract_all_hwpx_files(input_hwpx, temp_dir)
            extracted_content_path = os.path.join(temp_dir, f"{file_name_no_ext}_xml")
            
            # HWPX Namespaces
            ns = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
            xml_files = glob.glob(os.path.join(extracted_content_path, "**", "section*.xml"), recursive=True)
            xml_files.sort()

            for xml in xml_files:
                tree = ET.parse(xml)
                root = tree.getroot()
                for p in root.findall('.//hp:p', ns):
                    # 모든 자식 노드에서 텍스트와 탭을 취합하는 로직 (그림 설명 등 메타데이터 제외)
                    def extract_all_p_text(element):
                        text_parts = []
                        # 모든 자식 노드를 순차적으로 탐색 (iter()는 자신 포함 모든 자손 순회)
                        for node in element.iter():
                            # hp:t 태그 처리
                            if node.tag == f"{{{ns['hp']}}}t":
                                if node.text:
                                    text_parts.append(node.text)
                            # hp:tab 태그 처리
                            elif node.tag == f"{{{ns['hp']}}}tab":
                                text_parts.append("\t")
                            
                            # [중요] 모든 자식 노드의 tail을 체크해야 합니다.
                            # hp:tab이나 hp:t 뒤에 바로 텍스트가 오는 경우 tail에 들어있을 수 있습니다.
                            if node.tail and node != element:
                                text_parts.append(node.tail)
                                
                        return "".join(text_parts)
                    
                    para_text = extract_all_p_text(p).strip()
                    if not para_text:
                        continue
                    
                    all_text_for_analysis.append(para_text)
            
            # 분석 기반 템플릿 저장
            template_mappings = {}
            kv_data = data_extractor.extract_kv_data(all_text_for_analysis)
            
            for field, value in kv_data.items():
                if field in data_extractor.FIELD_PATTERNS:
                    pattern = data_extractor.FIELD_PATTERNS[field]
                    for text in reversed(all_text_for_analysis):
                        if re.search(pattern, text):
                            template_mappings[field] = text
                            break
            
            new_template_path = os.path.join(TEMPLATE_DIR, f"template_{file_name_no_ext}.json")
            with open(new_template_path, "w", encoding="UTF-8") as tf:
                json_lib.dump({
                    "all_text": all_text_for_analysis,
                    "mappings": template_mappings
                }, tf, ensure_ascii=False, indent=4)
            print(f"[*] 분석 기반 템플릿을 생성했습니다: {new_template_path}")
            
            print(f"[*] Extracting structured data from {file_name}...")
            print("\n=== 추출된 데이터 (KV) ===")
            print(json_lib.dumps(kv_data, ensure_ascii=False, indent=4))
            print("=========================\n")

        finally:
            # 분석 모드인 경우 여기서 폴더를 지울지 결정 (일단 분석 모드는 기존과 동일하게 유지 가능)
            pass

    if not modify_source:
        print("[*] 치환 데이터가 입력되지 않아 분석 및 템플릿 생성만 수행합니다.")
        return

    # 2. 치환 규칙(Mapping) 생성
    print("[*] 치환 규칙을 생성하는 중...")
    
    # modify_source가 파일인지 일반 문자열인지 판별
    is_json_file = os.path.exists(modify_source) if isinstance(modify_source, str) else False
    
    modify_data = text_modifier.get_json_modifications(
        modify_source, 
        is_file=is_json_file,
        template_mappings=template_mappings
    )
    
    if not modify_data:
        print("[!] 치환할 내용을 찾지 못했습니다.")
        return

    ai_modifications = []
    
    for mod_item in modify_data:
        # mod_item: {'original': ..., 'modified': ..., 'field': ...}
        field = mod_item.get("field", "")
        new_value = mod_item.get("modified", "") # text_modifier가 이미 레이블 포함하여 생성함
        mapping_info = mod_item.get("original", "")
        
        # 일반 텍스트 매핑인 경우: text_modifier가 제공한 값을 그대로 사용
        if isinstance(mapping_info, str) and mapping_info:
            ai_modifications.append({
                "original": mapping_info,
                "modified": str(new_value)
            })
        else:
            print(f"[!] Warning: Field '{field}' not found or invalid mapping.")

    # 편집용 폴더 생성 (고정 이름: extracted_xml)
    temp_proc_dir = "extracted_xml"
    if os.path.exists(temp_proc_dir):
        shutil.rmtree(temp_proc_dir)
    os.makedirs(temp_proc_dir, exist_ok=True)

    try:
        # 3. XML 공정
        # 3-1. HWPX 파일 압축 해제
        await xml_converter.extract_all_hwpx_files(input_hwpx, temp_proc_dir)
        extracted_xml_path = os.path.join(temp_proc_dir, f"{file_name_no_ext}_xml")
        
        # 3-2. XML 파일 내용 치환
        print(f"[*] XML 수정을 시작합니다. ({len(ai_modifications)}개 항목)")
        xml_files = glob.glob(os.path.join(extracted_xml_path, "Contents", "section*.xml"))
        for xml_file in xml_files:
            xml_editor.update_xml_text_content(xml_file, ai_modifications)
        
        # 4. 최종 재패키징 및 저장
        if not output_hwpx:
            output_hwpx = os.path.join(OUTPUT_DIR, f"[수정]{file_name}")
            
        xml_repacker.repackage_hwpx(extracted_xml_path, output_hwpx)
        print(f"[*] 수정 완료: {output_hwpx}")
        
        # 5. PDF 자동 변환 (신규 공정)
        # 수정된 HWPX 파일을 즉시 PDF로 변환하여 사용자 편의성을 높입니다.
        pdf_path = pdf_repacker.convert_to_pdf(output_hwpx, OUTPUT_DIR)
        if pdf_path:
            print(f"[*] PDF 생성 완료: {pdf_path}")
        
    finally:
        # XML 자동 삭제 로직
        # if os.path.exists(temp_proc_dir):
        #     shutil.rmtree(temp_proc_dir)
        # print(f"[*] XML 확인을 위해 폴더를 유지합니다: {temp_proc_dir}")
        pass

async def main():
    # 필요 폴더 자동 생성
    for directory in [INPUT_DIR, OUTPUT_DIR, TEMPLATE_DIR]:
        os.makedirs(directory, exist_ok=True)

    parser = argparse.ArgumentParser(description="HWPX 텍스트 치환 도구")
    parser.add_argument("--input", required=True, help="입력 HWPX 파일 경로 (파일명만 입력 시 input_hwpx 폴더에서 찾음)")
    parser.add_argument("--output", help="출력 HWPX 파일 경로")
    
    # modify와 data는 상호 배타적 (템플릿 생성만 원할 경우 생략 가능)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--modify", help="치환 규칙 JSON 파일 경로")
    group.add_argument("--data", help="치환 규칙 JSON 문자열")
    
    # 템플릿 사용 옵션
    parser.add_argument("--template", help="사용할 템플릿 JSON 파일 경로")

    args = parser.parse_args()
    
    # 입력 파일 경로 처리: 파일명만 있는 경우 INPUT_DIR 결합
    input_path = args.input
    if not os.path.dirname(input_path) and not os.path.isabs(input_path):
        input_path = os.path.join(INPUT_DIR, input_path)
    
    modify_source = args.modify if args.modify else args.data
    
    await process_hwpx_document(
        input_hwpx=input_path, 
        output_hwpx=args.output, 
        modify_source=modify_source,
        template_file=args.template
    )

if __name__ == "__main__":
    asyncio.run(main())
