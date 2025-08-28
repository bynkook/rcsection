# core/section/rectangular.py

"""
이 모듈은 사각형 단면(RectangularSection)의 기하학적 특성을 정의하고,
BaseSection 추상 클래스를 구현하여 관련 단면 계수를 계산합니다.
이 클래스는 불변(immutable) 객체로, 생성 시 단면 치수에 대한 유효성을 검사합니다.
모든 단위는 mm 기준입니다.
"""

from dataclasses import dataclass, field
from typing import Optional

from core.section.base_section import BaseSection
from core.material.material import Concrete
from core.material.material import Steel
from core.exceptions import SectionError

@dataclass(frozen=True)
class RectangularSection(BaseSection):
    """
    Attributes:
        width (float): 단면의 폭 (b, mm). 사각형 단면에서는 이 값이 웨브 폭(bw)과 같습니다.
        height (float): 단면의 전체 높이 (h, mm).
        cover (float): 콘크리트 표면에서 스터럽(띠철근) 표면까지의 피복두께 (mm).
        stirrup_dia (float): 스터럽의 직경 (mm).
        tension_rebar_dia (float): 인장 주철근의 직경 (mm).
        concrete (Concrete): 콘크리트 재료 객체.
        tension_steel (Steel): 인장 철근 재료 객체.
        compression_rebar_dia (Optional[float]): 압축 철근 직경 (복근보의 경우, mm).
        compression_steel (Optional[Steel]): 압축 철근 재료 객체 (복근보의 경우).
    """
    width: float
    height: float
    cover_to_stirrup: float
    stirrup_dia: float
    tension_rebar_dia: float
    concrete: Concrete
    tension_steel: Steel
    compression_rebar_dia: Optional[float] = None
    compression_steel: Optional[Steel] = None

    def __post_init__(self):
        # 기하학적 값들에 대한 유효성 검사
        if not all(val >= 0 for val in [self.width, self.height, self.cover_to_stirrup, self.stirrup_dia, self.tension_rebar_dia]):
            raise SectionError("All geometric dimensions must be non-negative.")
        if self.effective_depth <= 0:
            raise SectionError("Effective depth (d) must be positive. Check dimensions and cover.")

    @property
    def shape_code(self) -> str:
        return 'r'

    @property
    def gross_area(self) -> float:
        """단면의 총면적 gross area (Ag)을 계산합니다."""
        return self.width * self.height

    @property
    def Ig(self) -> float:
        """단면2차모멘트(Ig)를 계산합니다."""
        return (self.width * self.height ** 3) / 12

    @property
    def effective_depth(self) -> float:
        """인장철근의 유효깊이 (d)를 계산합니다."""
        return self.height - self.cover_to_stirrup - self.stirrup_dia - (self.tension_rebar_dia / 2)

    @property
    def d_prime(self) -> Optional[float]:
        """압축철근의 유효깊이 (d')를 계산합니다. 압축철근이 없으면 None을 반환합니다."""
        if self.compression_rebar_dia is None:
            return None
        return self.cover_to_stirrup + self.stirrup_dia + (self.compression_rebar_dia / 2)

    @property
    def cracking_moment(self) -> float:
        """
        단면의 균열모멘트 (Mcr)를 계산합니다.
        Mcr = fr * Ig / yt
        [V2.1 수정] 이제 self.Ig 속성을 직접 사용합니다.
        """
        fr = self.concrete.modulus_of_rupture
        Ig = self.Ig
        yt = self.height / 2
        
        return fr * Ig / yt

# ==============================================================================
# 사용 예시 (이 파일을 직접 실행할 경우에만 동작)
# ==============================================================================
if __name__ == '__main__':
    from core.material.material import Concrete
    from core.material.material import Steel

    # 1. 재료 정의
    c24_material = Concrete(fck=24)
    s400_material = Steel(grade="SD400")

    print("--- 단철근보 예시 ---")
    # 2. 단면 객체 생성
    beam_section = RectangularSection(
        width=400, height=600,
        cover_to_stirrup=50,
        stirrup_dia=13,
        tension_rebar_dia=25,
        concrete=c24_material,
        tension_steel=s400_material
    )
    
    print(f"단면 형상 코드 shape_code: '{beam_section.shape_code}'")
    print(f"단면 폭 w: {beam_section.width} mm")
    print(f"단면 높이 h: {beam_section.height} mm")
    print(f"단면 총면적 Ag: {beam_section.gross_area / 100:.2f} cm^2")
    print(f"단면2차모멘트 Ig: {beam_section.Ig / 1000:.2f} cm^4")
    print(f"인장철근 유효깊이 d: {beam_section.effective_depth:.2f} mm")
    print(f"철근 항복강도 fy: {beam_section.tension_steel.fy} MPa")
    print(f"콘크리트 파괴계수 fr: {beam_section.concrete.modulus_of_rupture:.2f} MPa")
    print(f"균열 모멘트 Mcr: {beam_section.cracking_moment / 1e6:.2f} kN.m")
    
    print("\n--- 복철근보 예시 ---")
    c30_material = Concrete(fck=30)
    s500_material = Steel(grade="SD500")
    doubly_reinforced_beam = RectangularSection(
        width=400,
        height=600,
        cover_to_stirrup=50,
        stirrup_dia=13,
        tension_rebar_dia=29,
        concrete=c30_material,
        tension_steel=s500_material,
        compression_rebar_dia=25,
        compression_steel=s400_material
    )
    print(f"압축철근 유효깊이 d': {doubly_reinforced_beam.d_prime:.2f} mm")