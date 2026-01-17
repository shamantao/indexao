# Core logic for language detection and path handling
import re

def is_chinese_content(text: str, threshold: float = 0.05) -> bool:
    """
    Detect if the content is primarily Chinese/CJK based on character ratio.
    """
    if not text:
        return False
        
    # Range for CJK Unified Ideographs
    # 4E00-9FFF is the main block for common CJK characters
    cjk_pattern = re.compile(r'[\u4e00-\u9fff]')
    cjk_chars = cjk_pattern.findall(text)
    
    ratio = len(cjk_chars) / len(text)
    return ratio > threshold
