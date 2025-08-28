# interface/batch_runner.py

import itertools
import pandas as pd
from tqdm.auto import tqdm
from typing import Dict, List, Any

from core.material.material import Concrete, Steel
from core.section.base_section import BaseSection
from core.section.rectangular import RectangularSection
from core.section.tshape import TSection
from core.engine import DesignEngine
from core.exceptions import RCDException

class BatchRunner:
    """
    설계 파라미터의 여러 조합에 대한 배치 실행을 관리하고 결과를 생성합니다.
    """
    def __init__(self, params: Dict[str, List[Any]]):
        self.params = params
        self.engine = DesignEngine()
        self.results = []

    def run(self):
        """배치 실행을 시작하고 모든 조합에 대한 계산을 수행합니다."""
        # Step 1: 기본 조합 생성
        base_combinations = self._generate_combinations()

        # Step 2: 각 조합에 공통 데이터를 미리 계산하여 추가 (데이터 보강)
        for combo in tqdm(base_combinations, desc="Batch Processing", ncols=120):
            try:
                # Step 2a: 객체 생성
                section, mu, pu = self._setup_case_from_combo(combo)

                # Step 2b: 공통 정보 보강 (코드 중복 제거)
                add_combo = {
                    **combo,
                    'fy': section.tension_steel.fy,
                    'd': section.effective_depth,
                    'Ag': section.gross_area,
                    'Ig': section.Ig,
                    'Sm': section.Ig / section.height * 2 / section.width   # unit section modulus (I/0.5H/W) 파생변수
                }

                # Step 3: 실행 모드에 따라 작업 분배
                mode = combo.get("mode", "design")
                if mode == "design":
                    self._run_design_mode(section, mu, pu, add_combo)
                elif mode == "analysis":
                    self._run_analysis_mode(section, add_combo)
                elif mode == "check":
                    self._run_check_mode(section, mu, pu, add_combo)
                else:
                    raise ValueError(f"Unknown mode: {mode}")

            except RCDException as e:
                self.results.append({**combo, "status": "Error", "message": str(e)})
            except Exception as e:
                self.results.append({**combo, "status": "Critical Error", "message": str(e)})

    def _generate_combinations(self) -> List[Dict[str, Any]]:
        """itertools.product를 사용하여 모든 파라미터 조합 딕셔너리를 생성합니다."""
        keys = self.params.keys()
        values = self.params.values()
        return [dict(zip(keys, p)) for p in itertools.product(*values)]

    def _run_design_mode(self, section: BaseSection, mu: float, pu: float, combo: Dict[str, Any]):
        """[설계 모드] Mu, Pu가 주어졌을 때 As_required를 계산합니다."""
        result = self.engine.design_flexural_reinforcement(section, mu, pu)
        output = {
            **combo,
            "as_required": result.as_required,
            "as_min": result.as_min,
            "as_max": result.as_max,
            "phi": result.analysis_result.phi,
            "net_tensile_strain": result.analysis_result.net_tensile_strain,
            "is_min_controlled": result.is_min_rebar_controlled
        }
        self.results.append(output)

    def _run_analysis_mode(self, section: BaseSection, combo: Dict[str, Any]):
        """[해석 모드] Mu, Pu가 없을 때, 단면 성능 곡선을 생성합니다."""
        num_steps = combo.get("num_rebar_steps", 20) # get으로 안전하게 접근
        capacity = self.engine.get_maximum_capacity(section)
        design = self.engine.design_flexural_reinforcement(section, 0)
        as_min, as_max = design.as_min, capacity.as_max

        if num_steps > 1:
            step_size = (as_max - as_min) / (num_steps - 1) if as_max > as_min else 0
            rebar_areas_to_check = [as_min + i * step_size for i in range(num_steps)]
        else:
            rebar_areas_to_check = [as_min]

        for i, as_provided in enumerate(rebar_areas_to_check):
            result = self.engine.check_section_adequacy(section, as_provided, 0)
            output = {
                **combo,
                "f_idx": int(str(int(section.concrete.fck))+str(int(section.tension_steel.fy))) / 1e3,
                "bd": section.width*section.effective_depth,    # (mm2) 단위변환은 파일출력시 일괄처리
                "as_min": as_min,
                "as_max": as_max,
                "current_rebar_step": i + 1,
                "as_provided": as_provided, # (mm2)
                "rho": as_provided/(section.width*section.effective_depth), # 숫자가 너무 작아서 exp 변환한다
                "phi": result.analysis_result.phi,
                "phi_mn": result.analysis_result.phi_mn,
                "net_tensile_strain": result.analysis_result.net_tensile_strain,
                "is_ok": result.is_ok,
                "strength_ok": result.strength_ok,
                "ductility_ok": result.ductility_ok,
                "min_rebar_ok": result.min_rebar_ok,
            }
            self.results.append(output)

    def _run_check_mode(self, section: BaseSection, mu: float, pu: float, combo: Dict[str, Any]):
        """[검증 모드] 주어진 As, Mu, Pu에 대해 Code Check를 수행합니다."""
        as_provided = combo['as_provided']
        design = self.engine.design_flexural_reinforcement(section, 0)
        capacity = self.engine.get_maximum_capacity(section)
        as_min, as_max = design.as_min, capacity.as_max
        result = self.engine.check_section_adequacy(section, as_provided, mu, pu)
        output = {
            **combo,
            "as_min": as_min,
            "as_max": as_max,
            "as_provided": as_provided,
            "rho": as_provided/(section.width*section.effective_depth)*100,
            "phi": result.analysis_result.phi,
            "phi_mn": result.analysis_result.phi_mn,
            "net_tensile_strain": result.analysis_result.net_tensile_strain,
            "is_ok": result.is_ok,
            "strength_ok": result.strength_ok,
            "ductility_ok": result.ductility_ok,
            "min_rebar_ok": result.min_rebar_ok,
        }
        self.results.append(output)

    def _setup_case_from_combo(self, combo: Dict[str, Any]) -> tuple:
        """'shape' 키를 기반으로 적절한 단면 객체를 생성합니다."""
        concrete = Concrete(fck=combo['fck'])
        steel = Steel(grade=combo['grade'])
        shape_code = combo.get('shape', 'r')

        if shape_code == 'r':
            section = RectangularSection(
                width=combo['width'],
                height=combo['height'],
                cover_to_stirrup=combo['cover'],
                stirrup_dia=combo['stirrup_dia'],
                tension_rebar_dia=combo['rebar_dia'],
                concrete=concrete,
                tension_steel=steel
                )
        elif shape_code == 't':
            section = TSection(
                web_width=combo['web_width'],
                height=combo['height'],
                flange_width=combo['flange_width'],
                flange_depth=combo['flange_depth'],
                cover_to_stirrup=combo['cover'],
                stirrup_dia=combo['stirrup_dia'],
                tension_rebar_dia=combo['rebar_dia'],
                concrete=concrete,
                tension_steel=steel
                )
        else:
            raise ValueError(f"지원하지 않는 단면 형상 코드입니다: '{shape_code}'")

        # 하중 입력값 없으면 0 으로 처리
        mu = combo.get('mu', 0.0)
        pu = combo.get('pu', 0.0)

        return section, mu, pu

    def save_to_csv(self, filename: str):
        """결과를 pandas DataFrame으로 변환하고 단위를 조정한 후 CSV 파일로 저장합니다."""
        if not self.results:
            print("결과가 없습니다. 저장할 내용이 없습니다.")
            return

        df = pd.DataFrame(self.results)

        # --- 출력의 단위 변환은 여기서 일괄 수행 ---
        # Ig, As 는 cm4, cm2 단위로 출력
        # 휨모멘트는 N-mm -> kN-m 로 출력
        # 축력은 N -> kN 로 출력
        cm2_cols = ['as_min', 'as_max', 'as_required', 'as_provided', 'Ag', 'bd', 'Sm']
        cm4_cols = ['Ig']
        kNm_cols = ['mu', 'phi_mn']
        kN_cols = ['pu']

        for col in df.columns:
            if col in cm2_cols:
                df[col] = df[col] / 1e2
            elif col in cm4_cols:
                df[col] = df[col] / 1e4
            elif col in kNm_cols:
                df[col] = df[col] / 1e6
            elif col in kN_cols:
                df[col] = df[col] / 1e3

        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n결과가 '{filename}' 파일로 성공적으로 저장되었습니다.")