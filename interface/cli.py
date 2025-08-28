# interface/cli.py

import math
from typing import Dict, Any, List

# --- 모든 필요한 모듈과 클래스를 import ---
from core.material.material import Concrete, Steel, Rebar
from core.section.base_section import BaseSection
from core.section.rectangular import RectangularSection
from core.section.tshape import TSection
from core.engine import DesignEngine, DesignResult, CheckResult
from core.exceptions import RCDException

from services.rebar_selector import RebarSelector, SelectedOption
from services.rebar_detailer import RebarDetailer, RebarLayout, RebarLayer

# --- [1. 기본 사용자 입력(Prompt) 함수] ---

def prompt_for_material() -> Dict[str, Any]:
    """사용자로부터 재료 정보를 입력받습니다."""
    print("\n--- [Step 1] 재료 정보 입력 ---")
    fck = float(input("콘크리트 설계기준압축강도 (fck, MPa): "))
    fy_grade = input("철근 강종 (예: SD400, SD500): ").upper()
    return {"fck": fck, "grade": fy_grade}

def prompt_for_section_shape() -> str:
    """사용자로부터 단면 형상을 선택받습니다."""
    while True:
        print("\n--- [Step 2] 단면 형상 선택 ---")
        shape = input("단면 형상을 선택하세요 [r: 사각형, t: T형]: ").strip().lower()
        if shape in ['r', 't']:
            return shape
        else:
            print("잘못된 입력입니다. 'r' 또는 't' 중에서 선택해주세요.")

def prompt_for_rectangular_section() -> Dict[str, Any]:
    """사용자로부터 사각형 단면 정보를 입력받습니다."""
    print("\n--- [Step 2a] 사각형 단면 정보 입력 (mm) ---")
    width = float(input("단면의 폭 (b): "))
    height = float(input("단면의 높이 (h): "))
    cover_to_stirrup = float(input("스터럽 표면까지 피복두께: "))
    stirrup_dia = float(input("스터럽 직경: "))
    return {"width": width, "height": height, "cover_to_stirrup": cover_to_stirrup, "stirrup_dia": stirrup_dia}

def prompt_for_t_section() -> Dict[str, Any]:
    """사용자로부터 T형 단면 정보를 입력받습니다."""
    print("\n--- [Step 2b] T형 단면 정보 입력 (mm) ---")
    web_width = float(input("웨브 폭 (bw): "))
    flange_width = float(input("플랜지 폭 (bf): "))
    flange_depth = float(input("플랜지 두께 (hf): "))
    height = float(input("전체 높이 (h): "))
    cover_to_stirrup = float(input("스터럽 표면까지 피복두께: "))
    stirrup_dia = float(input("스터럽 직경: "))
    return {"web_width": web_width, "flange_width": flange_width, "flange_depth": flange_depth, "height": height, "cover_to_stirrup": cover_to_stirrup, "stirrup_dia": stirrup_dia}

def prompt_for_loads() -> Dict[str, Any]:
    """계수하중 정보를 입력받고 N, mm 단위로 변환합니다."""
    print("\n--- [Step 3] 계수하중 정보 입력 ---")
    mu = float(input("계수휨모멘트 (Mu, kN.m): ")) * 1e6
    pu = float(input("계수축력 (Pu, kN) [압축+, 인장-]: ")) * 1e3
    return {"mu": mu, "pu": pu}

def prompt_for_rebar_layout(steel: Steel, sec_props: Dict[str, Any]) -> RebarLayout:
    """상세 배근 검토 모드용: 다층 배근 상세를 입력받아 RebarLayout 객체를 생성합니다."""
    print("\n--- [Step 3] 상세 배근 정보 입력 ---")
    num_layers = int(input("총 철근 층수: "))
    
    layers = []
    cover = sec_props['cover_to_stirrup']
    stirrup_dia = sec_props['stirrup_dia']
    vertical_spacing = 25.0     # 이 부분은 추후 설계기준에 따라 설정되게 해야 함

    y_pos = 0.0
    for i in range(num_layers):
        print(f"\n--- {i+1}번째 층 (가장 아래층부터) ---")
        dia = int(input(f"  철근 직경 (D): "))
        num = int(input(f"  철근 개수: "))
        rebar = Rebar(material=steel, diameter=dia)
        
        if i == 0:
            y_pos = cover + stirrup_dia + dia / 2
        else:
            prev_dia = layers[i-1].rebar.diameter
            y_pos += (prev_dia / 2) + vertical_spacing + (dia / 2)
        
        layers.append(RebarLayer(y_from_bottom=y_pos, num_rebars=num, rebar=rebar))

    as_provided = sum(l.num_rebars * l.rebar.area for l in layers)
    return RebarLayout(option=None, layers=layers, as_provided_total=as_provided, section_height=0)

