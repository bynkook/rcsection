# main_batch.py

import numpy as np
from fastapi import params
from interface.batch_runner import BatchRunner
import time


# =================================
# 사용자 배치 실행 시나리오 정의
# =================================

# --- 사각형 단면 설계 모드 ---
rectangular_design = {
    "shape": ["r"],
    "mode": ["design"],
    "fck": [24, 27, 30, 40],
    "grade": ["SD400"],
    "width": [500], "height": [800],
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [25],
    "mu": [300, 400], # kN.m
    "pu": [0, 200]  # kN
}

# --- T형 단면 설계 모드 ---
tshape_design = {
    "shape": ["t"],
    "mode": ["design"],
    "fck": [24, 27], "grade": ["SD400"],
    # T형 단면 파라미터
    "web_width": [400, 500],
    "flange_width": [1200, 1500],
    "flange_depth": [200],
    "height": [800, 1000],
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [25],
    "mu": [300, 400], # kN.m
    "pu": [0, 100]  # kN
}

# --- 사각형 단면 해석모드(철근비 변화) ---
rectangular_analysis = {
    "shape": ["r"],
    "mode": ["analysis"],
    "fck": [24, 28, 30, 35, 40, 45, 50, 55, 60], "grade": ["SD400", "SD500"],
    "width": np.linspace(300, 1000, int((1000-300)/50)+1),
    "height": np.linspace(500, 1500, int((1500-500)/50)+1),
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [29],
    "num_rebar_steps": [25]    # from 최소철근 to 최대철근 case number
}

rectangular_analysis_small = {
    "shape": ["r"],
    "mode": ["analysis"],
    "fck": [27, 30],
    "grade": ["SD400"],
    "width": np.linspace(800, 1000, int((1000-800)/20)+1),
    "height": np.linspace(1000, 1200, int((1200-1000)/20)+1),
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [29],
    "num_rebar_steps": [25]    # from 최소철근 to 최대철근 case number
}

# --- T형 단면 해석 모드(철근비 변화) ---
tshape_analysis = {
    "shape": ["t"],
    "mode": ["analysis"],
    "fck": [40], "grade": ["SD500"],
    # T형 단면 파라미터
    "web_width": [400, 500],
    "flange_width": [1200, 1500],
    "flange_depth": [200],
    "height": [800, 1000],
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [2],
    "num_rebar_steps": [100]    # from 최소철근 to 최대철근 case number
}

# --- 사각형 단면 Code Check ---
rectangular_codecheck = {
    "shape": ["r"],
    "mode": ["check"],
    "fck": [24, 30],
    "grade": ["SD400"],
    "width": [1000], "height": [1000, 1100, 1200],
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [25, 29, 32],
    # 검토할 철근량 범위 (mm^2)
    "as_provided": [2500, 3000, 3500], 
    # 검토할 하중 범위
    "mu": [400, 500, 600, 1000, 1200, 1500],
    "pu": [0]   
}
    
# ---T형 단면 Code Check ---
tshape_codecheck = {
    "shape": ["t"],
    "mode": ["check"],
    "fck": [24, 30],
    "grade": ["SD400"],
    # T형 단면 파라미터
    "web_width": [400, 500],
    "flange_width": [1200, 1500],
    "flange_depth": [200],
    "height": [800, 1000],
    "cover": [50], "stirrup_dia": [13], "rebar_dia": [25, 29, 32],
    # 검토할 철근량 범위 (mm^2)
    "as_provided": [2500, 3000, 3500], 
    # 검토할 하중 범위
    "mu": [400, 500, 600, 1000, 1200, 1500],
    "pu": [0]   
}


def main():
    
    """
    RC Beam Designer (Batch Mode)의 메인 실행 함수.
    재료, 치수 단위 : (N, mm, MPa)
    하중 단위 : (kN) - 프로그램내부에서 N, mm 로 변환
    """
    print("="*50)
    print("    RC Beam Designer - Batch Mode (R2.0)")
    print("="*50)

    # 실행할 배치 입력
    # param = rectangular_design ; output_filename= 'batch_design_rect_result'
    # param = tshape_design ; output_filename = 'batch_design_tshape_result'
    # param = rectangular_analysis ; output_filename = 'batch_analysis_rect_result'
    param = rectangular_analysis_small ; output_filename = 'batch_analysis_rect_result'
    # param = tshape_analysis ; output_filename = 'batch_analysis_tshape_result'
    # param = rectangular_codecheck ; output_filename= 'batch_check_rect_result'
    # param = tshape_codecheck ; output_filename = 'batch_check_tshape_result'

    # 하중 입력값 단위 변환 (kN, m) -> (N, mm)
    for key, value in param.items():
        if key == 'mu':
            param |= {key:[x*1e6 for x in value]}   # 휨모멘트 단위 변경
        elif key == 'pu':
            param |= {key:[x*1e3 for x in value]}   # 축력 단위 변경

    outfile_name = str(output_filename + '.csv')
    
    start_time = time.time()

    runner = BatchRunner(param)
    runner.run()
    runner.save_to_csv(outfile_name)
    
    print(f"'{outfile_name}' 의 결과 파일로 저장됩니다.")
    end_time = time.time()    
    print(f"총 실행 시간: {end_time - start_time:.2f} 초")

if __name__ == "__main__":
    main()