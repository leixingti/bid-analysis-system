"""数据脱敏工具 - 符合《个人信息保护法》"""
import re


def mask_phone(text: str) -> str:
    return re.sub(r'(1[3-9]\d)\d{4}(\d{4})', r'\1****\2', text)


def mask_id_card(text: str) -> str:
    return re.sub(r'(\d{6})\d{8}(\d{4})', r'\1********\2', text)


def mask_bank_account(text: str) -> str:
    return re.sub(r'(\d{4})\d{8,12}(\d{4})', r'\1********\2', text)


def mask_name(name: str) -> str:
    if len(name) <= 1:
        return name
    return name[0] + '*' * (len(name) - 1)


def desensitize_text(text: str) -> str:
    text = mask_phone(text)
    text = mask_id_card(text)
    text = mask_bank_account(text)
    return text
