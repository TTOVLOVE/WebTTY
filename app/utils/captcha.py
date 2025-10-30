"""
验证码生成和验证模块
"""
import random
import string
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from flask import session
import os

class CaptchaGenerator:
    """验证码生成器"""
    
    def __init__(self, width=120, height=40, font_size=24):
        self.width = width
        self.height = height
        self.font_size = font_size
        
    def generate_code(self, length=4):
        """生成随机验证码字符串"""
        # 使用数字和大写字母，避免容易混淆的字符
        chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
        return ''.join(random.choice(chars) for _ in range(length))
    
    def create_image(self, code):
        """创建验证码图片"""
        # 创建图片
        image = Image.new('RGB', (self.width, self.height), color='white')
        draw = ImageDraw.Draw(image)
        
        # 尝试使用系统字体，如果失败则使用默认字体
        try:
            # Windows系统字体路径
            font_path = 'C:/Windows/Fonts/arial.ttf'
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, self.font_size)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # 绘制背景干扰线
        for _ in range(5):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = random.randint(0, self.width)
            y2 = random.randint(0, self.height)
            draw.line([(x1, y1), (x2, y2)], fill=self._random_color(), width=1)
        
        # 绘制验证码字符
        char_width = self.width // len(code)
        for i, char in enumerate(code):
            x = char_width * i + random.randint(5, 15)
            y = random.randint(5, 15)
            color = self._random_color()
            draw.text((x, y), char, font=font, fill=color)
        
        # 添加噪点
        for _ in range(50):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            draw.point((x, y), fill=self._random_color())
        
        return image
    
    def _random_color(self):
        """生成随机颜色"""
        return (
            random.randint(0, 150),
            random.randint(0, 150),
            random.randint(0, 150)
        )
    
    def generate_captcha(self):
        """生成验证码并返回base64编码的图片"""
        code = self.generate_code()
        image = self.create_image(code)
        
        # 将图片转换为base64
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # 将验证码存储到session中
        session['captcha_code'] = code.upper()
        
        return {
            'code': code,
            'image': f"data:image/png;base64,{image_base64}"
        }
    
    @staticmethod
    def verify_captcha(user_input):
        """验证用户输入的验证码"""
        if not user_input:
            return False
            
        stored_code = session.get('captcha_code', '').upper()
        user_code = user_input.upper().strip()
        
        # 验证后清除session中的验证码
        if 'captcha_code' in session:
            del session['captcha_code']
        
        return stored_code == user_code and stored_code != ''