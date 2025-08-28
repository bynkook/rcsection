# services/rebar_selector.py

"""
이 모듈은 단위폭 당 소요 철근량을 기준으로, 가장 경제적인 철근 조합
(직경+간격) 컨셉을 찾아 제안하는 RebarSelector 서비스를 제공합니다.
"사전 계산 및 빠른 조회"와 "역산" 방식을 결합하여 최적화되어 있습니다.
"""
from dataclasses import dataclass
from typing import List, Optional

from core.material.material import Steel, Rebar, _REBAR_AREAS

@dataclass(frozen=True)
class SelectedOption:
    """단위폭 당 최적 철근 배근 '컨셉'을 나타냅니다."""
    diameter: int
    spacing: int
    as_provided_per_meter: float
    efficiency: float

class RebarSelector:
    """단위폭 당 소요 철근량을 만족하는 최적의 철근 배치(D@S)를 제안"""
    def __init__(self,
                 available_diameters: List[int],
                 preferred_spacings: List[int]):
        """
        RebarSelector를 초기화합니다.
        Args:
            available_diameters: 사용자가 고려할 철근 직경 목록.
            preferred_spacings: 사용자가 선호하는 간격 목록.
        """
        self.available_diameters = sorted(available_diameters)
        self.preferred_spacings = sorted(preferred_spacings)
        self.rebar_areas = {dia: _REBAR_AREAS[dia] for dia in self.available_diameters}

    def select_optimal_options(self, as_required_pm: float, top_n: int = 5) -> List[SelectedOption]:
        """
        가장 경제적인 상위 N개의 배근 안을 "역산" 방식으로 찾습니다.
        """
        if as_required_pm <= 0:
            return []

        valid_options = []
        # 1. 선호 간격을 기준으로 루프 실행
        for spacing in self.preferred_spacings:
            # 2. 이 간격을 만족하기 위해 필요한 단일 철근의 최소 면적을 역산
            required_single_rebar_area = as_required_pm * (spacing / 1000.0)

            # 3. 필요한 면적보다 크면서 가장 작은 철근(최적 직경)을 찾음
            best_dia_for_spacing = None
            for dia in self.available_diameters:
                if self.rebar_areas[dia] >= required_single_rebar_area:
                    best_dia_for_spacing = dia
                    break # 정렬되어 있으므로 처음 찾은 것이 가장 작은 것

            # 4. 최적 직경을 찾았다면, 최종 조합을 생성
            if best_dia_for_spacing:
                as_provided_pm = self.rebar_areas[best_dia_for_spacing] * (1000 / spacing)
                efficiency = as_provided_pm / as_required_pm

                option = SelectedOption(
                    diameter=best_dia_for_spacing,
                    spacing=spacing,
                    as_provided_per_meter=as_provided_pm,
                    efficiency=efficiency
                )
                valid_options.append(option)

        # 5. 모든 간격에 대해 찾아낸 최적 조합들을 효율성 기준으로 최종 정렬
        valid_options.sort(key=lambda opt: opt.efficiency)
        return valid_options[:top_n]