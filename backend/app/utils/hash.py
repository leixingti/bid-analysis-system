import hashlib


def compute_md5(file_path: str) -> str:
    """计算文件MD5哈希"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def compute_text_hash(text: str) -> str:
    """计算文本内容MD5"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()
