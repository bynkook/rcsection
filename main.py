# main.py

import sys
from interface import cli
from core.material.material import REBAR_DIA_LIST

# ==========================================================
# 사용자 설정 (User Configuration)
# ==========================================================
# 이 부분만 수정하면 프로그램 전체에 적용됩니다.
CALCULATION_DIAMETERS = [13, 16, 19, 22, 25, 29, 32] # 사용자가 여기서 수정
PREFERRED_REBAR_SPACINGS = [100, 125, 150]

# --- [V3.1 신규] 설정값 유효성 검증 ---
def validate_configuration():
    """
    사용자 설정값이 프로그램에서 지원하는 범위 내에 있는지 확인합니다.
    """
    # set으로 변환하여 효율적인 부분집합(subset) 검사 수행
    all_supported_dias = set(REBAR_DIA_LIST)
    user_selected_dias = set(CALCULATION_DIAMETERS)

    if not user_selected_dias.issubset(all_supported_dias):
        # 사용자가 선택한 직경 중 지원하지 않는 직경이 있음
        unsupported_dias = user_selected_dias - all_supported_dias
        print("="*50)
        print("❌ 설정 오류 (Configuration Error)")
        print(f"다음 철근 직경은 지원하지 않습니다: {sorted(list(unsupported_dias))}")
        print(f"지원 가능한 전체 직경: {sorted(list(all_supported_dias))}")
        print("main.py 상단의 'CALCULATION_DIAMETERS' 설정을 수정해주세요.")
        print("="*50)
        sys.exit(1) # 프로그램 비정상 종료
    
    # 향후 preferred_spacings에 대한 유효성 검사도 추가 가능 (예: 0보다 커야 함)


def get_user_choice():
    """사용자로부터 실행할 모드를 입력받습니다."""
    while True:
        print("\n어떤 작업을 수행하시겠습니까?")
        print("  1: 단면 설계 (소요철근량 산정 및 배근)")     # 소요철근량 계산, 철근 배치, 강도 재계산(다단배근 지원)
        print("  2: 단면 검토 (Code Check)")                  # 강도, As_req 만 계산
        print("  Q: 종료 (Quit)")
        choice = input("선택: ").strip().upper()
        if choice in ['1', '2', 'Q']:
            return choice
        else:
            print("잘못된 입력입니다. 1, 2, Q 중에서 선택해주세요.")

def main():
    """
    RC Beam Designer 프로그램의 메인 실행 함수.
    """
    print("="*50)
    print("      RC Beam Flexural Design Calculator (V3.1)")
    print("="*50)
    print("이 프로그램은 KDS 설계기준에 따라 휨부재를 설계하거나 검토합니다.")
    print("모든 치수 단위는 'mm', 재료강도 단위는 'MPa' 입니다.")
    print("하중 단위는 프롬프트에 명시된 단위를 따라주세요.")

    # --- 프로그램 시작 시 설정값부터 검증 ---
    validate_configuration()
    
    while True:
        choice = get_user_choice()
        
        if choice == '1':
            cli.run_design_workflow(CALCULATION_DIAMETERS, PREFERRED_REBAR_SPACINGS)
        elif choice == '2':
            cli.run_check_workflow()
        elif choice == 'Q':
            break
    
    print("\n프로그램을 종료합니다.")

if __name__ == "__main__":
    main()