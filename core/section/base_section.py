# core/section/base_section.py

"""
이 모듈은 모든 단면 형상 클래스가 따라야 할 추상 기본 클래스(ABC)인
BaseSection을 정의합니다.

BaseSection은 단면이 가져야 할 최소한의 기능(계산 가능한 속성)을 명시합니다.
이를 통해 설계 엔진(DesignEngine)은 구체적인 단면 형상에 의존하지 않고
일관된 방식으로 모든 단면을 다룰 수 있습니다.
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.material.material import Concrete, Steel

class BaseSection(ABC):
    """
    모든 단면 형상 클래스가 상속받아야 할 추상 기본 클래스(Interface).
    이 클래스는 단면이 가져야 할 최소한의 기능(계산 가능한 속성)을 정의합니다.
    실제 계산 로직은 이 클래스를 상속받는 구체적인 단면 클래스(예: RectangularSection)
    에서 구현되어야 합니다.
    """
    
    @property
    @abstractmethod
    def shape_code(self) -> str:
        pass

    @property
    @abstractmethod
    def gross_area(self) -> float:
        pass

    @property
    @abstractmethod
    def Ig(self) -> float:
        pass

    @property
    @abstractmethod
    def effective_depth(self) -> float:
        """인장철근의 유효깊이 (d) : 콘크리트 압축연단에서 인장철근 도심까지의 거리"""
        pass

    @property
    @abstractmethod
    def cracking_moment(self) -> float:
        """단면의 균열모멘트 (Mcr) : 최소철근량 검토에 사용"""
        pass