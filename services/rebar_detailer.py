# services/rebar_detailer.py

"""
이 모듈은 선택된 철근 배근 컨셉(D@S)을 실제 단면 폭에 적용하여,
구체적인 배근 상세(철근 개수, 실제 간격, 다층 배근, 실제 d값)를 계획하는
RebarDetailer 서비스를 제공합니다.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

from core.material.material import Steel, Rebar
from services.rebar_selector import SelectedOption

@dataclass
class RebarLayer:
    """단일 철근 층의 상세 정보를 나타냅니다."""
    y_from_bottom: float
    num_rebars: int
    rebar: Rebar

@dataclass
class RebarLayout:
    """최종 다층 철근 배근 상세 정보를 나타냅니다."""
    option: SelectedOption
    layers: List[RebarLayer]
    as_provided_total: float
    section_height: float

    @property
    def total_rebars(self) -> int:
        return sum(layer.num_rebars for layer in self.layers)

    def calculate_actual_d(self) -> float:
        """다층 배근된 전체 철근 그룹의 도심을 계산하여 실제 유효깊이(d_actual)를 반환합니다."""
        moment_y, total_area = 0.0, 0.0
        for layer in self.layers:
            layer_area = layer.num_rebars * layer.rebar.area
            moment_y += layer_area * layer.y_from_bottom
            total_area += layer_area

        if total_area == 0: return 0
        centroid_y_from_bottom = moment_y / total_area
        return self.section_height - centroid_y_from_bottom

class RebarDetailer:
    """선택된 철근 컨셉을 실제 단면에 상세 배근하는 계획을 수립합니다."""
    def __init__(self, steel_material: Steel, min_clear_spacing_factor: float = 1.0):
        self.steel_material = steel_material
        # 향후 굵은 골재 최대치수 등을 반영하기 위한 계수 (현재는 철근 직경만큼만 이격)
        self.min_spacing_factor = min_clear_spacing_factor

    def plan_layout(self,
                    selected_option: SelectedOption,
                    section_width: float,
                    section_height: float,
                    as_required_total: float,
                    cover_to_stirrup: float,
                    stirrup_dia: float) -> Optional[RebarLayout]:
        """
        선택된 D@S 컨셉으로 다층 배근을 고려한 상세 계획을 수립합니다.
        """
        dia = selected_option.diameter
        rebar = Rebar(material=self.steel_material, diameter=dia)

        # 1. 강도를 만족하는 총 필요 철근 개수
        num_required = math.ceil(as_required_total / rebar.area) if as_required_total > 0 else 0
        if num_required == 0: return None

        # 2. 시공성을 고려한 1층의 최대 배근 가능 개수
        min_clear_spacing = max(25.0, dia * self.min_spacing_factor) # KDS 14 20 50, 4.2.2 (1)
        effective_width = section_width - (2 * cover_to_stirrup) - (2 * stirrup_dia) - dia
        if effective_width < 0: return None # 폭이 너무 좁아 1개도 배근 불가

        max_per_layer = math.floor(effective_width / (dia + min_clear_spacing)) + 1
        if max_per_layer == 0: return None

        # 3. 다층 배근 계획 수립
        layers: List[RebarLayer] = []
        rebars_to_place = num_required
        current_layer_index = 0

        while rebars_to_place > 0:
            num_this_layer = min(rebars_to_place, max_per_layer)

            # 층의 수직 위치 계산 (KDS 14 20 50, 4.2.2 (2) - 수직 순간격 25mm)
            vertical_clear_spacing = 25.0
            y_pos = cover_to_stirrup + stirrup_dia + dia/2 + current_layer_index * (dia + vertical_clear_spacing)

            layers.append(RebarLayer(y_from_bottom=y_pos, num_rebars=num_this_layer, rebar=rebar))

            rebars_to_place -= num_this_layer
            current_layer_index += 1

        as_provided = sum(l.num_rebars for l in layers) * rebar.area
        return RebarLayout(option=selected_option, layers=layers, as_provided_total=as_provided, section_height=section_height)