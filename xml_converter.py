import os
import zipfile
import shutil
import glob
import argparse # terminal
import asyncio
import logging

import re
import json
import xml.etree.ElementTree as ET

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# func
async def extract_hwpx_file(hwpx_path: str, output_xml_dir: str) -> bool:
    """
    주어진 HWPX 파일을 압축 해제하여 output_xml_dir에 {파일명}_xml 폴더로 저장합니다.
    (무조건 기존 폴더 삭제 후 재생성)
    """
    try:
        file_name = os.path.splitext(os.path.basename(hwpx_path))[0]
        output_dir = os.path.join(output_xml_dir, f"{file_name}_xml")

        # 기존 디렉토리 존재 시 무조건 삭제
        if os.path.exists(output_dir):
            try:
                logger.info(f"기존 디렉토리 삭제 시도: {output_dir}")
                shutil.rmtree(output_dir)
            except Exception as e:
                logger.error(f"기존 디렉토리 삭제 실패 (파일이 사용 중일 수 있음): {output_dir}\n오류: {e}")
                return False

        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"'{hwpx_path}' 압축 해제 중... -> {output_dir}")

        def _extract():
            with zipfile.ZipFile(hwpx_path, "r") as zf:
                zf.extractall(output_dir)

        await asyncio.to_thread(_extract)

        logger.info(f"'{file_name}' 압축 해제 완료!")
        return True

    except Exception as e:
        logger.error(f"'{hwpx_path}' 처리 중 오류 발생: {str(e)}", exc_info=True)
        return False


async def extract_all_hwpx_files(input_path: str, output_base_dir: str) -> bool:
    """
    input_path가 폴더면 그 안의 *.hwpx 전부 처리.
    input_path가 파일이면 그 파일만 처리.
    """
    if not os.path.exists(input_path):
        logger.error(f"입력 경로 '{input_path}'가 존재하지 않습니다.")
        return False

    os.makedirs(output_base_dir, exist_ok=True)

    # 폴더/파일 모두 지원
    if os.path.isdir(input_path):
        hwpx_files = glob.glob(os.path.join(input_path, "*.hwpx"))
    else:
        hwpx_files = [input_path] if input_path.lower().endswith(".hwpx") else []

    if not hwpx_files:
        logger.error(f"'{input_path}'에서 HWPX 파일을 찾지 못했습니다.")
        return False

    logger.info(f"HWPX 파일 {len(hwpx_files)}개 처리 시작")

    tasks = [extract_hwpx_file(p, output_base_dir) for p in hwpx_files]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    logger.info(f"압축 해제 결과: {len(hwpx_files)}개 중 {success_count}개 성공")
    return success_count == len(hwpx_files)