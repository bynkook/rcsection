# core/section/tshape.py

"""
이 모듈은 T형 단면(TSection)의 기하학적 특성을 정의하고,
BaseSection 추상 클래스를 구현하여 관련 단면 계수를 계산합니다.
이 클래스는 불변(immutable) 객체로, 생성 시 단면 치수에 대한 유효성을 검사합니다.
모든 단위는 mm 기준입니다.
"""

from dataclasses import dataclass
from typing import Optional

from core.section.base_section import BaseSection
from core.material.material import Concrete
from core.material.material import Steel
from core.exceptions import SectionError

@dataclass(frozen=True)
class TSection(BaseSection):
    """
    Attributes:
        web_width (float): 웨브(복부)의 폭 (bw, mm). BaseSection의 'width' 계약을 이행합니다.
        height (float): 단면의 전체 높이 (h, mm).
        flange_width (float): 플랜지의 전체 폭 (bf, mm).
        flange_depth (float): 플랜지의 두께 (hf, mm).
        cover_to_stirrup (float): 콘크리트 표면에서 스터럽 표면까지의 피복두께 (mm).
        stirrup_dia (float): 스터럽의 직경 (mm).
        tension_rebar_dia (float): 인장 주철근의 직경 (mm).
        concrete (Concrete): 콘크리트 재료 객체.
        tension_steel (Steel): 인장 철근 재료 객체.
        compression_rebar_dia (Optional[float]): 압축 철근 직경 (복근보의 경우, mm).
        compression_steel (Optional[Steel]): 압축 철근 재료 객체 (복근보의 경우).
    """
    height: float
    web_width: float
    flange_width: float
    flange_depth: float
    cover_to_stirrup: float
    stirrup_dia: float
    tension_rebar_dia: float
    concrete: Concrete
    tension_steel: Steel
    compression_rebar_dia: Optional[float] = None
    compression_steel: Optional[Steel] = None

    def __post_init__(self):
        # 기하학적 값들에 대한 유효성 검사
        if not all(val >= 0 for val in [self.web_width, self.height, self.flange_width, self.flange_depth, self.cover_to_stirrup, self.stirrup_dia, self.tension_rebar_dia]):
            raise SectionError("All geometric dimensions must be non-negative.")
        if self.flange_width < self.web_width:
            raise SectionError("플랜지 폭(flange_width)은 웨브 폭(web_width)보다 크거나 같아야 합니다.")
        if self.flange_depth >= self.height:
            raise SectionError("플랜지 두께(flange_depth)는 전체 높이(height)보다 작아야 합니다.")
        if self.effective_depth <= 0:
            raise SectionError("Effective depth (d) must be positive. Check dimensions and cover.")

    @property
    def shape_code(self) -> str:
        return 't'
    
    @property
    def gross_area(self) -> float:
        """단면의 총면적 gross area (Ag)을 계산합니다."""
        flange_area = self.flange_width * self.flange_depth
        web_area = self.web_width * (self.height - self.flange_depth)
        return flange_area + web_area

    @property
    def centroid_y(self) -> float:
        """[내부용] 단면 상단으로부터 T형 단면의 도심까지의 거리(yc)를 계산합니다."""
        flange_area = self.flange_width * self.flange_depth
        web_area = self.web_width * (self.height - self.flange_depth)
        
        # 단면 상단을 기준으로 한 모멘트 계산
        flange_moment = flange_area * (self.flange_depth / 2)
        web_moment = web_area * (self.flange_depth + (self.height - self.flange_depth) / 2)
        
        return (flange_moment + web_moment) / self.gross_area

    @property
    def Ig(self) -> float:
        """T형 단면의 총단면2차모멘트(Ig)를 평행축 정리를 이용하여 계산합니다."""
        # 1. 각 사각형 부분의 자체 도심에 대한 단면2차모멘트 계산
        Ig_flange = (self.flange_width * self.flange_depth ** 3) / 12
        Ig_web = (self.web_width * (self.height - self.flange_depth) ** 3) / 12
        
        # 2. 평행축 정리를 위한 (A * d^2) 항 계산
        yc = self.centroid_y
        flange_area = self.flange_width * self.flange_depth
        web_area = self.web_width * (self.height - self.flange_depth)
        
        d_flange = abs(yc - (self.flange_depth / 2))
        d_web = abs(yc - (self.flange_depth + (self.height - self.flange_depth) / 2))
        
        Ad2_flange = flange_area * (d_flange ** 2)
        Ad2_web = web_area * (d_web ** 2)
        
        return Ig_flange + Ad2_flange + Ig_web + Ad2_web

    @property
    def effective_depth(self) -> float:
        """인장철근의 유효깊이 (d)를 계산합니다."""
        return self.height - self.cover_to_stirrup - self.stirrup_dia - (self.tension_rebar_dia / 2)

    @property
    def d_prime(self) -> Optional[float]:
        """압축철근의 유효깊이 (d')를 계산합니다."""
        if self.compression_rebar_dia is None:
            return None
        return self.cover_to_stirrup + self.stirrup_dia + (self.compression_rebar_dia / 2)

    @property
    def cracking_moment(self) -> float:
        """
        단면의 균열모멘트 (Mcr)를 계산합니다. Mcr = fr * Ig / yt
        """
        fr = self.concrete.modulus_of_rupture
        Ig = self.Ig
        # yt : 전체 단면의 도심에서 인장측 최외단까지의 거리
        yt = self.height - self.centroid_y
        
        return fr * Ig / yt

# ==============================================================================
# 사용 예시 (이 파일을 직접 실행할 경우에만 동작)
# ==============================================================================
if __name__ == '__main__':
    from core.material.material import Concrete
    from core.material.material import Steel

    c30_material = Concrete(fck=30)
    s500_material = Steel(grade="SD500")

    print("--- T형보 예시 ---")
    try:
        t_beam_section = TSection(
            web_width=400,
            height=800,
            flange_width=1000,
            flange_depth=150,
            cover_to_stirrup=40,
            stirrup_dia=10,
            tension_rebar_dia=25,
            concrete=c30_material,
            tension_steel=s500_material
        )
        
        print(f"단면 형상 코드 shape_code: '{t_beam_section.shape_code}'")
        print(f"웨브 폭 bw: {t_beam_section.web_width} mm")
        print(f"플랜지 폭 fw: {t_beam_section.flange_width} mm")
        print(f"플랜지 두께 ft: {t_beam_section.flange_depth} mm")
        print(f"단면 높이 h: {t_beam_section.height} mm")
        print(f"단면 총면적 Ag: {t_beam_section.gross_area / 100:.2f} cm^2")
        print(f"단면 도심 yc (from top): {t_beam_section.centroid_y:.2f} mm")
        print(f"단면2차모멘트 Ig: {t_beam_section.Ig / 1e4:.2f} cm^4")
        print(f"인장철근 유효깊이 d: {t_beam_section.effective_depth:.2f} mm")
        print(f"균열 모멘트 Mcr: {t_beam_section.cracking_moment / 1e6:.2f} kN.m")
    except SectionError as e:
        print(f"Error: {e}")