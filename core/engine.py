# core/engine.py

from dataclasses import dataclass
from core.material.material import Concrete, Steel
from core.section.base_section import BaseSection
from core.section.rectangular import RectangularSection
from core.section.tshape import TSection
import core.constants as const
from core.exceptions import DuctilityError, MinReinforcementError, SectionCapacityError
# [수정됨] import 경로 변경 (utils -> helpers)
from core.helpers import is_greater_or_equal, is_less_or_equal, is_equal

# ==============================================================================
# 결과 반환을 위한 데이터 클래스 정의
# ==============================================================================
@dataclass(frozen=True)
class AnalysisResult:
    """단면 해석의 저수준(low-level) 결과를 담는 내부용 데이터 클래스."""
    c: float
    net_tensile_strain: float
    phi: float
    phi_mn: float

@dataclass(frozen=True)
class CapacityResult:
    """단면의 '최대 성능' 검토 결과를 담는 데이터 클래스."""
    as_max: float
    max_phi_mn: float
    analysis_result: AnalysisResult

@dataclass(frozen=True)
class DesignResult:
    """'설계' (소요 철근량 계산) 결과를 담는 데이터 클래스."""
    as_required: float
    as_min: float
    as_max: float
    is_min_rebar_controlled: bool
    analysis_result: AnalysisResult

@dataclass(frozen=True)
class CheckResult:
    """'검토' (기존 단면 적정성) 결과를 담는 데이터 클래스."""
    is_ok: bool
    strength_ok: bool
    ductility_ok: bool
    min_rebar_ok: bool
    analysis_result: AnalysisResult

