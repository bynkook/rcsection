# core/exceptions.py

"""
이 모듈은 RC-Designer 프로젝트에서 사용되는 모든 사용자 정의 예외 클래스를
중앙에서 관리합니다.

각 예외는 특정 오류 상황을 명확하게 나타내어, 체계적이고 구체적인
오류 처리를 가능하게 합니다. 모든 예외는 기본 RCDException을 상속받습니다.
"""

class RCDException(Exception):
    """
    이 프로젝트(Reinforced Concrete Design)의 모든 사용자 정의 예외에 대한 기본 클래스입니다.
    이 클래스를 직접 발생시키기보다는, 이를 상속받는 더 구체적인 예외를 사용합니다.
    """
    pass

# --- 입력값 및 정의 관련 오류 ---

class MaterialError(RCDException):
    """재료 정의와 관련된 오류에 대한 기본 클래스입니다."""
    pass

class SectionError(RCDException):
    """단면 정의와 관련된 오류에 대한 기본 클래스입니다."""
    pass

# --- 설계 계산 과정에서 발생하는 오류 ---

class DesignError(RCDException):
    """설계 계산 과정에서 발생하는 일반적인 오류에 대한 기본 클래스입니다."""
    pass

class SectionCapacityError(DesignError):
    """
    주어진 단면이 요구되는 계수하중을 저항하기에 물리적으로 너무 작거나,
    휨 해석이 불가능한 상태일 때 발생하는 예외입니다.
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DuctilityError(DesignError):
    """
    단면이 설계기준에서 요구하는 최소 연성(최소 변형률)을 만족하지 못할 때
    발생하는 예외입니다. (사실상의 최대 철근량 초과)
    """
    def __init__(self, et: float, et_min: float):
        message = (f"Ductility requirements not met. "
                   f"Calculated strain εt={et:.5f} is less than the minimum allowable strain εt,min={et_min:.5f}. "
                   f"The section is over-reinforced.")
        self.message = message
        super().__init__(self.message)

class MinReinforcementError(DesignError):
    """
    단면이 설계기준에서 요구하는 최소 철근량 규정(φMn >= 1.2 * Mcr)을
    만족하지 못할 때 발생하는 예외입니다.
    """
    def __init__(self, phi_mn: float, mcr_check_val: float):
        message = (f"Minimum reinforcement requirements not met. "
                   f"Design strength φMn={phi_mn/1e6:.2f} kNm is less than 1.2*Mcr={mcr_check_val/1e6:.2f} kNm.")
        self.message = message
        super().__init__(self.message)