import subprocess
import os
import logging

logger = logging.getLogger(__name__)

def convert_to_pdf(hwpx_path: str, output_dir: str) -> str:
    """
    LibreOffice(soffice)를 사용하여 HWPX 파일을 PDF로 변환합니다.
    """
    if not os.path.exists(hwpx_path):
        logger.error(f"변환할 HWPX 파일을 찾을 수 없습니다: {hwpx_path}")
        return None

    try:
        # LibreOffice headless 변환 명령 실행
        # -env:UserInstallation=file://... : 고유 프로필 폴더 사용 (락 방지)
        temp_profile = os.path.join(output_dir, ".libreoffice_profile")
        command = [
            "libreoffice",
            "-env:UserInstallation=file://" + os.path.abspath(temp_profile),
            "--headless",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            hwpx_path
        ]
        
        logger.info(f"PDF 변환 시작: {os.path.basename(hwpx_path)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # 생성된 PDF 파일 경로 추정
        file_name = os.path.basename(hwpx_path)
        pdf_name = os.path.splitext(file_name)[0] + ".pdf"
        pdf_path = os.path.join(output_dir, pdf_name)
        
        if os.path.exists(pdf_path):
            logger.info(f"PDF 변환 성공: {pdf_path}")
            return pdf_path
        else:
            logger.error(f"PDF 파일이 생성되지 않았습니다: {pdf_path}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"LibreOffice 실행 중 오류 발생: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"PDF 변환 중 예상치 못한 오류 발생: {e}")
        return None
