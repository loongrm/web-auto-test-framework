"""
AI服务门面
"""
from ai.failure_analyzer import AIFailureAnalyzer
from ai.case_generator import AICaseGenerator
from ai.locator_healer import LocatorHealer

# 单例
failure_analyzer = AIFailureAnalyzer()
case_generator = AICaseGenerator()
locator_healer = LocatorHealer()