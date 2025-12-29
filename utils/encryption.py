"""
数据加密工具
"""

import base64
from cryptography.fernet import Fernet


def get_encryption_key():
    """获取加密密钥"""
    try:
        from config_env import SECURITY_CONFIG
        return SECURITY_CONFIG['encryption_key']
    except ImportError:
        # 默认密钥
        return b'your-encryption-key-here-change-this-32-chars'


def get_cipher_suite():
    """获取加密套件"""
    key = get_encryption_key()
    return Fernet(base64.urlsafe_b64encode(key[:32]))


def encrypt_data(data):
    """加密数据"""
    if not data:
        return None
    
    try:
        cipher_suite = get_cipher_suite()
        return cipher_suite.encrypt(data.encode()).decode()
    except Exception as e:
        print(f"加密失败: {e}")
        return None


def decrypt_data(encrypted_data):
    """解密数据"""
    if not encrypted_data:
        return None
    
    try:
        cipher_suite = get_cipher_suite()
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        print(f"解密失败: {e}")
        return None


def generate_encryption_key():
    """生成新的加密密钥"""
    return Fernet.generate_key()