"""
加密通信模块
实现AES-256-GCM对称加密和ECDH密钥交换
"""

import os
import json
import base64
import hashlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import secrets
import logging

logger = logging.getLogger(__name__)

class EncryptionManager:
    """加密管理器，处理密钥交换和消息加密/解密"""
    
    def __init__(self):
        self.private_key = None
        self.public_key = None
        self.shared_key = None
        self.aes_key = None
        self.aesgcm = None
        self.is_initialized = False
        
    def generate_keypair(self):
        """生成ECDH密钥对"""
        try:
            self.private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
            self.public_key = self.private_key.public_key()
            logger.info("ECDH密钥对生成成功")
            return True
        except Exception as e:
            logger.error(f"生成ECDH密钥对失败: {e}")
            return False
    
    def get_public_key_bytes(self):
        """获取公钥的字节表示"""
        if not self.public_key:
            return None
        try:
            public_key_bytes = self.public_key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            return base64.b64encode(public_key_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"序列化公钥失败: {e}")
            return None
    
    def load_peer_public_key(self, peer_public_key_b64):
        """加载对方的公钥并计算共享密钥"""
        try:
            logger.info(f"[调试] 开始加载对方公钥: {peer_public_key_b64[:50]}...")
            
            # 解码对方的公钥
            peer_public_key_bytes = base64.b64decode(peer_public_key_b64)
            peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(), peer_public_key_bytes
            )
            
            logger.info("[调试] 对方公钥解码成功")
            
            # 计算共享密钥
            shared_key = self.private_key.exchange(ec.ECDH(), peer_public_key)
            logger.info(f"[调试] 共享密钥计算成功，长度: {len(shared_key)}")
            
            # 使用HKDF派生AES密钥
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # AES-256需要32字节密钥
                salt=None,
                info=b'RAT_ENCRYPTION_KEY',
                backend=default_backend()
            )
            self.aes_key = hkdf.derive(shared_key)
            self.aesgcm = AESGCM(self.aes_key)
            self.is_initialized = True
            
            logger.info("密钥交换完成，加密通道已建立")
            logger.info(f"[调试] AES密钥长度: {len(self.aes_key)}, is_initialized: {self.is_initialized}")
            return True
            
        except Exception as e:
            logger.error(f"密钥交换失败: {e}")
            return False
    
    def encrypt_message(self, message_dict):
        """加密消息"""
        if not self.is_initialized:
            raise RuntimeError("加密管理器未初始化")
        
        try:
            # 将消息转换为JSON字符串
            message_json = json.dumps(message_dict, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')
            
            # 生成随机nonce
            nonce = os.urandom(12)  # GCM推荐12字节nonce
            
            # 加密消息
            ciphertext = self.aesgcm.encrypt(nonce, message_bytes, None)
            
            # 返回加密后的数据包
            encrypted_packet = {
                'encrypted': True,
                'nonce': base64.b64encode(nonce).decode('utf-8'),
                'data': base64.b64encode(ciphertext).decode('utf-8')
            }
            
            return encrypted_packet
            
        except Exception as e:
            logger.error(f"消息加密失败: {e}")
            raise
    
    def decrypt_message(self, encrypted_packet):
        """解密消息"""
        if not self.is_initialized:
            raise RuntimeError("加密管理器未初始化")
        
        try:
            # 检查是否为加密消息
            if not encrypted_packet.get('encrypted'):
                return encrypted_packet  # 返回原始消息
            
            # 解码nonce和密文
            nonce = base64.b64decode(encrypted_packet['nonce'])
            ciphertext = base64.b64decode(encrypted_packet['data'])
            
            # 解密消息
            decrypted_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            
            # 解析JSON消息
            message_json = decrypted_bytes.decode('utf-8')
            message_dict = json.loads(message_json)
            
            return message_dict
            
        except Exception as e:
            logger.error(f"消息解密失败: {e}")
            raise
    
    def create_handshake_message(self):
        """创建握手消息"""
        if not self.public_key:
            self.generate_keypair()
        
        public_key_b64 = self.get_public_key_bytes()
        if not public_key_b64:
            return None
        
        return {
            'type': 'key_exchange',
            'public_key': public_key_b64,
            'version': '1.0'
        }
    
    def process_handshake_response(self, response):
        """处理握手响应"""
        try:
            if response.get('type') != 'key_exchange_ack':
                return False
            
            peer_public_key = response.get('public_key')
            if not peer_public_key:
                return False
            
            return self.load_peer_public_key(peer_public_key)
            
        except Exception as e:
            logger.error(f"处理握手响应失败: {e}")
            return False


class SecureSocket:
    """安全Socket包装器，提供透明的加密/解密功能"""
    
    def __init__(self, socket_obj, encryption_manager=None):
        self.socket = socket_obj
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.buffer = b''
    
    def send_encrypted(self, message_dict):
        """发送加密消息"""
        try:
            logger.info(f"[调试] 准备发送消息: {message_dict}")
            logger.info(f"[调试] 加密管理器状态 - is_initialized: {self.encryption_manager.is_initialized}")
            
            # 检查是否为密钥交换消息，如果是则发送明文
            is_key_exchange = message_dict.get('type') in ['key_exchange', 'key_exchange_ack']
            
            if self.encryption_manager.is_initialized and not is_key_exchange:
                # 加密消息
                encrypted_packet = self.encryption_manager.encrypt_message(message_dict)
                payload = json.dumps(encrypted_packet, ensure_ascii=False).encode('utf-8') + b'\n'
                logger.info(f"[调试] 发送加密消息，payload长度: {len(payload)}")
            else:
                # 如果加密未初始化或是密钥交换消息，发送明文
                payload = json.dumps(message_dict, ensure_ascii=False).encode('utf-8') + b'\n'
                logger.info(f"[调试] 发送明文消息，payload长度: {len(payload)}")
            
            self.socket.sendall(payload)
            logger.info("[调试] 消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"发送加密消息失败: {e}")
            return False
    
    def receive_encrypted(self, buffer_size=4096):
        """接收并解密消息"""
        try:
            # 接收数据
            data = self.socket.recv(buffer_size)
            if not data:
                return None
            
            self.buffer += data
            messages = []
            
            # 处理缓冲区中的完整消息
            while b'\n' in self.buffer:
                message_bytes, self.buffer = self.buffer.split(b'\n', 1)
                
                try:
                    # 解析JSON
                    message_dict = json.loads(message_bytes.decode('utf-8'))
                    
                    # 如果是加密消息且加密管理器已初始化，则解密
                    if (message_dict.get('encrypted') and 
                        self.encryption_manager.is_initialized):
                        decrypted_message = self.encryption_manager.decrypt_message(message_dict)
                        messages.append(decrypted_message)
                    else:
                        # 明文消息（握手阶段或未加密）
                        messages.append(message_dict)
                        
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.error(f"解析消息失败: {e}")
                    continue
                except Exception as e:
                    logger.error(f"解密消息失败: {e}")
                    continue
            
            # 如果有消息则返回消息列表，否则返回空列表表示需要继续接收
            return messages
            
        except Exception as e:
            logger.error(f"接收加密消息失败: {e}")
            return None
    
    def perform_key_exchange(self, is_server=False):
        """执行密钥交换"""
        try:
            if is_server:
                # 服务端：等待客户端的密钥交换请求
                messages = self.receive_encrypted()
                if not messages:
                    return False
                
                handshake_msg = messages[0]
                if handshake_msg.get('type') != 'key_exchange':
                    return False
                
                # 生成服务端密钥对
                if not self.encryption_manager.generate_keypair():
                    return False
                
                # 处理客户端公钥
                client_public_key = handshake_msg.get('public_key')
                if not self.encryption_manager.load_peer_public_key(client_public_key):
                    return False
                
                # 发送服务端公钥
                server_public_key = self.encryption_manager.get_public_key_bytes()
                response = {
                    'type': 'key_exchange_ack',
                    'public_key': server_public_key,
                    'status': 'success'
                }
                
                return self.send_encrypted(response)
                
            else:
                # 客户端：发起密钥交换
                handshake_msg = self.encryption_manager.create_handshake_message()
                if not handshake_msg:
                    return False
                
                # 发送握手消息
                if not self.send_encrypted(handshake_msg):
                    return False
                
                # 等待服务端响应
                messages = self.receive_encrypted()
                if not messages:
                    return False
                
                response = messages[0]
                return self.encryption_manager.process_handshake_response(response)
                
        except Exception as e:
            logger.error(f"密钥交换失败: {e}")
            return False
    
    def close(self):
        """关闭Socket"""
        try:
            self.socket.close()
        except:
            pass
    
    def settimeout(self, timeout):
        """设置Socket超时"""
        return self.socket.settimeout(timeout)
    
    def shutdown(self, how):
        """关闭Socket连接"""
        return self.socket.shutdown(how)
    
    def getsockname(self):
        """获取Socket名称"""
        return self.socket.getsockname()
    
    def getpeername(self):
        """获取对端Socket名称"""
        return self.socket.getpeername()
    
    def fileno(self):
        """获取Socket文件描述符"""
        return self.socket.fileno()
    
    def setsockopt(self, level, optname, value):
        """设置Socket选项"""
        return self.socket.setsockopt(level, optname, value)
    
    def getsockopt(self, level, optname):
        """获取Socket选项"""
        return self.socket.getsockopt(level, optname)


def create_secure_socket(socket_obj):
    """创建安全Socket包装器"""
    return SecureSocket(socket_obj)