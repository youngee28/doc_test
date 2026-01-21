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

# 전역 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

import xml_converter
import xml_editor
import xml_repacker
import text_modifier
import pdf_repacker

# logging
# basicConfig is already done in other modules, but let's ensure it's clean here

# 폴더 경로 상수
INPUT_DIR = "input_hwpx"
OUTPUT_DIR = "output_hwpx"
TEMPLATE_DIR = "template_json"
MASTER_TEMPLATE_PATH = "master_template.json"


async def process_hwpx_document(input_hwpx, output_hwpx=None, modify_source=None, template_file=None):
    """
    HWPX 파일을 처리합니다.
    master_template.json(스키마)의 라벨을 사용하여 입력 파일에서 실제 텍스트 라인을 찾고,
    해당 라인에 대해 값 치환을 수행합니다.
    """
    file_name = os.path.basename(input_hwpx)
    file_name_no_ext = os.path.splitext(file_name)[0]
    
    # 0. 작업 디렉토리 준비 (입력 파일 추출)
    temp_dir = "extracted_xml"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    extracted_content_path = ""
    try:
        await xml_converter.extract_all_hwpx_files(input_hwpx, temp_dir)
        extracted_content_path = os.path.join(temp_dir, f"{file_name_no_ext}_xml")
    except Exception as e:
        logger.error(f"파일 추출 실패: {e}")
        return

    # 1. 문서 전체 텍스트 추출 (메모리 로드)
    # 스키마 매칭을 위해 현재 문서의 내용을 스캔합니다.
    ns = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
    all_text_lines = []
    
    xml_files = glob.glob(os.path.join(extracted_content_path, "**", "section*.xml"), recursive=True)
    for xml in xml_files:
        tree = ET.parse(xml)
        root = tree.getroot()
        for p in root.findall('.//hp:p', ns):
            def extract_all_p_text(element):
                text_parts = []
                for node in element.iter():
                    if node.tag == f"{{{ns['hp']}}}t" and node.text:
                        text_parts.append(node.text)
                    elif node.tag == f"{{{ns['hp']}}}tab":
                        text_parts.append("\t")
                    if node.tail and node != element:
                        text_parts.append(node.tail)
                return "".join(text_parts)
            para = extract_all_p_text(p).strip()
            if para: 
                all_text_lines.append(para)

    # 2. 스키마(라벨) 로드
    schema_mappings = {} # {Key: Label}
    if os.path.exists(MASTER_TEMPLATE_PATH):
        print(f"[*] 마스터 스키마 로드: {MASTER_TEMPLATE_PATH}")
        with open(MASTER_TEMPLATE_PATH, "r", encoding="UTF-8") as f:
            full_data = json_lib.load(f)
            # 매핑 값은 "신청인 :" 같은 라벨(Label) 역할
            schema_mappings = full_data.get("mappings", {})
    
    # 3. Dynamic Mapping (Label -> Actual Full Line in Input Doc)
    # 스키마의 라벨이 포함된 실제 문장을 찾아서 '진짜 template_mappings' 구축
    current_doc_mappings = {} # {Key: Actual Full Line Text}
    
    if schema_mappings:
        # "위의 사실을 증명합니다" 위치 찾기 (날짜 식별을 위한 Anchor)
        anchor_index = -1
        for i, line in enumerate(all_text_lines):
            if "위의 사실을 증명합니다" in line.replace(" ", ""):
                anchor_index = i
                break

        for field_key, label_pattern in schema_mappings.items():
            found = False

            # 작성날짜 특수 처리: Regex + Anchor 기반 정밀 탐색
            if field_key == "작성날짜":
                date_pattern = r"\d{2,4}년\s*\d{1,2}월\s*\d{1,2}일"
                
                # 1. Anchor(증명 문구) 이후 구간에서 가장 먼저 나오는 날짜 탐색
                if anchor_index != -1:
                    for i in range(anchor_index + 1, len(all_text_lines)):
                        line = all_text_lines[i]
                        if re.search(date_pattern, line) and "~" not in line:
                            current_doc_mappings[field_key] = line
                            found = True
                            break
                
                # 2. Anchor가 없거나 검색 실패 시, 전체 문서에서 마지막 날짜 줄 선택 (Fallback)
                if not found:
                    for line in reversed(all_text_lines):
                        if re.search(date_pattern, line) and "~" not in line:
                            current_doc_mappings[field_key] = line
                            found = True
                            break
            
            # 일반 필드: Label 기반 prefix 매칭
            else:
                clean_label = label_pattern.replace(" ", "").strip()
                for line in all_text_lines:
                    # 라인에서도 공백 제거 후 라벨로 시작하는지 확인 (정밀 매칭)
                    clean_line = line.replace(" ", "")
                    if clean_line.startswith(clean_label):
                        # [중요] 원본 라인(공백 포함)을 매핑 값으로 저장
                        current_doc_mappings[field_key] = line
                        found = True
                        break # 첫 번째 매칭만 사용
            
            if not found:
                 # 못 찾았다면 스키마의 값을 그대로 사용
                 current_doc_mappings[field_key] = label_pattern

    # 4. 치환 규칙 생성
    ai_modifications = []
    if modify_source:
        is_json_file = os.path.exists(modify_source) if isinstance(modify_source, str) else False
        
        # 여기서 생성한 current_doc_mappings(실제 문서 텍스트 기반)를 넘겨줍니다.
        # text_modifier는 이제 "진짜 원본 문장"을 보고 교체 규칙을 만듭니다.
        modify_data_list = text_modifier.get_json_modifications(
            modify_source, 
            is_file=is_json_file, 
            template_mappings=current_doc_mappings
        )
        
        for mod_item in modify_data_list:
            if "original" in mod_item and "modified" in mod_item:
                ai_modifications.append({
                    "original": mod_item["original"],
                    "modified": str(mod_item["modified"])
                })

    if not ai_modifications:
        print("[!] 적용할 치환 내용이 없습니다.")

    # 5. XML 수정 및 레이아웃 최적화 수행
    try:
        # print(f"[*] XML 데이터 수정 및 레이아웃 최적화 수행...")
        # (좌표/스타일 수정 로직 삭제됨)
        xml_files_content = glob.glob(os.path.join(extracted_content_path, "Contents", "section*.xml"))
        for xml_file in xml_files_content:
            
            # xml_base_path를 전달하여 header.xml 스타일 수동 수정(내어쓰기 등)이 가능하도록 함
            xml_editor.update_xml_text_content(xml_file, ai_modifications)
        
        if not output_hwpx:
            output_hwpx = os.path.join(OUTPUT_DIR, f"[수정]{file_name}")
            
        xml_repacker.repackage_hwpx(extracted_content_path, output_hwpx)
        print(f"[*] 수정 완료: {output_hwpx}")
        
        pdf_path = pdf_repacker.convert_to_pdf(output_hwpx, OUTPUT_DIR)
        if pdf_path:
            print(f"[*] PDF 생성 완료: {pdf_path}")
            
    finally:
        pass

async def main():
    for directory in [INPUT_DIR, OUTPUT_DIR]:
        os.makedirs(directory, exist_ok=True)

    parser = argparse.ArgumentParser(description="HWPX 문서 생성 엔진 (Target Search Mode)")
    parser.add_argument("--input", required=True, help="입력 HWPX 파일 경로")
    parser.add_argument("--output", help="출력 HWPX 파일 경로")
    
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--modify", help="치환 데이터 JSON 파일")
    group.add_argument("--data", help="치환 데이터 JSON 문자열")
    
    parser.add_argument("--template", help="템플릿 지정 (옵션)")

    args = parser.parse_args()
    
    input_path = args.input
    if not os.path.dirname(input_path) and not os.path.isabs(input_path):
        input_path = os.path.join(INPUT_DIR, input_path)
            
    modify_source = args.modify if args.modify else args.data

    await process_hwpx_document(input_path, args.output, modify_source, args.template)

if __name__ == "__main__":
    asyncio.run(main())
