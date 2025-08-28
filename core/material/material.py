# core/material.py

"""
이 모듈은 콘크리트와 철근 재료의 물리적, 기계적 특성을 정의하는
데이터 클래스들을 제공합니다.

각 클래스는 불변(immutable) 객체로 설계되어 데이터의 일관성과 안정성을 보장합니다.
객체 생성 시 설계기준(KDS)에 따른 유효성 검사를 수행합니다.
모든 단위는 N, mm, MPa 기준입니다.
"""

from dataclasses import dataclass
from math import sqrt
from core.exceptions import MaterialError # <<< 사용자 정의 예외 Import

# ==============================================================================
# Module Root Level Constants
# ==============================================================================
_REBAR_SPECS = {
    "SD300": (300, 440), "SD350": (350, 490), "SD400": (400, 560), "SD500": (500, 620), "SD600": (600, 710),
    "SD400W": (400, 560), "SD500W": (500, 620)
}
# KS D 3504 : As_nom = 0.7854*d_nom^2, 유효숫자 4개
_REBAR_AREAS = {
    10: 71.33, 13: 126.7, 16: 198.6, 19: 286.5, 22: 387.1, 25: 506.7, 29: 642.4, 32: 794.2, 35: 956.6, 38: 1140.0
}

REBAR_DIA_LIST = list(_REBAR_AREAS.keys())
STEEL_ELASTIC_MODULUS = 200000

# ==============================================================================
# Material Classes
# ==============================================================================
@dataclass(frozen=True)
class Steel:
    grade: str

    def __post_init__(self):
        if self.grade not in _REBAR_SPECS:
            # ValueError -> MaterialError 로 변경
            raise MaterialError(f"Unknown rebar grade: '{self.grade}'.")
        if self.fy > 600:
            # ValueError -> MaterialError 로 변경
            raise MaterialError(f"Design yield strength (fy={self.fy} MPa) exceeds 600 MPa limit (KDS 14.20.10).")

    # --- 기본 재료 특성 ---
    @property
    def fy(self) -> float:
        """설계기준항복강도 (MPa)"""
        return _REBAR_SPECS[self.grade][0]
    
    @property
    def Es(self) -> float:
        """탄성계수 (MPa)"""
        return STEEL_ELASTIC_MODULUS

    @property
    def yield_strain(self) -> float:
        """항복변형률 (εy)"""
        return self.fy / self.Es

    # --- KDS 설계기준에 따른 변형률 한계 (fy에만 의존하므로 Steel 클래스 책임) ---
    @property
    def compression_controlled_limit_strain(self) -> float:
        """압축지배 변형률 한계(ε_ccl). 이 값은 철근의 항복변형률과 같습니다."""
        return self.yield_strain

    @property
    def tension_controlled_limit_strain(self) -> float:
        """인장지배 변형률 한계(ε_tcl). KDS 14 20 20 (4.1.2(4))"""
        return 2.5 * self.yield_strain if self.fy > 400 else 0.005

    @property
    def min_allowable_tensile_strain(self) -> float:
        """휨부재의 최소허용 순인장변형률(ε_t,min). KDS 14 20 20 (4.1.2(5))"""
        return 2.0 * self.yield_strain if self.fy > 400 else 0.004


@dataclass(frozen=True)
class Rebar:
    """단일 철근의 재료와 기하학적 특성(직경)을 정의하는 불변 객체."""
    material: Steel
    diameter: int
    
    def __post_init__(self):
        if self.diameter not in REBAR_DIA_LIST:
            # ValueError -> MaterialError 로 변경
            raise MaterialError(f"Unsupported rebar diameter: {self.diameter}mm.")

    @property
    def area(self) -> float:
        """철근의 공칭 단면적 (mm^2)"""
        return _REBAR_AREAS[self.diameter]


@dataclass(frozen=True)
class Concrete:
    """콘크리트 재료의 고유한 기계적 특성을 정의하는 불변 객체."""
    fck: float
    unit_mass: float = 2300.0
    lightweight_factor_lambda: float = 1.0

    def __post_init__(self):
        if self.fck <= 0:
            # ValueError -> MaterialError 로 변경
            raise MaterialError("fck must be a positive number.")
        if not (0.75 <= self.lightweight_factor_lambda <= 1.0):
            # ValueError -> MaterialError 로 변경
            raise MaterialError("Lightweight factor (lambda) must be between 0.75 and 1.0.")

    @property
    def fcm(self) -> float:
        """평균압축강도 (MPa). KDS 14 20 10 (4.3-3)"""
        if self.fck <= 40: return self.fck + 4.0
        if self.fck < 60: return self.fck + (4.0 + 2.0 * (self.fck - 40.0) / 20.0)
        return self.fck + 6.0

    @property
    def Ec(self) -> float:
        """할선탄성계수 (MPa). KDS 14 20 10 (4.3-1)"""
        return 0.077 * (self.unit_mass ** 1.5) * (self.fcm ** (1/3))

    @property
    def ultimate_strain(self) -> float:
        """극한변형률 (εcu). KDS 14 20 20 (4.1.1(3))"""
        if self.fck <= 40: return 0.0033
        return max(0.0033 - (self.fck - 40) / 100000, 0.0028)

    @property
    def modulus_of_rupture(self) -> float:
        """파괴계수 (fr). 경량콘크리트 계수 λ 반영. KDS 14 20 50 (4.1.2(3)①)"""
        return 0.63 * self.lightweight_factor_lambda * sqrt(self.fck)

    @property
    def beta1(self) -> float:
        """등가응력블록 깊이 계수 (β1). KDS 14 20 20 (표 4.1-2)"""
        if self.fck <= 40: return 0.80
        if self.fck < 80: return max(0.64, 0.80 - 0.04 * ((self.fck - 40) / 10))
        return 0.64

    @property
    def eta(self) -> float:
        """등가응력블록 응력 계수 (η). KDS 14 20 20 (표 4.1-2)"""
        if self.fck <= 40: return 1.00
        if self.fck < 90: return max(0.84, 1.00 - 0.03 * ((self.fck - 40) / 10))
        return 0.84