# --- [2. 내부용 헬퍼(Helper) 함수] ---

def _prompt_and_create_materials() -> tuple[Concrete, Steel]:
    """[내부용] 재료 정보를 입력받아 Concrete와 Steel 객체를 생성하여 반환합니다."""
    mat_props = prompt_for_material()
    concrete = Concrete(fck=mat_props['fck'])
    steel = Steel(grade=mat_props['grade'])
    return concrete, steel

def _create_section_from_props(shape: str, sec_props: Dict[str, Any], concrete: Concrete, steel: Steel) -> BaseSection:
    """[내부용] 입력받은 속성과 재료로 적절한 단면 객체를 생성하는 헬퍼 함수."""
    if shape == 'r':
        return RectangularSection(**sec_props, concrete=concrete, tension_steel=steel)
    elif shape == 't':
        return TSection(**sec_props, concrete=concrete, tension_steel=steel)
    else:
        raise ValueError("알 수 없는 단면 형상 코드입니다.")

# --- [3. 결과 출력(Display) 함수] ---

def display_layout_proposals(layouts: List[RebarLayout], initial_d: float):
    """RebarDetailer가 생성한 여러 배근 제안을 출력합니다."""
    print("\n" + "="*50)
    print("      ✅ 최적 철근 배근 상세 제안")
    print("="*50)
    for i, layout in enumerate(layouts):
        option = layout.option
        actual_d = layout.calculate_actual_d()
        print(f"--- [ 제안 {i+1} ] ---")
        print(f"  - 설계 컨셉: D{option.diameter} @ {option.spacing} (효율성: {option.efficiency:.3f})")
        print(f"  - 배근 상세: 총 {layout.total_rebars}개 ({len(layout.layers)}단 배근)")
        print(f"  - 실제 제공 철근량: {layout.as_provided_total:.2f} mm^2")
        print(f"  - 유효깊이(d) 변화: {initial_d:.1f} mm -> {actual_d:.1f} mm")
    print("="*50)

def display_check_result(result: CheckResult, section: BaseSection):
    """단면 강도 검토 결과를 가독성 높게 출력합니다."""
    print("\n" + "="*40)
    print("      ✅ 단면 검토 결과")
    print("="*40)
    analysis = result.analysis_result
    print(f"  - 실제 유효깊이 (d) : {section.effective_depth:.1f} mm")
    print(f"  - 설계 휨강도 (φMn) : {analysis.phi_mn / 1e6:.2f} kN.m")
    print(f"\n  [단면 성능 상세]")
    print(f"  - 중립축 깊이 (c) : {analysis.c:.2f} mm")
    print(f"  - 순인장변형률 (εt) : {analysis.net_tensile_strain:.5f}")
    print(f"  - 강도감소계수 (φ) : {analysis.phi:.3f}")
    print(f"\n  [설계기준 적합성 검토]")
    print(f"  - 종합 판정        : {'OK' if result.is_ok else 'NG'}")
    print(f"  - 강도 조건        : {'OK' if result.strength_ok else 'NG'}")
    print(f"  - 연성 조건        : {'OK' if result.ductility_ok else 'NG'}")
    print(f"  - 최소 철근량 조건 : {'OK' if result.min_rebar_ok else 'NG'}")
    print("="*40)

def display_error(error: Exception):    
    print("\n" + "-"*40)
    print("      ❌ 오류 발생 (Error)")
    print(f"  오류 유형: {type(error).__name__}")
    print(f"  상세 내용: {error}")
    print("-"*40)

# --- [4. 메인 워크플로우(Workflow) 함수] ---

