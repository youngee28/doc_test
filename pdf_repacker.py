import os
import logging
import zipfile
import shutil
from lxml import etree
from weasyprint import HTML

logger = logging.getLogger(__name__)

class HWPXToPDFConverter:
    def __init__(self, hwpx_path, output_dir):
        self.hwpx_path = hwpx_path
        self.output_dir = output_dir
        self.extract_path = os.path.join(output_dir, "_temp_xslt_extract")
        self.xslt_path = os.path.abspath("hwpx_to_html.xslt")

    def convert(self):
        try:
            # 1. Extract HWPX
            if os.path.exists(self.extract_path):
                shutil.rmtree(self.extract_path)
            with zipfile.ZipFile(self.hwpx_path, 'r') as zip_ref:
                zip_ref.extractall(self.extract_path)

            # 2. XSLT Transformation
            section_path = os.path.join(self.extract_path, "Contents", "section0.xml")
            header_path = os.path.join(self.extract_path, "Contents", "header.xml")
            
            # Load XML and XSLT
            xml_doc = etree.parse(section_path)
            xslt_doc = etree.parse(self.xslt_path)
            transform = etree.XSLT(xslt_doc)

            # Apply transformation (passing header.xml path, fonts_dir, and base_dir as parameters)
            header_uri = "file://" + os.path.abspath(header_path)
            fonts_dir_path = os.path.abspath("fonts")
            base_dir_path = os.path.abspath(self.extract_path)
            
            result_tree = transform(xml_doc, 
                                    header_path=etree.XSLT.strparam(header_uri),
                                    fonts_dir=etree.XSLT.strparam(fonts_dir_path),
                                    base_dir=etree.XSLT.strparam(base_dir_path))
            
            # 3. Save Temporary HTML
            base_name = os.path.splitext(os.path.basename(self.hwpx_path))[0]
            html_path = os.path.join(self.output_dir, f"{base_name}_xslt_temp.html")
            pdf_path = os.path.join(self.output_dir, f"{base_name}.pdf")
            
            with open(html_path, "wb") as f:
                f.write(etree.tostring(result_tree, pretty_print=True, method="html", encoding="UTF-8"))

            # 4. Render PDF via WeasyPrint
            logger.info(f"XSLT-WeasyPrint PDF 변환 시작: {base_name}")
            HTML(html_path).write_pdf(pdf_path)
            
            # Cleanup
            if os.path.exists(html_path): os.remove(html_path)
            shutil.rmtree(self.extract_path)
            
            return pdf_path
        except Exception as e:
            logger.error(f"XSLT PDF 변환 중 오류 발생: {e}")
            if os.path.exists(self.extract_path): shutil.rmtree(self.extract_path)
            return None

def convert_to_pdf(hwpx_path: str, output_dir: str) -> str:
    """
    XSLT + WeasyPrint 방식을 사용하여 HWPX를 PDF로 변환합니다. (Option D)
    """
    if not os.path.exists(hwpx_path):
        logger.error(f"변환할 HWPX 파일을 찾을 수 없습니다: {hwpx_path}")
        return None
    
    # 출력 폴더 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    converter = HWPXToPDFConverter(hwpx_path, output_dir)
    return converter.convert()