# ==============================================================================
# 설계 엔진 클래스
# ==============================================================================
class DesignEngine:
    """
    콘크리트 휨부재의 해석, 설계, 검토를 수행하는 핵심 엔진 클래스.
    모든 계산은 N, mm 단위를 기준으로 하며, 축력은 압축이 양수(+)입니다.
    
    [V2.1] 사각형(Rectangular) 및 T형(T-Shape) 단면을 지원합니다.
    """

    def get_maximum_capacity(self, section: BaseSection, pu: float = 0.0) -> CapacityResult:
        """
        주어진 단면의 최대 설계휨강도(φMn,max)를 계산합니다.
        단면에 작용하는 축방향력을 고려합니다.
        """
        self._check_axial_load_limit(section, pu)
        
        conc = section.concrete
        steel = section.tension_steel

        et_min = steel.min_allowable_tensile_strain
        c_max = (conc.ultimate_strain / (conc.ultimate_strain + et_min)) * section.effective_depth
        a_max = conc.beta1 * c_max
        
        if isinstance(section, TSection):            
            if is_less_or_equal(a_max, section.flange_depth):
                Cc = conc.eta * 0.85 * conc.fck * a_max * section.flange_width
            else:
                Ccf = conc.eta * 0.85 * conc.fck * (section.flange_width - section.web_width) * section.flange_depth
                Ccw = conc.eta * 0.85 * conc.fck * section.web_width * a_max
                Cc = Ccf + Ccw
        else:
            Cc = conc.eta * 0.85 * conc.fck * a_max * section.width

        # 힘의 평형(T = Cc + Pu)으로부터 As_max 계산
        As_max = (Cc + pu) / steel.fy
        
        if As_max < 0:
            raise SectionCapacityError("인장력이 너무 커서 휨 저항을 위한 인장철근 배치가 불가능합니다.")

        result = self._analyze_section(section, As_max, pu)
        
        return CapacityResult(as_max=As_max, max_phi_mn=result.phi_mn, analysis_result=result)

    def design_flexural_reinforcement(self, section: BaseSection, mu: float, pu: float = 0.0) -> DesignResult:
        """
        [최적화됨] 주어진 계수휨모멘트(mu)와 계수축력(pu)에 저항하기 위해 필요한 
        소요 철근량을 계산합니다.
        """
        if mu < 0: raise ValueError("계수휨모멘트(mu)는 0보다 큰 양수여야 합니다.")
        self._check_axial_load_limit(section, pu)
        
        max_capacity = self.get_maximum_capacity(section, pu)
        As_max = max_capacity.as_max
        max_phi_mn = max_capacity.max_phi_mn
        
        mcr_check_val = const.MIN_FLEXURAL_STRENGTH_FACTOR * section.cracking_moment
        As_min = 0.0
        if mcr_check_val > 0:
             As_min = self._find_as_for_mu(section, mcr_check_val, pu, As_max)
        
        if not is_less_or_equal(mu, max_phi_mn):
            raise SectionCapacityError(f"설계 불가: 요구 휨강도({mu/1e6:.2f} kNm)가 단면의 최대 저항 강도({max_phi_mn/1e6:.2f} kNm)를 초과합니다.")

        as_strength = self._find_as_for_mu(section, mu, pu, As_max)
        
        as_required = max(as_strength, As_min)
        is_min_controlled = is_greater_or_equal(as_required, As_min) and not is_equal(as_required, as_strength)
        
        result = self._analyze_section(section, as_required, pu)

        return DesignResult(
            as_required=as_required, 
            as_min=As_min,
            as_max=As_max,
            is_min_rebar_controlled=is_min_controlled,
            analysis_result=result
        )

    def check_section_adequacy(self, section: BaseSection, as_provided: float, mu: float, pu: float = 0.0) -> CheckResult:
        """배근된 철근량이 주어진 하중에 대해 적합한지 검토하고, '상세 보고서'를 반환합니다."""
        if as_provided < 0: raise ValueError("배근된 철근량(as_provided)은 0 이상이어야 합니다.")

        analysis_result = self._analyze_section(section, as_provided, pu)
        steel = section.tension_steel
        
        # 부동소수점 오차 문제로 전역 tolerance 적용한 함수를 사용하여 안전하게 비교
        strength_ok = is_greater_or_equal(analysis_result.phi_mn, mu)
        ductility_ok = is_greater_or_equal(analysis_result.net_tensile_strain, steel.min_allowable_tensile_strain)
        mcr_check_val = const.MIN_FLEXURAL_STRENGTH_FACTOR * section.cracking_moment
        min_rebar_ok = is_greater_or_equal(analysis_result.phi_mn, mcr_check_val)
        
        is_ok = all([strength_ok, ductility_ok, min_rebar_ok])

        return CheckResult(
            is_ok=is_ok,
            strength_ok=strength_ok,
            ductility_ok=ductility_ok,
            min_rebar_ok=min_rebar_ok,
            analysis_result=analysis_result
            )
    
    def check_section_adequacy_or_raise(self, section: BaseSection, as_provided: float, mu: float, pu: float = 0.0) -> None:
        """배근된 철근량이 주어진 하중에 대해 적합한지 검토하고, 실패 시 원인에 맞는 예외를 발생시킵니다."""
        check_result = self.check_section_adequacy(section, as_provided, mu, pu)
        if check_result.is_ok: return

        if not check_result.ductility_ok:
            raise DuctilityError(et=check_result.analysis_result.net_tensile_strain, et_min=section.tension_steel.min_allowable_tensile_strain)
        if not check_result.strength_ok:
            raise SectionCapacityError(f"강도 부족: 설계강도(φMn={check_result.analysis_result.phi_mn/1e6:.2f} kNm)가 요구강도(Mu={mu/1e6:.2f} kNm)보다 작습니다.")
        if not check_result.min_rebar_ok:
            mcr_check_val = const.MIN_FLEXURAL_STRENGTH_FACTOR * section.cracking_moment
            raise MinReinforcementError(phi_mn=check_result.analysis_result.phi_mn, mcr_check_val=mcr_check_val)

    def _get_max_axial_capacity(self, section: BaseSection, assumed_rho: float = 0.01) -> float:
        """[내부용] 단면의 최대 설계압축강도(φPn,max)를 계산합니다. KDS 14 20 20 (4.1-17)"""
        # 단면의 축방향 주철근 단면적은 0.01Ag 로 가정한다
        conc, steel = section.concrete, section.tension_steel
        Ag, Ast = section.gross_area, assumed_rho * section.gross_area
        phi = const.PHI_COMPRESSION_CONTROLLED_TIED
        Pn_max_nominal = 0.85 * conc.fck * (Ag - Ast) + steel.fy * Ast
        return 0.80 * phi * Pn_max_nominal
    
    def _check_axial_load_limit(self, section: BaseSection, pu: float) -> None:
        """[내부용] 입력된 축력이 단면의 최대 저항 능력을 초과하는지 검사합니다."""
        if pu > 0: # 압축력일 경우에만 검사
            max_pu_limit = self._get_max_axial_capacity(section)
            if pu > max_pu_limit:
                raise SectionCapacityError(f"계수압축력(pu={pu/1000:.2f}kN)이 단면의 최대 저항 가능 압축강도({max_pu_limit/1000:.2f}kN)를 초과합니다.")

    def _find_as_for_mu(self, section: BaseSection, target_mu: float, pu: float, as_upper_bound: float) -> float:
        """[내부용] 주어진 target_mu를 만족하는 As를 이진 탐색으로 찾습니다."""        
        
        if target_mu < 0: raise ValueError("계수휨모멘트(mu)는 0보다 큰 양수여야 합니다.")
        
        as_lower_bound, as_upper_bound_search = 0.0, as_upper_bound
        for _ in range(100):
            as_guess = (as_lower_bound + as_upper_bound_search) / 2.0
            if as_upper_bound_search - as_lower_bound < 1e-9: break
            analysis_result = self._analyze_section(section, as_guess, pu)
            if analysis_result.phi_mn < target_mu:
                as_lower_bound = as_guess
            else:
                as_upper_bound_search = as_guess
        return as_upper_bound_search
    
    # --------------------------------------------------------------------------
    # [V2.1 추가] 공통 로직을 위한 유틸리티 메서드
    # --------------------------------------------------------------------------
    def _calculate_phi(self, steel: Steel, et: float) -> float:
        """[내부용] 주어진 변형률(et)에 따라 강도감소계수(φ)를 계산합니다."""
        e_ccl = steel.compression_controlled_limit_strain
        e_tcl = steel.tension_controlled_limit_strain
        
        if is_greater_or_equal(et, e_tcl):
            return const.PHI_TENSION_CONTROLLED
        elif is_less_or_equal(et, e_ccl):
            return const.PHI_COMPRESSION_CONTROLLED_TIED
        else:
            return const.PHI_COMPRESSION_CONTROLLED_TIED + \
                   (const.PHI_TENSION_CONTROLLED - const.PHI_COMPRESSION_CONTROLLED_TIED) * \
                   (et - e_ccl) / (e_tcl - e_ccl)

    # --------------------------------------------------------------------------
    # [V2.1 수정] 핵심 해석 함수 (Type Dispatcher)
    # --------------------------------------------------------------------------
    def _analyze_section(self, section: BaseSection, As: float, Pu: float, As_prime: float = 0.0) -> AnalysisResult:
        """[내부용] 주어진 철근량과 축력에 대해 단면의 설계휨강도를 해석합니다."""
        if As_prime > 0:
            raise NotImplementedError("복근보 해석 로직은 아직 구현되지 않았습니다.")

        if isinstance(section, RectangularSection):
            return self._analyze_rectangular(section, As, Pu)
        elif isinstance(section, TSection):
            return self._analyze_tsection(section, As, Pu)
        else:
            raise NotImplementedError(f"해석이 지원되지 않는 단면 타입입니다: {type(section)}")

    def _analyze_rectangular(self, section: RectangularSection, As: float, Pu: float) -> AnalysisResult:
        """[내부용] 사각형 단면을 해석합니다."""
        conc, steel = section.concrete, section.tension_steel
        b, d, h = section.width, section.effective_depth, section.height
        
        # 힘의 평형 Cc = T - Pu -> c = (As*fy - Pu) / (...)
        numerator = As * steel.fy - Pu
        denominator = conc.eta * 0.85 * conc.fck * conc.beta1 * b
        if abs(denominator) < 1e-9:
            raise SectionCapacityError("단면 정보가 유효하지 않습니다 (b=0 또는 fck=0).")
        c = numerator / denominator
        
        if c <= 0:
            raise SectionCapacityError("중립축이 단면 외부에 있어 휨 해석이 불가능합니다.")

        et = conc.ultimate_strain * (d - c) / c
        phi = self._calculate_phi(steel, et)
        
        a = conc.beta1 * c
        Cc = conc.eta * 0.85 * conc.fck * a * b
        Mn = Cc * (d - a / 2) + Pu * (d - h / 2)

        return AnalysisResult(c=c, net_tensile_strain=et, phi=phi, phi_mn=phi * Mn)

    def _analyze_tsection(self, section: TSection, As: float, Pu: float) -> AnalysisResult:
        """[내부용] T형 단면을 해석합니다."""
        conc, steel = section.concrete, section.tension_steel
        bw, d, h = section.web_width, section.effective_depth, section.height
        bf, hf = section.flange_width, section.flange_depth

        # STEP 1: 중립축이 플랜지 내에 있다고 가정하고 c 계산
        # [수정됨] 부호 오류 수정 (+Pu -> -Pu)
        numerator_rect = As * steel.fy - Pu
        denominator_rect = conc.eta * 0.85 * conc.fck * conc.beta1 * bf
        if abs(denominator_rect) < 1e-9:
            raise SectionCapacityError("T형 단면 플랜지 폭이 0입니다.")
        c_rect_assumption = numerator_rect / denominator_rect
        a = conc.beta1 * c_rect_assumption

        if is_less_or_equal(a, hf):
            # Case 1: 중립축이 플랜지 내에 위치.
            c = c_rect_assumption
            Cc = conc.eta * 0.85 * conc.fck * a * bf
            Mn = Cc * (d - a / 2) + Pu * (d - h / 2)
        else:
            # Case 2: 중립축이 웨브 내에 위치.
            Ccf = conc.eta * 0.85 * conc.fck * (bf - bw) * hf
            # [수정됨] 부호 오류 수정 (+Pu -> -Pu)
            numerator_t = As * steel.fy - Pu - Ccf
            denominator_t = conc.eta * 0.85 * conc.fck * conc.beta1 * bw
            if abs(denominator_t) < 1e-9:
                raise SectionCapacityError("T형 단면 웨브 폭이 0입니다.")
            c = numerator_t / denominator_t
            a = conc.beta1 * c

            Ccw = conc.eta * 0.85 * conc.fck * a * bw
            Mn_f = Ccf * (d - hf / 2)
            Mn_w = Ccw * (d - a / 2)
            Mn = Mn_f + Mn_w + Pu * (d - h / 2)

        if c <= 0:
            raise SectionCapacityError("중립축이 단면 외부에 있어 휨 해석이 불가능합니다.")

        et = conc.ultimate_strain * (d - c) / c
        phi = self._calculate_phi(steel, et)

        return AnalysisResult(c=c, net_tensile_strain=et, phi=phi, phi_mn=phi * Mn)