def run_design_workflow(available_diameters: List[int], preferred_spacings: List[int]):    
    print("\n>>> 단면 설계(Design Mode)를 시작합니다.")
    try:
        # --- 초기 설정 ---
        concrete, steel = _prompt_and_create_materials()
        shape = prompt_for_section_shape()
        if shape == 'r':
            sec_props = prompt_for_rectangular_section()
            section_width = sec_props['width']
        else:
            sec_props = prompt_for_t_section()
            section_width = sec_props['web_width']  # T형 단면 주철근은 web 에 배치
        loads = prompt_for_loads()
        
        # --- 서비스 객체 생성 ---
        engine = DesignEngine()
        selector = RebarSelector(available_diameters=available_diameters, preferred_spacings=preferred_spacings)
        detailer = RebarDetailer(steel_material=steel)
        
        # --- 지능형 반복 설계 루프 ---
        iteration_count = 1
        initial_rebar_dia = available_diameters[len(available_diameters) // 2]
        current_sec_props = {**sec_props, 'tension_rebar_dia': initial_rebar_dia}

        while iteration_count <= 5:
            print("\n" + f"--- [ 설계 반복 #{iteration_count} ] ---")
            
            section = _create_section_from_props(shape, current_sec_props, concrete, steel)
            design_result = engine.design_flexural_reinforcement(section=section, mu=loads['mu'], pu=loads['pu'])
            as_required_total = design_result.as_required
            
            as_req_per_meter = as_required_total * (1000 / section_width)
            top_options = selector.select_optimal_options(as_req_per_meter, top_n=3)
            if not top_options:
                raise RCDException("경제적인 배근 컨셉을 찾을 수 없습니다.")

            detailed_layouts = [layout for option in top_options if (layout := detailer.plan_layout(option, section_width, section.height, as_required_total, current_sec_props['cover_to_stirrup'], current_sec_props['stirrup_dia']))]
            if not detailed_layouts:
                raise RCDException("제안된 컨셉으로 시공 가능한 배근을 찾을 수 없습니다.")
                
            display_layout_proposals(detailed_layouts, section.effective_depth)

            choice_str = input("\n가장 적합한 제안의 번호를 선택하세요 (재설계 없이 종료하려면 'q'): ").strip().lower()
            if choice_str == 'q': break
            
            try:
                chosen_layout = detailed_layouts[int(choice_str) - 1]
            except (ValueError, IndexError):
                print("잘못된 선택입니다. 다시 시도합니다."); iteration_count += 1; continue
                
            d_initial = section.effective_depth
            d_actual = chosen_layout.calculate_actual_d()

            if not math.isclose(d_initial, d_actual):
                print(f"\n[!] 유효깊이(d) 변경 감지: {d_initial:.1f}mm -> {d_actual:.1f}mm")
                recalc_choice = input("변경된 d값으로 재설계 하시겠습니까? [y/n]: ").lower()
                if recalc_choice == 'y':
                    equivalent_dia = 2 * (section.height - current_sec_props['cover_to_stirrup'] - current_sec_props['stirrup_dia'] - d_actual)
                    current_sec_props['tension_rebar_dia'] = equivalent_dia
                    iteration_count += 1
                    continue
            
            print("\n--- 최종 설계안 검증 ---")
            final_section = _create_section_from_props(shape, current_sec_props, concrete, steel)
            check_result = engine.check_section_adequacy(section=final_section, as_provided=chosen_layout.as_provided_total, mu=loads['mu'], pu=loads['pu'])
            display_check_result(check_result, final_section)
            if check_result.is_ok:
                print("✅ 최종 설계안이 모든 기준을 만족합니다.")
            else:
                print("❌ 최종 설계안이 기준을 만족하지 못합니다.")
            break
            
    except (RCDException, ValueError) as e:
        display_error(e)

def run_check_workflow():
    """사용자가 입력한 상세 배근안을 종합적으로 검토합니다."""
    print("\n>>> 단면 검토(Check Mode)를 시작합니다.")
    try:
        concrete, steel = _prompt_and_create_materials()
        shape = prompt_for_section_shape()
        if shape == 'r':
            sec_props = prompt_for_rectangular_section()
        else: # shape == 't'
            sec_props = prompt_for_t_section()

        layout = prompt_for_rebar_layout(steel, sec_props)
        layout.section_height = sec_props['height']

        d_actual = layout.calculate_actual_d()
        equivalent_dia = 2 * (sec_props['height'] - sec_props['cover_to_stirrup'] - sec_props['stirrup_dia'] - d_actual)
        sec_props['tension_rebar_dia'] = equivalent_dia
        
        final_section = _create_section_from_props(shape, sec_props, concrete, steel)
            
        loads = prompt_for_loads()
        engine = DesignEngine()
        check_result = engine.check_section_adequacy(section=final_section, as_provided=layout.as_provided_total, mu=loads['mu'], pu=loads['pu'])

        print("\n--- [상세 배근 검토 결과] ---")
        print(f"총 제공 철근량 As_prov = {layout.as_provided_total:.2f} mm^2 ({len(layout.layers)}단 배근)")
        display_check_result(check_result, final_section)

    except (RCDException, ValueError) as e:
        display_error(e)