# core/helpers.py

"""
이 모듈은 core 패키지 내부의 다른 모듈들이 공통적으로 사용하는
저수준(low-level) 도우미 함수들을 제공합니다.
"""

# 프로젝트 전역에서 사용할 부동소수점 비교를 위한 허용 오차
TOLERANCE = 1e-9

def is_greater_or_equal(a: float, b: float) -> bool:
    """
    부동소수점 오차를 고려하여 a >= b 인지 안전하게 비교합니다.
    a가 b보다 크거나, 두 수의 차이가 허용 오차보다 작으면 True를 반환합니다.
    """
    return (a - b) > -TOLERANCE

def is_less_or_equal(a: float, b: float) -> bool:
    """
    부동소수점 오차를 고려하여 a <= b 인지 안전하게 비교합니다.
    a가 b보다 작거나, 두 수의 차이가 허용 오차보다 작으면 True를 반환합니다.
    """
    return (a - b) < TOLERANCE

def is_equal(a: float, b: float) -> bool:
    """
    부동소수점 오차를 고려하여 a == b 인지 안전하게 비교합니다.
    두 수의 차이의 절대값이 허용 오차보다 작으면 True를 반환합니다.
    """
    return abs(a - b) < TOLERANCE