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
        print(f"加密数据长度: {len(encrypted_data)}")
        print(f"加密数据前32字符: {encrypted_data[:32]}")
        print(f"当前加密密钥前16字节: {get_encryption_key()[:16]}")
        return None


def generate_encryption_key():
    """生成新的加密密钥"""
    return Fernet.generate_key()


def test_encryption():
    """测试加密解密功能"""
    test_data = "test_api_key_12345"
    try:
        # 尝试加密
        encrypted = encrypt_data(test_data)
        if not encrypted:
            return "加密失败"
        
        # 尝试解密
        decrypted = decrypt_data(encrypted)
        if decrypted == test_data:
            return "加密解密功能正常"
        else:
            return f"解密结果不匹配: 期望'{test_data}', 实际'{decrypted}'"
            
    except Exception as e:
        return f"加密测试异常: {e}"