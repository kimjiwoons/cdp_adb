# ============================================
# CDP를 이용한 네이버 모바일 검색 자동화
# 크롬 디버깅 모드 필요: --remote-debugging-port=9222 --remote-allow-origins=*
# 
# 사용법: python cdp_touch_scroll.py 검색어
# ============================================

import json
import time
import random
import sys
import re
import requests
import websocket
import pyperclip

# ============================================
# UA Agent import (같은 폴더에 ua_agent.py 필요)
# 없으면 내장 버전 매핑 사용
# ============================================
try:
    from ua_agent import (
        CHROME_VERSION_MAP,
        OPERA_VERSION_MAP,
        OPERA_MOBILE_VERSION_MAP,
        SAMSUNG_VERSION_MAP,
        get_chrome_full_version,
        get_opera_full_version,
        get_opera_mobile_full_version,
        get_opera_mobile_chromium_version,
        get_samsung_full_version,
        get_opera_chromium_version,
        get_samsung_chromium_version,
    )
    print("[UA Agent] 외부 모듈 로드됨")
except ImportError:
    print("[UA Agent] 내장 버전 매핑 사용")
    
    # ============================================
    # 내장 버전 매핑 (ua_agent.py 없을 때 사용)
    # ============================================
    CHROME_VERSION_MAP = {
        # Chrome 120~131 (Opera Mobile 80~92용)
        "120": {"build": "6099", "patches": ["109", "199", "216", "224"]},
        "121": {"build": "6167", "patches": ["85", "139", "160", "184"]},
        "122": {"build": "6261", "patches": ["57", "69", "111", "128"]},
        "123": {"build": "6312", "patches": ["58", "59", "86", "122"]},
        "124": {"build": "6367", "patches": ["60", "78", "118", "207"]},
        "125": {"build": "6422", "patches": ["60", "76", "112", "141"]},
        "126": {"build": "6478", "patches": ["61", "114", "126", "182"]},
        "127": {"build": "6533", "patches": ["72", "84", "99", "106", "119"]},  # 106 실폰 추가
        "128": {"build": "6613", "patches": ["84", "113", "119", "137"]},
        "129": {"build": "6668", "patches": ["58", "70", "89", "100"]},  # 100 실폰 확인
        "130": {"build": "6723", "patches": ["58", "91", "116", "127"]},
        "131": {"build": "6778", "patches": ["69", "108", "139", "204"]},
        # Chrome 132~144 (최신)
        "132": {"build": "6834", "patches": ["83", "110", "122", "159", "194"]},  # 122 실폰 추가
        "133": {"build": "6943", "patches": ["53", "98", "126", "141", "142"]},
        "134": {"build": "6998", "patches": ["35", "39", "88", "117", "166"]},  # 39 실폰 추가
        "135": {"build": "7049", "patches": ["42", "84", "95", "111", "115"]},  # 111 실폰 추가
        "136": {"build": "7103", "patches": ["49", "92", "113", "114", "127"]},
        "137": {"build": "7151", "patches": ["41", "55", "68", "89", "104"]},  # 89 실폰 추가
        "138": {"build": "7204", "patches": ["49", "93", "157", "179", "183", "184"]},
        "139": {"build": "7258", "patches": ["66", "67", "128", "138", "139", "143"]},
        "140": {"build": "7339", "patches": ["80", "81", "124", "154", "207", "208"]},
        "141": {"build": "7390", "patches": ["43", "55", "65", "70", "112", "123", "125"]},
        "142": {"build": "7444", "patches": ["59", "91", "135", "138", "158", "171", "176"]},
        "143": {"build": "7499", "patches": ["40", "41", "52", "92", "110", "169"]},
        "144": {"build": "7509", "patches": ["3", "10", "20"]},
    }
    
    # Opera Desktop 버전 맵 (PC용)
    OPERA_VERSION_MAP = {
        "115": {"build": "5322", "patches": ["68", "94", "109", "119"], "chromium": "130"},
        "116": {"build": "5366", "patches": ["127"], "chromium": "131"},
        "117": {"build": "5408", "patches": ["197"], "chromium": "132"},
        "118": {"build": "5461", "patches": ["104"], "chromium": "133"},
        "119": {"build": "5497", "patches": ["141"], "chromium": "134"},
        "120": {"build": "5543", "patches": ["38", "61", "93", "128", "161", "201"], "chromium": "135"},
        "121": {"build": "5600", "patches": ["20", "38", "50"], "chromium": "137"},
        "122": {"build": "5643", "patches": ["17", "24", "51", "71", "92", "142"], "chromium": "138"},
        "123": {"build": "5669", "patches": ["23", "47"], "chromium": "139"},
        "124": {"build": "5705", "patches": ["15", "42", "65"], "chromium": "140"},
        "125": {"build": "5729", "patches": ["12", "15", "21", "49"], "chromium": "141"},
    }
    
    # Opera Mobile 버전 맵 (모바일용 - Desktop과 버전 체계 다름!)
    # 실제 데이터: OPR 80~93 범위, 실폰/LDPlayer 확인
    # 형식: major.minor.build.patch (minor는 업데이트 횟수)
    OPERA_MOBILE_VERSION_MAP = {
        "80": {"build": "4244", "minor_patches": [("0", "77240")]},  # 실폰: 80.0.4244.77240
        "81": {"build": "4292", "minor_patches": [("1", "78446")]},  # 실폰: 81.1.4292.78446
        "82": {"build": "4342", "minor_patches": [("0", "79423")]},  # 실폰: 82.0.4342.79423
        "83": {"build": "4388", "minor_patches": [("0", "80445")]},  # 실폰: 83.0.4388.80445
        "84": {"build": "4452", "minor_patches": [("4", "81430")]},  # 실폰: 84.4.4452.81430
        "85": {"build": "4500", "minor_patches": [("7", "82229")]},  # 실폰: 85.7.4500.82229
        "86": {"build": "4550", "minor_patches": [("0", "82358")]},  # 실폰: 86.0.4550.82358
        "87": {"build": "4607", "minor_patches": [("1", "82866")]},  # 실폰: 87.1.4607.82866
        "88": {"build": "4656", "minor_patches": [("0", "83326")]},  # 실폰: 88.0.4656.83326
        "89": {"build": "4705", "minor_patches": [("5", "84314")]},  # 실폰: 89.5.4705.84314
        "90": {"build": "4752", "minor_patches": [("0", "84419")]},  # 실폰: 90.0.4752.84419
        "91": {"build": "4810", "minor_patches": [("0", "85200")]},  # 추정
        "92": {"build": "4866", "minor_patches": [("0", "85599")]},  # 추정
        "93": {"build": "4906", "minor_patches": [("3", "86355")]},  # 실폰: 93.3.4906.86355
    }
    
    # Opera Mobile → Chromium 버전 매핑 (실폰 확인!)
    OPERA_MOBILE_CHROMIUM_MAP = {
        "80": "120", "81": "122", "82": "124", "83": "126", "84": "127",
        "85": "129", "86": "130", "87": "132", "88": "134", "89": "135",
        "90": "137", "91": "140", "92": "140", "93": "142",
    }
    
    # Opera Mobile → Opera Desktop 매핑 (실폰 확인!)
    # Client Hints에 넣는 Opera 버전은 Desktop 버전임
    OPERA_MOBILE_TO_DESKTOP_MAP = {
        "80": "106", "81": "108", "82": "110", "83": "112", "84": "113",
        "85": "114", "86": "115", "87": "117", "88": "117", "89": "121",
        "90": "121", "91": "124", "92": "124", "93": "126",
    }
    
    # Opera Desktop 상세 버전 (build.patch) - 실폰 확인
    OPERA_DESKTOP_VERSION_MAP = {
        "106": {"build": "4998", "patches": ["28"]},      # 실폰: 106.0.4998.28
        "108": {"build": "5067", "patches": ["24"]},      # 실폰: 108.0.5067.24
        "110": {"build": "5130", "patches": ["13"]},      # 실폰: 110.0.5130.13
        "112": {"build": "5196", "patches": ["0"]},       # 실폰: 112.0.5196.0
        "113": {"build": "5230", "patches": ["26"]},      # 실폰: 113.0.5230.26
        "114": {"build": "5282", "patches": ["21"]},      # 실폰: 114.0.5282.21
        "115": {"build": "5322", "patches": ["58"]},      # 실폰: 115.0.5322.58
        "117": {"build": "5408", "patches": ["4"]},       # 실폰: 117.0.5408.4
        "121": {"build": "5600", "patches": ["0"]},       # 실폰: 121.0.5600.0
        "124": {"build": "5705", "patches": ["15"]},      # 추정
        "126": {"build": "5800", "patches": ["0"]},       # 실폰: 126.0.5800.0
    }
    
    # Opera Mobile 버전별 GREASE 형식 (실폰 확인!)
    # 세미콜론 위치가 버전마다 다름
    OPERA_MOBILE_GREASE_MAP = {
        "80": "Not A;Brand",    # Not A;Brand (세미콜론 뒤)
        "81": "Not A;Brand",    # Not A;Brand
        "82": ";Not A Brand",   # ;Not A Brand (세미콜론 앞)
        "83": "Not A;Brand",    # Not A;Brand
        "84": "Not;A Brand",    # Not;A Brand (중간)
        "85": "Not;A Brand",    # Not;A Brand
        "86": ";Not A Brand",   # ;Not A Brand
        "87": "Not A;Brand",    # Not A;Brand
        "88": "Not A;Brand",    # Not A;Brand
        "89": "Not;A Brand",    # Not;A Brand
        "90": ";Not A Brand",   # ;Not A Brand
        "91": ";Not A Brand",   # 추정 (86, 90과 유사)
        "92": ";Not A Brand",   # 추정
        "93": "Not A Brand",    # Not A Brand (세미콜론 없음)
    }
    
    # Opera Mobile 버전별 brands 순서 (실폰 확인!)
    # 순서가 버전마다 다름
    OPERA_MOBILE_BRANDS_ORDER_MAP = {
        "80": ["GREASE", "Chromium", "Opera", "OperaMobile"],
        "81": ["Chromium", "Opera", "GREASE", "OperaMobile"],
        "82": ["Opera", "GREASE", "Chromium", "OperaMobile"],
        "83": ["OperaMobile", "Chromium", "GREASE", "Opera"],
        "84": ["OperaMobile", "GREASE", "Chromium", "Opera"],
        "85": ["OperaMobile", "Opera", "GREASE", "Chromium"],
        "86": ["OperaMobile", "GREASE", "Opera", "Chromium"],
        "87": ["Chromium", "OperaMobile", "Opera", "GREASE"],
        "88": ["Opera", "OperaMobile", "GREASE", "Chromium"],
        "89": ["Opera", "OperaMobile", "Chromium", "GREASE"],
        "90": ["Chromium", "OperaMobile", "GREASE", "Opera"],
        "91": ["Chromium", "OperaMobile", "GREASE", "Opera"],  # 추정 (90과 유사)
        "92": ["Chromium", "OperaMobile", "GREASE", "Opera"],  # 추정
        "93": ["GREASE", "Opera", "OperaMobile", "Chromium"],
    }
    
    # Samsung Internet → Chromium 버전 매핑 (실제 확인된 데이터)
    # 출처: UA 검색, chromedriver, 실폰 데이터
    # 패치 형식: "X.Y" → 실제로는 "X" (마이너) + "Y" (패치) 분리됨
    # 예: 28.0.5.9 = Samsung 28, minor 0, build 5, patch 9
    # 하지만 실폰 데이터 보면 29.0.0.59 형식 (build=0, patch=59)
    SAMSUNG_VERSION_MAP = {
        "23": {"patches": ["47", "1.1", "8.2"], "chromium": "115"},      # UA 확인
        "24": {"patches": ["47", "1.2", "3.4", "6.15", "7.1"], "chromium": "117"},  # 공식 문서
        "25": {"patches": ["41", "1.3"], "chromium": "121"},             # UA 확인
        "26": {"patches": ["42", "52", "1.3", "3.7", "8.1"], "chromium": "122"},  # UA 확인
        "27": {"patches": ["57", "79", "1.4", "6.47", "7.12", "7.17"], "chromium": "125"},  # UA 확인
        "28": {"patches": ["40", "55", "56", "57", "59", "5.9"], "chromium": "130"},  # 포럼 확인
        "29": {"patches": ["59"], "chromium": "136"},                    # 실폰 확인
    }
    
    # Chromium 빌드 번호 (삼성용)
    CHROMIUM_BUILD_MAP = {
        "115": "5790",  # chromedriver
        "117": "5938",  # chromedriver
        "121": "6167",  # chromedriver
        "122": "6261",  # chromedriver
        "125": "6422",  # chromedriver
        "130": "6723",  # chromedriver
        "136": "7103",  # 실폰
    }
    
    # Chromium 패치 번호 (삼성용 - 실제 데이터)
    CHROMIUM_PATCH_MAP = {
        "115": ["110", "170"],
        "117": ["88", "149"],
        "121": ["139", "160", "184"],
        "122": ["57", "69", "94", "111", "128"],
        "125": ["60", "76", "112", "141", "142"],
        "130": ["58", "70", "116", "117"],
        "136": ["49", "92", "113", "127"],  # 실폰: 127
    }
    
    # ============================================
    # Edge 버전별 상세 빌드 번호 매핑 (132~143)
    # Edge는 Chromium과 다른 자체 빌드 번호 사용!
    # ============================================
    EDGE_VERSION_MAP = {
        "132": {"build": "2957", "patches": ["115", "127", "140", "171", "178"]},
        "133": {"build": "3065", "patches": ["51", "59", "69", "82", "92"]},
        "134": {"build": "3124", "patches": ["51", "62", "66", "68", "72", "83", "85", "93", "95", "105", "129"]},
        "135": {"build": "3179", "patches": ["54", "73", "85", "98"]},
        "136": {"build": "3240", "patches": ["50", "64", "76", "92", "104", "115", "124"]},
        "137": {"build": "3296", "patches": ["52", "62", "68"]},
        "138": {"build": "3351", "patches": ["55", "65", "77", "83", "95", "109", "121"]},
        "139": {"build": "3405", "patches": ["86", "111"]},
        "140": {"build": "3485", "patches": ["54"]},
        "141": {"build": "3537", "patches": ["57", "71", "85", "99"]},
        "142": {"build": "3595", "patches": ["53", "65", "80", "90", "94"]},
        "143": {"build": "3650", "patches": ["66", "75", "80"]},
        "144": {"build": "3710", "patches": ["10", "20"]},
    }
    
    def get_chrome_full_version(major_version):
        """Chrome/Chromium 메이저 → 상세 버전"""
        major = str(major_version).split(".")[0]
        if major in CHROME_VERSION_MAP:
            info = CHROME_VERSION_MAP[major]
            patch = random.choice(info["patches"])
            return f"{major}.0.{info['build']}.{patch}"
        return f"{major}.0.0.0"
    
    def get_samsung_chromium_full_version(chromium_major):
        """Samsung에서 사용하는 Chromium 상세 버전
        실폰: 136.0.7103.127
        일반 Chrome과 다른 빌드/패치 사용
        """
        major = str(chromium_major).split(".")[0]
        if major in CHROMIUM_BUILD_MAP:
            build = CHROMIUM_BUILD_MAP[major]
            patches = CHROMIUM_PATCH_MAP.get(major, ["0"])
            patch = random.choice(patches)
            return f"{major}.0.{build}.{patch}"
        # CHROME_VERSION_MAP 폴백
        if major in CHROME_VERSION_MAP:
            info = CHROME_VERSION_MAP[major]
            patch = random.choice(info["patches"])
            return f"{major}.0.{info['build']}.{patch}"
        return f"{major}.0.0.0"
    
    def get_opera_full_version(major_version):
        """Opera Desktop 메이저 → 상세 버전"""
        major = str(major_version).split(".")[0]
        if major in OPERA_VERSION_MAP:
            info = OPERA_VERSION_MAP[major]
            patch = random.choice(info["patches"])
            return f"{major}.0.{info['build']}.{patch}"
        return f"{major}.0.0.0"
    
    def get_opera_mobile_full_version(major_version):
        """Opera Mobile 메이저 → 상세 버전 (모바일 전용)
        형식: major.minor.build.patch (예: 93.3.4906.86355)
        """
        major = str(major_version).split(".")[0]
        if major in OPERA_MOBILE_VERSION_MAP:
            info = OPERA_MOBILE_VERSION_MAP[major]
            minor, patch = random.choice(info["minor_patches"])
            return f"{major}.{minor}.{info['build']}.{patch}"
        return f"{major}.0.0.0"
    
    def get_opera_mobile_chromium_version(opera_major):
        """Opera Mobile → Chromium 버전 (모바일 전용)"""
        major = str(opera_major).split(".")[0]
        if major in OPERA_MOBILE_CHROMIUM_MAP:
            return OPERA_MOBILE_CHROMIUM_MAP[major]
        return "142"
    
    def get_samsung_full_version(major_version):
        """Samsung 메이저 → 상세 버전
        실폰 포맷: 29.0.0.59 (major.minor.build.patch)
        APK 포맷: 28.0.5.9 또는 28.0.0.59 형태 다양
        """
        major = str(major_version).split(".")[0]
        if major in SAMSUNG_VERSION_MAP:
            info = SAMSUNG_VERSION_MAP[major]
            patch = random.choice(info["patches"])
            # 패치가 "X.Y" 형식이면 그대로 사용 (예: "5.9" → "28.0.5.9")
            # 패치가 숫자만이면 "0.X" 형식 (예: "59" → "28.0.0.59")
            if "." in patch:
                return f"{major}.0.{patch}"
            else:
                return f"{major}.0.0.{patch}"
        return f"{major}.0.0.0"
    
    def get_opera_chromium_version(opera_major):
        """Opera → Chromium 버전 (모바일/데스크톱 자동 판별)"""
        major = str(opera_major).split(".")[0]
        # 모바일 Opera는 80~99 범위
        if major in OPERA_MOBILE_VERSION_MAP:
            return OPERA_MOBILE_VERSION_MAP[major]["chromium"]
        # 데스크톱 Opera는 100+ 범위
        if major in OPERA_VERSION_MAP:
            return OPERA_VERSION_MAP[major]["chromium"]
        return "142"
    
    def get_samsung_chromium_version(samsung_major):
        """Samsung → Chromium 버전"""
        major = str(samsung_major).split(".")[0]
        if major in SAMSUNG_VERSION_MAP:
            return SAMSUNG_VERSION_MAP[major]["chromium"]
        return "140"
    
    def get_edge_full_version(major_version):
        """Edge 메이저 → 상세 버전 (Edge 자체 빌드)"""
        major = str(major_version).split(".")[0]
        if major in EDGE_VERSION_MAP:
            info = EDGE_VERSION_MAP[major]
            patch = random.choice(info["patches"])
            return f"{major}.0.{info['build']}.{patch}"
        return f"{major}.0.0.0"

# ============================================
# 설정
# ============================================
CONFIG = {
    # 크롬 디버깅 포트
    "chrome_port": 9222,
    
    # 네이버 모바일 검색 URL
    "naver_mobile_url": "https://naver.com",
    
    # 찾을 텍스트
    "target_text": "검색결과 더보기",
    
    # 검색 실행 모드: 1=엔터, 2=돋보기 클릭, 3=랜덤
    "search_mode": 3,
    
    # 통합 페이지에서 먼저 찾기: True=통합에서 먼저 찾고 없으면 더보기, False=바로 더보기
    "search_in_total_first": True,
    
    # ──────────────────────────────────────────
    # 체류 시간 설정 (초)
    # ──────────────────────────────────────────
    # 타겟 사이트 도착 후 체류 시간
    "stay_min": 10,   # 최소 체류 시간 (초)
    "stay_max": 20,   # 최대 체류 시간 (초)
    
    # ──────────────────────────────────────────
    # 작업 완료 후 브라우저 종료
    # ──────────────────────────────────────────
    # True: 작업 완료 후 크롬 브라우저 종료
    # False: 브라우저 유지
    "close_browser_on_finish": True,
    
    # 브라우저 창 크기 (모바일)
    "viewport": {
        "width": 375,
        "height": 812
    },
    
    # 터치 스크롤 설정
    "scroll": {
        "distance": 300,
        "distance_random": 50,
        "delay": 0.1,
        "delay_random": 0.05,
        "steps": 10,
        "step_delay": 0.015
    },
    
    # 스크롤 후 읽기 멈춤 설정
    "reading_pause": {
        "enabled": True,
        "probability": 0.2,    # 20% 확률로 멈춤
        "min_time": 2.0,       # 최소 2초
        "max_time": 4.0        # 최대 4초
    },
    
    # 터치 좌표 랜덤 범위
    "touch_random": {
        "x_range": 50,
        "y_range": 30
    },
    
    # 터치 속성 (모바일 손가락 시뮬레이션)
    "touch_properties": {
        # 손가락 반지름 범위 (픽셀)
        "radius_min": 5,
        "radius_max": 15,
        # 터치 압력 범위 (0~1)
        "force_min": 0.3,
        "force_max": 0.7
    },
    
    # 타이핑 설정
    "typing": {
        # 글자 간 딜레이 (초)
        "char_delay": 0.55,
        # 딜레이 랜덤 범위 (±)
        "char_delay_random": 0.53
    },
    
    # 요소 대기 설정
    "wait": {
        # 최대 대기 시간 (초)
        "timeout": 20,
        # 체크 간격 (초)
        "interval": 0.3,
        # 요소 발견 후 추가 딜레이 (초)
        "after_found_delay": 3.5,
        "after_found_delay_random": 2.3
    },
    
    # 페이지 로딩 대기 설정 (클릭 후 페이지 이동 대기)
    "page_load": {
        # 최대 대기 시간 (초)
        "timeout": 120,
        # 체크 간격 (초)
        "check_interval": 0.5,
        # 로딩 실패 시 재시도 횟수
        "retry_count": 1,
        # 로딩 완료 후 대기 시간 (사람처럼 페이지 훑어보기)
        "after_load_min": 2.0,
        "after_load_max": 4.0
    },
    
    # 재시도 설정
    "retry": {
        # 요소 대기 1회당 최대 시도 횟수
        "max_element_retry": 30,
        # 전체 재시도 횟수 (30번 실패 시 처음부터 다시)
        "max_full_retry": 2,
        # 5단계(더보기 찾기) 페이지 재이동 재시도 횟수
        "step5_full_retry": 1,
        # 6단계(더보기 클릭) 클릭 시도 횟수
        "step6_click_retry": 5,
        # 6단계 페이지 재이동 재시도 횟수
        "step6_full_retry": 1,
        # 새로고침/재이동 후 대기 시간 (초)
        "after_refresh_delay": 2.0,
        # 페이지 오류 텍스트 (이 텍스트 있으면 페이지 오류로 판단)
        "error_texts": ["연결할 수 없습니다", "페이지를 찾을 수 없습니다", "오류가 발생", "ERR_", "시간이 초과"]
    },
    
    # 요소 selectors (우선순위대로, 바뀌면 여기만 수정)
    "selectors": {
        # 메인 페이지 검색창
        "search_fake": ["#MM_SEARCH_FAKE", "input.sch_input", "input[type='search']"],
        # 검색 모드 실제 입력창
        "search_real": ["input#query", "#query", "input.sch_input[data-focus]"],
        # 더보기 페이지 검색창 (continue 모드용)
        "search_more": ["input#nx_query", "#nx_query"],
        # 검색 버튼 (돋보기)
        "search_button": ["button.sch_btn_search", ".sch_btn_search", "button.btn_search", "button[type='submit']"],
        # 검색 결과 확인용 요소
        "search_result": [".search_result", ".lst_total", "#content", ".api_subject_bx"]
    },
    
    # 최대 스크롤 횟수
    "max_scrolls": 50,
    
    # 4.5단계(통합 페이지) 최대 스크롤 횟수
    "max_scrolls_total": 30,
    
    # 결과 메시지
    "done_value": "SCROLL:DONE",
    "not_found_value": "SCROLL:NOTFOUND",
    "error_value": "SCROLL:ERROR",
    
    # 결과 파일 경로
    "result_file": "C:\\exload\\python\\result.txt",
    
    # UA 파일 설정
    "ua_files": {
        # UA 리스트 파일 경로
        "base_path": "C:\\exload\\python\\ua_lists\\mo",
        
        # 브라우저별 파일 및 확률 (weight 합계 = 100)
        "browsers": {
            "chrome":      {"file": "chrome.txt",      "weight": 30},
            "samsung":     {"file": "samsung.txt",     "weight": 20},
            "safari_ios":  {"file": "safari_ios.txt",  "weight": 20},
            "opera":       {"file": "opera.txt",       "weight": 10},
            "firefox":     {"file": "firefox.txt",     "weight": 5},
            "edge":        {"file": "edge.txt",        "weight": 5},
            "chrome_ios":  {"file": "chrome_ios.txt",  "weight": 10},
        }
    },
    
    # 모바일 에뮬레이션 설정
    "mobile_emulation": {
        # 모델명 (None이면 랜덤)
        "model": None,
        
        # 플랫폼 버전 (None이면 랜덤)
        "platform_version": None,
        
        # 해상도 프리셋 (None이면 랜덤)
        "preset": None,
    }
}

# ============================================
# 모바일 디바이스 설정
# ============================================
MOBILE_CONFIG = {
    # 브라우저별 UA (2025년 12월 기준 최신)
    "browser_uas": {
        "chrome": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36",
        "samsung": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/142.0.0.0 Mobile Safari/537.36",
        "opera": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 OPR/88.0.0.0",
        "firefox": "Mozilla/5.0 (Android 16; Mobile; rv:143.0) Gecko/143.0 Firefox/143.0",
        "edge": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0",
        "safari_ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1",
        "chrome_ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_1_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/143.0.7499.108 Mobile/15E148 Safari/604.1",
    },
    
    # ============================================
    # 아이폰 해상도 프리셋 (실제 디바이스 데이터 기준)
    # 출처: ios-resolution.com, 실폰 테스트
    # br_sr: inner (뷰포트), device_sr: screen (logical resolution)
    # iOS는 screen = availWidth = outer 동일, inner만 다름
    # ============================================
    "iphone_presets": [
        # iPhone 16 Pro Max (6.9") - 2024-09
        {"model": "iPhone 16 Pro Max", "br_sr": "440x852", "device_sr": "440x956", "inner_height": 852, "outer_height": 956, "dpr": 3.0},
        # iPhone 16 Pro (6.3") - 2024-09
        {"model": "iPhone 16 Pro", "br_sr": "402x778", "device_sr": "402x874", "inner_height": 778, "outer_height": 874, "dpr": 3.0},
        # iPhone 16 Plus (6.7") - 2024-09
        {"model": "iPhone 16 Plus", "br_sr": "430x828", "device_sr": "430x932", "inner_height": 828, "outer_height": 932, "dpr": 3.0},
        # iPhone 16 (6.1") - 2024-09
        {"model": "iPhone 16", "br_sr": "393x748", "device_sr": "393x852", "inner_height": 748, "outer_height": 852, "dpr": 3.0},
        # iPhone 16e (6.1") - 2025-02 (저가형)
        {"model": "iPhone 16e", "br_sr": "390x740", "device_sr": "390x844", "inner_height": 740, "outer_height": 844, "dpr": 3.0},
        # iPhone 15 Pro Max (6.7") - 2023-09
        {"model": "iPhone 15 Pro Max", "br_sr": "430x828", "device_sr": "430x932", "inner_height": 828, "outer_height": 932, "dpr": 3.0},
        # iPhone 15 Pro (6.1") - 2023-09
        {"model": "iPhone 15 Pro", "br_sr": "393x748", "device_sr": "393x852", "inner_height": 748, "outer_height": 852, "dpr": 3.0},
        # iPhone 15 Plus (6.7") - 2023-09
        {"model": "iPhone 15 Plus", "br_sr": "430x828", "device_sr": "430x932", "inner_height": 828, "outer_height": 932, "dpr": 3.0},
        # iPhone 15 (6.1") - 2023-09
        {"model": "iPhone 15", "br_sr": "393x748", "device_sr": "393x852", "inner_height": 748, "outer_height": 852, "dpr": 3.0},
        # iPhone 14 Pro Max (6.7") - 2022-09
        {"model": "iPhone 14 Pro Max", "br_sr": "430x828", "device_sr": "430x932", "inner_height": 828, "outer_height": 932, "dpr": 3.0},
        # iPhone 14 Pro (6.1") - 2022-09
        {"model": "iPhone 14 Pro", "br_sr": "393x748", "device_sr": "393x852", "inner_height": 748, "outer_height": 852, "dpr": 3.0},
        # iPhone 14 Plus (6.7") - 2022-10
        {"model": "iPhone 14 Plus", "br_sr": "428x822", "device_sr": "428x926", "inner_height": 822, "outer_height": 926, "dpr": 3.0},
        # iPhone 14 (6.1") - 2022-09
        {"model": "iPhone 14", "br_sr": "390x740", "device_sr": "390x844", "inner_height": 740, "outer_height": 844, "dpr": 3.0},
        # iPhone 13 Pro Max (6.7") - 2021-09
        {"model": "iPhone 13 Pro Max", "br_sr": "428x822", "device_sr": "428x926", "inner_height": 822, "outer_height": 926, "dpr": 3.0},
        # iPhone 13 Pro (6.1") - 2021-09
        {"model": "iPhone 13 Pro", "br_sr": "390x740", "device_sr": "390x844", "inner_height": 740, "outer_height": 844, "dpr": 3.0},
        # iPhone 13 (6.1") - 2021-09
        {"model": "iPhone 13", "br_sr": "390x740", "device_sr": "390x844", "inner_height": 740, "outer_height": 844, "dpr": 3.0},
        # iPhone 13 mini (5.4") - 2021-09
        {"model": "iPhone 13 mini", "br_sr": "375x708", "device_sr": "375x812", "inner_height": 708, "outer_height": 812, "dpr": 3.0},
    ],
}

# ============================================
# 안드로이드 모델별 스펙 (Android 버전 + DPR + 해상도)
# br_sr: 브라우저 inner (뷰포트), device_sr: screen (전체 화면)
# 실폰 기준: screen > outer > inner (상태바, 주소창 높이만큼 차이)
# ============================================
MODEL_SPECS = {
    # Samsung Galaxy S24 시리즈 (2024년 출시, Android 14→15)
    "SM-S928B": {  # S24 Ultra
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",      # inner (screen - ~100px)
        "device_sr": "412x915",  # screen
    },
    "SM-S926B": {  # S24+
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-S921B": {  # S24
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    
    # Samsung Galaxy S23 시리즈 (2023년 출시, Android 13→15)
    "SM-S918B": {  # S23 Ultra
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-S916B": {  # S23+
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-S911B": {  # S23
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    
    # Samsung Galaxy S22 시리즈 (2022년 출시, Android 12→15)
    "SM-S908B": {  # S22 Ultra
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-S906B": {  # S22+
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-S901B": {  # S22
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    
    # Samsung Galaxy S21 시리즈 (2021년 출시, Android 11→14)
    "SM-G998B": {  # S21 Ultra
        "android": ["13.0.0", "14.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-G996B": {  # S21+
        "android": ["13.0.0", "14.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-G991B": {  # S21
        "android": ["13.0.0", "14.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    
    # Samsung Galaxy Z Fold 시리즈
    "SM-F956B": {  # Z Fold6 (2024, Android 14→15)
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "411x830",      # inner
        "device_sr": "412x960",  # screen
    },
    "SM-F946B": {  # Z Fold5 (2023, Android 13→15)
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "411x830",
        "device_sr": "412x960",
    },
    "SM-F936B": {  # Z Fold4 (2022, Android 12→14)
        "android": ["13.0.0", "14.0.0"],
        "dpr": 2.625,
        "br_sr": "411x830",
        "device_sr": "412x960",
    },
    "SM-F966N": {  # Z Fold6 5G 한국판 (2024, Android 14→16) - 실폰 확인
        "android": ["15.0.0", "16.0.0"],
        "dpr": 2.625,
        "br_sr": "411x774",      # 실폰: inner 411x774
        "device_sr": "412x960",  # 실폰: screen 412x960
    },
    
    # Samsung Galaxy Z Flip 시리즈
    "SM-F741B": {  # Z Flip6 (2024, Android 14→15)
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    "SM-F731B": {  # Z Flip5 (2023, Android 13→15)
        "android": ["14.0.0", "15.0.0"],
        "dpr": 3.0,
        "br_sr": "412x862",
        "device_sr": "412x915",
    },
    
    # Samsung Galaxy A 시리즈
    "SM-A556E": {  # A55 (2024, Android 14)
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x883",
        "device_sr": "415x1020",
    },
    "SM-A546E": {  # A54 (2023, Android 13→14)
        "android": ["13.0.0", "14.0.0"],
        "dpr": 2.625,
        "br_sr": "412x883",
        "device_sr": "415x1020",
    },
    "SM-A536E": {  # A53 (2022, Android 12→14)
        "android": ["13.0.0", "14.0.0"],
        "dpr": 2.625,
        "br_sr": "412x883",
        "device_sr": "415x1020",
    },
    
    # Samsung Galaxy F 시리즈
    "SM-E546": {  # F54 (2023)
        "android": ["13.0.0", "14.0.0"],
        "dpr": 2.625,
        "br_sr": "412x860",
        "device_sr": "415x1100",
    },
    
    # Google Pixel 시리즈
    "Pixel 8 Pro": {  # 2023, Android 14→15
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x860",
        "device_sr": "415x1100",
    },
    "Pixel 8": {  # 2023, Android 14→15
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x860",
        "device_sr": "415x1100",
    },
    "Pixel 7 Pro": {  # 2022, Android 13→15
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x845",
        "device_sr": "415x1080",
    },
    "Pixel 7": {  # 2022, Android 13→15
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x860",
        "device_sr": "415x1100",
    },
    "Pixel 6 Pro": {  # 2021, Android 12→15
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x845",
        "device_sr": "415x1080",
    },
    "Pixel 6": {  # 2021, Android 12→15
        "android": ["14.0.0", "15.0.0"],
        "dpr": 2.625,
        "br_sr": "412x860",
        "device_sr": "415x1100",
    },
}

# 모델 목록 (MODEL_SPECS에서 추출)
ANDROID_MODELS = list(MODEL_SPECS.keys())

# 모델명 → GPU 매핑 (Firefox용)
MODEL_GPU_MAP = {
    # 삼성 S24 시리즈 (Snapdragon 8 Gen 3)
    "SM-S928B": "Adreno (TM) 750", "SM-S926B": "Adreno (TM) 750", "SM-S921B": "Adreno (TM) 750",
    # 삼성 S23 시리즈 (Snapdragon 8 Gen 2)
    "SM-S918B": "Adreno (TM) 740", "SM-S916B": "Adreno (TM) 740", "SM-S911B": "Adreno (TM) 740",
    # 삼성 S22 시리즈 (Snapdragon 8 Gen 1)
    "SM-S908B": "Adreno (TM) 730", "SM-S906B": "Adreno (TM) 730", "SM-S901B": "Adreno (TM) 730",
    # 삼성 S21 시리즈
    "SM-G998B": "Adreno (TM) 660", "SM-G996B": "Adreno (TM) 660", "SM-G991B": "Adreno (TM) 660",
    # 삼성 폴드/플립
    "SM-F966N": "Adreno (TM) 830", "SM-F956B": "Adreno (TM) 750", "SM-F946B": "Adreno (TM) 740",
    "SM-F936B": "Adreno (TM) 730", "SM-F926B": "Adreno (TM) 660",
    # 삼성 A 시리즈
    "SM-A546E": "Adreno (TM) 642L", "SM-A536E": "Adreno (TM) 619", "SM-E546": "Adreno (TM) 610",
    # Pixel (Google Tensor - Mali GPU)
    "Pixel 8 Pro": "Mali-G715", "Pixel 8": "Mali-G715", 
    "Pixel 7 Pro": "Mali-G710", "Pixel 7": "Mali-G710",
    "Pixel 6 Pro": "Mali-G78", "Pixel 6": "Mali-G78",
    "_default": "Adreno (TM) 650",
}

# 모델별 GPU Vendor 매핑
MODEL_GPU_VENDOR_MAP = {
    # Pixel은 ARM Mali (Google 표기)
    "Pixel 8 Pro": "Google Inc. (ARM)", "Pixel 8": "Google Inc. (ARM)",
    "Pixel 7 Pro": "Google Inc. (ARM)", "Pixel 7": "Google Inc. (ARM)",
    "Pixel 6 Pro": "Google Inc. (ARM)", "Pixel 6": "Google Inc. (ARM)",
    # 삼성/기타는 Qualcomm
    "_default": "Qualcomm",
}

# 모델별 deviceMemory (GB)
MODEL_MEMORY_MAP = {
    # 삼성 S24 시리즈 (12GB)
    "SM-S928B": 8, "SM-S926B": 8, "SM-S921B": 8,
    # 삼성 S23 시리즈 (8GB)
    "SM-S918B": 8, "SM-S916B": 8, "SM-S911B": 8,
    # 삼성 S22 시리즈 (8GB)
    "SM-S908B": 8, "SM-S906B": 8, "SM-S901B": 8,
    # 삼성 S21 시리즈 (8GB)
    "SM-G998B": 8, "SM-G996B": 8, "SM-G991B": 8,
    # 삼성 폴드/플립 (12GB/8GB)
    "SM-F966N": 8, "SM-F956B": 8, "SM-F946B": 8,
    "SM-F936B": 8, "SM-F926B": 8,
    # 삼성 A 시리즈 (6GB/4GB)
    "SM-A546E": 8, "SM-A536E": 6, "SM-E546": 4,
    # Pixel
    "Pixel 8 Pro": 8, "Pixel 8": 8,
    "Pixel 7 Pro": 8, "Pixel 7": 8,
    "Pixel 6 Pro": 8, "Pixel 6": 8,
    "_default": 8,
}

# 모델별 Android 버전 (platformVersion) - 최신 업데이트 기준
MODEL_ANDROID_VERSION_MAP = {
    # 삼성 S24 시리즈 (Android 14 출시, 15 업데이트)
    "SM-S928B": "15.0.0", "SM-S926B": "15.0.0", "SM-S921B": "15.0.0",
    # 삼성 S23 시리즈 (Android 13 출시, 15 업데이트)
    "SM-S918B": "15.0.0", "SM-S916B": "15.0.0", "SM-S911B": "15.0.0",
    # 삼성 S22 시리즈 (Android 12 출시, 15 업데이트)
    "SM-S908B": "15.0.0", "SM-S906B": "15.0.0", "SM-S901B": "15.0.0",
    # 삼성 S21 시리즈 (Android 11 출시, 14 업데이트)
    "SM-G998B": "14.0.0", "SM-G996B": "14.0.0", "SM-G991B": "14.0.0",
    # 삼성 폴드6/플립6 (Android 14 출시, 15 업데이트)
    "SM-F966N": "16.0.0", "SM-F956B": "15.0.0",
    # 삼성 폴드5/플립5 (Android 13 출시, 15 업데이트)
    "SM-F946B": "15.0.0", "SM-F936B": "14.0.0",
    # 삼성 폴드4/플립4
    "SM-F926B": "14.0.0",
    # 삼성 A 시리즈
    "SM-A546E": "14.0.0", "SM-A536E": "14.0.0", "SM-E546": "13.0.0",
    # Pixel 8 시리즈 (Android 14 출시, 15 업데이트)
    "Pixel 8 Pro": "15.0.0", "Pixel 8": "15.0.0",
    # Pixel 7 시리즈 (Android 13 출시, 15 업데이트)
    "Pixel 7 Pro": "15.0.0", "Pixel 7": "15.0.0",
    # Pixel 6 시리즈 (Android 12 출시, 15 업데이트)
    "Pixel 6 Pro": "15.0.0", "Pixel 6": "15.0.0",
    "_default": "14.0.0",
}


def save_result(value):
    """결과를 파일로 저장"""
    try:
        with open(CONFIG["result_file"], "w", encoding="utf-8") as f:
            f.write(value)
        print(f"[결과 저장] {CONFIG['result_file']} → {value}")
    except Exception as e:
        print(f"[결과 저장 실패] {e}")
        try:
            pyperclip.copy(value)
            print(f"[클립보드 대체] {value}")
        except:
            pass

# ============================================
# CDP 연결
# ============================================
def get_websocket_url():
    """활성 탭의 WebSocket URL 가져오기"""
    try:
        response = requests.get(f"http://localhost:{CONFIG['chrome_port']}/json")
        tabs = response.json()
        
        # 네이버 탭 찾기 (검색 페이지 또는 메인)
        for tab in tabs:
            url = tab.get("url", "")
            if "m.search.naver.com" in url or "m.naver.com" in url:
                return tab["webSocketDebuggerUrl"]
        
        # 못 찾으면 첫 번째 페이지 탭
        for tab in tabs:
            if tab.get("type") == "page":
                return tab["webSocketDebuggerUrl"]
        
        print("[오류] 활성 탭을 찾을 수 없습니다.")
        return None
    except Exception as e:
        print(f"[오류] 크롬 연결 실패: {e}")
        print("크롬이 --remote-debugging-port=9222 로 실행되었는지 확인하세요.")
        return None

class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url)
        self.msg_id = 0
    
    def send(self, method, params=None):
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        
        # 응답 대기
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") == self.msg_id:
                return response.get("result", {})
    
    def enable_touch_emulation(self):
        """터치 에뮬레이션 활성화 (터치 포인트 표시됨)"""
        self.send("Emulation.setEmitTouchEventsForMouse", {
            "enabled": True,
            "configuration": "mobile"
        })
        self.send("Emulation.setTouchEmulationEnabled", {
            "enabled": True,
            "maxTouchPoints": 1
        })
        print("[설정] 터치 에뮬레이션 활성화")
    
    def type_text(self, text):
        """텍스트 입력 (키보드 이벤트)"""
        typing_config = CONFIG["typing"]
        
        print(f"[타이핑 시작] '{text}' ({len(text)}글자)")
        
        for i, char in enumerate(text):
            # 각 글자 입력
            self.send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char
            })
            self.send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "text": char
            })
            
            # 랜덤 딜레이
            delay = typing_config["char_delay"]
            delay_random = typing_config["char_delay_random"]
            actual_delay = delay + random.uniform(-delay_random, delay_random)
            actual_delay = max(0.01, actual_delay)  # 최소 딜레이 보장
            
            print(f"  [{i+1}/{len(text)}] '{char}' 입력, 딜레이: {actual_delay:.3f}초")
            time.sleep(actual_delay)
        
        print(f"[타이핑 완료] '{text}'")
    
    def press_enter(self):
        """Enter 키 입력"""
        # rawKeyDown (실제 키 누름)
        self.send("Input.dispatchKeyEvent", {
            "type": "rawKeyDown",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13,
            "text": "\r"
        })
        # char (문자 입력)
        self.send("Input.dispatchKeyEvent", {
            "type": "char",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13,
            "text": "\r"
        })
        # keyUp (키 뗌)
        self.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13
        })
        print("[입력] Enter 키 입력")
    
    def navigate(self, url, wait=3):
        """페이지 이동"""
        self.send("Page.navigate", {"url": url})
        time.sleep(wait)  # 페이지 로딩 대기
        print(f"[이동] {url}")
    
    def close(self):
        self.ws.close()


# ============================================
# UA 파싱 함수
# ============================================
def parse_ua(ua):
    """UA 문자열 파싱 - 플랫폼, 브라우저, 버전 추출"""
    result = {
        "platform": "unknown",
        "is_mobile": False,
        "browser": "unknown",
        "browser_version": "0.0.0.0",
        "chromium_version": None,
        "is_ios_safari": False,
        "is_firefox": False,
        "needs_hints": True,
    }
    
    ua_lower = ua.lower()
    
    # 플랫폼 감지
    if "iphone" in ua_lower or "ipad" in ua_lower:
        result["platform"] = "iOS"
        result["is_mobile"] = True
        result["needs_hints"] = False
        if not re.search(r'CriOS|FxiOS|EdgiOS|OPR|Chrome', ua, re.I):
            result["is_ios_safari"] = True
    elif "android" in ua_lower:
        result["platform"] = "Android"
        result["is_mobile"] = True
    elif "windows" in ua_lower:
        result["platform"] = "Windows"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        result["platform"] = "macOS"
    elif "linux" in ua_lower:
        result["platform"] = "Linux"
    
    # Firefox 감지
    if re.search(r'Firefox/', ua, re.I) and not re.search(r'Chrome|Chromium', ua, re.I):
        result["is_firefox"] = True
        result["needs_hints"] = False
        m = re.search(r'Firefox/([\d.]+)', ua, re.I)
        if m:
            result["browser"] = "Firefox"
            result["browser_version"] = normalize_version(m.group(1))
        return result
    
    # 브라우저 및 버전 감지
    browser_patterns = [
        (r'SamsungBrowser/([\d.]+)', "Samsung Internet"),
        (r'EdgA/([\d.]+)', "Microsoft Edge"),
        (r'Edg/([\d.]+)', "Microsoft Edge"),
        (r'OPR/([\d.]+)', "Opera"),
        (r'CriOS/([\d.]+)', "Chrome iOS"),
        (r'Chrome/([\d.]+)', "Google Chrome"),
        (r'Version/([\d.]+).*Safari', "Safari"),
    ]
    
    for pattern, browser_name in browser_patterns:
        m = re.search(pattern, ua, re.I)
        if m:
            result["browser"] = browser_name
            result["browser_version"] = normalize_version(m.group(1))
            break
    
    # Chromium 버전 추출
    m = re.search(r'Chrome/([\d.]+)', ua, re.I)
    if m:
        result["chromium_version"] = normalize_version(m.group(1))
    
    return result


def normalize_version(version):
    """버전을 x.x.x.x 형식으로 정규화"""
    if not version:
        return "0.0.0.0"
    parts = version.split(".")[:4]
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts)


def select_random_ua_from_files():
    """
    UA 파일에서 확률 기반으로 브라우저 선택 후 랜덤 UA 반환
    
    Returns:
        tuple: (browser_type, ua_string) 또는 실패 시 (None, None)
    """
    import os
    
    ua_config = CONFIG.get("ua_files", {})
    base_path = ua_config.get("base_path", "C:\\exload\\python\\ua_lists")
    browsers = ua_config.get("browsers", {})
    
    if not browsers:
        print("[오류] ua_files.browsers 설정이 없습니다")
        return None, None
    
    # 1. 확률 기반 브라우저 선택
    total_weight = sum(b["weight"] for b in browsers.values())
    rand_val = random.randint(1, total_weight)
    
    cumulative = 0
    selected_browser = None
    selected_file = None
    
    for browser_type, config in browsers.items():
        cumulative += config["weight"]
        if rand_val <= cumulative:
            selected_browser = browser_type
            selected_file = config["file"]
            break
    
    if not selected_browser or not selected_file:
        print("[오류] 브라우저 선택 실패")
        return None, None
    
    # 2. 선택된 파일에서 UA 랜덤 선택
    file_path = os.path.join(base_path, selected_file)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            ua_list = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        if not ua_list:
            print(f"[오류] {selected_file} 파일이 비어있습니다")
            return None, None
        
        selected_ua = random.choice(ua_list)
        print(f"[UA 선택] {selected_browser} ({len(ua_list)}개 중 랜덤)")
        print(f"[UA] {selected_ua[:80]}...")
        
        return selected_browser, selected_ua
        
    except FileNotFoundError:
        print(f"[오류] UA 파일을 찾을 수 없습니다: {file_path}")
        return None, None
    except Exception as e:
        print(f"[오류] UA 파일 읽기 실패: {e}")
        return None, None


def generate_random_mobile_ip():
    """모바일/WiFi 내부 IP 랜덤 생성"""
    patterns = [
        lambda: f"192.0.0.{random.randint(2, 254)}",
        lambda: f"100.{random.randint(64, 127)}.{random.randint(0, 255)}.{random.randint(2, 254)}",
        lambda: f"192.168.{random.randint(0, 255)}.{random.randint(2, 254)}",
        lambda: f"172.{random.randint(16, 31)}.{random.randint(0, 255)}.{random.randint(2, 254)}",
        lambda: f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(2, 254)}",
    ]
    return random.choice(patterns)()


def generate_client_hints(ua_info, browser, browser_version, model, platform_version):
    """SEC-CH-UA 힌트 정보 생성 (버전 매핑 적용)"""
    if not ua_info.get("needs_hints", True):
        return None
    
    major = browser_version.split(".")[0]
    chromium_version = ua_info.get("chromium_version", browser_version)
    chromium_major = chromium_version.split(".")[0] if chromium_version else major
    
    # ========================================
    # 상세 버전 생성 (버전 매핑 적용)
    # UA는 메이저만, fullVersionList는 상세버전 필요
    # ========================================
    # Samsung은 Chromium 빌드/패치가 다름
    if browser == "Samsung Internet":
        chromium_full = get_samsung_chromium_full_version(chromium_major)
    else:
        chromium_full = get_chrome_full_version(chromium_major)
    
    # 브라우저별 상세 버전
    if browser == "Opera":
        browser_full = get_opera_mobile_full_version(major)  # 모바일용!
        # Opera Mobile은 별도로 Opera Desktop 버전을 보고함! (버전별로 다름)
        opera_desktop_major = OPERA_MOBILE_TO_DESKTOP_MAP.get(major, "126")
        # Opera Desktop 상세 버전
        if opera_desktop_major in OPERA_DESKTOP_VERSION_MAP:
            desk_info = OPERA_DESKTOP_VERSION_MAP[opera_desktop_major]
            desk_patch = random.choice(desk_info["patches"])
            opera_desktop_full = f"{opera_desktop_major}.0.{desk_info['build']}.{desk_patch}"
        else:
            opera_desktop_full = f"{opera_desktop_major}.0.0.0"
    elif browser == "Samsung Internet":
        browser_full = get_samsung_full_version(major)
    elif browser == "Microsoft Edge":
        browser_full = get_edge_full_version(major)  # Edge는 자체 빌드!
    else:
        browser_full = chromium_full
    
    print(f"[버전 매핑] Chromium: {chromium_major} → {chromium_full}")
    if browser in ["Opera", "Samsung Internet", "Microsoft Edge"]:
        print(f"[버전 매핑] {browser}: {major} → {browser_full}")
    if browser == "Opera":
        print(f"[버전 매핑] Opera Desktop: {opera_desktop_major} → {opera_desktop_full}")
    
    # ========================================
    # 실폰 테스트 결과 기반 브라우저별 설정
    # ========================================
    # Chrome: Chrome → Chromium → Grease (버전별로 다름!)
    # Samsung: Chromium → Samsung → Grease (Not.A/Brand v99)
    # Opera: ;Not A Brand → Opera(Desktop) → OperaMobile → Chromium (실제 순서!)
    # Edge: Chromium → Edge → Grease (Not_A Brand v99)
    
    # Chrome 버전별 GREASE 값 결정
    chromium_major_int = int(chromium_major) if chromium_major.isdigit() else 100
    
    if browser == "Google Chrome":
        # Chrome 110+ : "Not A(Brand", version 24, 순서: Chrome → Chromium → GREASE
        # Chrome 109 이하: "Not?A_Brand", version 8, 순서: Chrome → GREASE → Chromium
        if chromium_major_int >= 110:
            grease = "Not A(Brand"
            grease_version = "24"
            order = ["Google Chrome", "Chromium", "GREASE"]
        else:
            grease = "Not?A_Brand"
            grease_version = "8"
            order = ["Google Chrome", "GREASE", "Chromium"]
        
    elif browser == "Samsung Internet":
        grease = "Not.A/Brand"
        grease_version = "99"
        order = ["Chromium", "Samsung Internet", "GREASE"]
        
    elif browser == "Opera":
        # 버전별 GREASE 형식 (실폰 확인 - 버전마다 다름!)
        grease = OPERA_MOBILE_GREASE_MAP.get(major, ";Not A Brand")
        grease_version = "99"
        # 버전별 brands 순서 (실폰 확인 - 버전마다 다름!)
        order = OPERA_MOBILE_BRANDS_ORDER_MAP.get(major, ["GREASE", "Opera", "OperaMobile", "Chromium"])
        
    elif browser == "Microsoft Edge":
        grease = "Not_A Brand"
        grease_version = "99"
        order = ["Chromium", "Microsoft Edge", "GREASE"]
        
    else:
        # 기타 브라우저도 버전에 따라
        if chromium_major_int >= 110:
            grease = "Not A(Brand"
            grease_version = "24"
            order = ["Google Chrome", "Chromium", "GREASE"]
        else:
            grease = "Not?A_Brand"
            grease_version = "8"
            order = ["Google Chrome", "GREASE", "Chromium"]
    
    brands = []
    full_version_list = []
    
    # 브랜드 정보 (상세 버전 적용)
    # Samsung brands는 "29.0" 형식 (major + ".0")
    samsung_major_with_zero = f"{major}.0" if browser == "Samsung Internet" else major
    
    # Opera는 Desktop 버전(126)과 Mobile 버전(93)이 다름!
    if browser == "Opera":
        brand_info = {
            "Chromium": {"major": chromium_major, "full": chromium_full},
            "Opera": {"major": opera_desktop_major, "full": opera_desktop_full},  # Desktop 126!
            "OperaMobile": {"major": major, "full": browser_full},  # Mobile 93
        }
    else:
        brand_info = {
            "Chromium": {"major": chromium_major, "full": chromium_full},
            "Google Chrome": {"major": chromium_major, "full": chromium_full},
            "Samsung Internet": {"major": samsung_major_with_zero, "full": browser_full},
            "Microsoft Edge": {"major": major, "full": browser_full},
        }
    
    for brand_name in order:
        if brand_name == "GREASE":
            brands.append({"brand": grease, "version": grease_version})
            full_version_list.append({"brand": grease, "version": f"{grease_version}.0.0.0"})
        elif brand_name in brand_info:
            brands.append({"brand": brand_name, "version": brand_info[brand_name]["major"]})
            full_version_list.append({"brand": brand_name, "version": brand_info[brand_name]["full"]})
    
    print(f"[Client Hints] {browser} 순서: {[b['brand'] for b in brands]}")
    print(f"[fullVersionList] {[b['version'] for b in full_version_list]}")
    
    is_mobile = ua_info["is_mobile"]
    platform = ua_info["platform"]
    
    # Opera 모바일은 formFactors가 빈 배열
    if browser == "Opera" and is_mobile:
        form_factors = []
    elif is_mobile:
        form_factors = ["Mobile"]
    else:
        form_factors = ["Desktop"]
    
    # Opera 모바일은 platformVersion이 소수점 없이 (예: "16")
    if browser == "Opera" and is_mobile:
        pv = platform_version or "14.0.0"
        platform_ver = pv.split(".")[0]  # "16.0.0" → "16"
    else:
        platform_ver = platform_version or "14.0.0"
    
    return {
        "brands": brands,
        "fullVersionList": full_version_list,
        "mobile": is_mobile,
        "platform": platform,
        "platformVersion": platform_ver,
        "architecture": "" if is_mobile else "x86",
        "bitness": "" if is_mobile else "64",
        "model": model or "" if platform == "Android" else "",
        "wow64": False,
        "formFactors": form_factors,
    }


# ============================================
# 모바일 에뮬레이션 설정 (핵심!)
# ============================================
def setup_mobile_emulation(cdp, ua, browser_type=None, model=None, preset=None, platform_version=None):
    """
    완벽한 모바일 에뮬레이션 설정
    
    Args:
        cdp: CDP 인스턴스
        ua: User-Agent 문자열
        browser_type: 브라우저 타입 (파일명 기반, UA 파싱보다 우선)
        model: 안드로이드 모델명 (None이면 랜덤)
        preset: 해상도 프리셋 (None이면 랜덤)
        platform_version: 플랫폼 버전 (None이면 랜덤)
    """
    
    # Network/Page 도메인 활성화
    cdp.send("Network.enable", {})
    cdp.send("Page.enable", {})
    
    # UA 파싱
    ua_info = parse_ua(ua)
    
    # browser_type이 명시적으로 전달되면 파싱 결과 덮어쓰기 (파일명 기반이 더 정확)
    if browser_type:
        browser_type_map = {
            "chrome": ("Google Chrome", False, False),
            "samsung": ("Samsung Internet", False, False),
            "opera": ("Opera", False, False),
            "firefox": ("Firefox", True, False),
            "edge": ("Microsoft Edge", False, False),
            "safari_ios": ("Safari", False, True),
            "chrome_ios": ("Chrome iOS", False, False),
        }
        if browser_type in browser_type_map:
            mapped = browser_type_map[browser_type]
            ua_info["browser"] = mapped[0]
            ua_info["is_firefox"] = mapped[1]
            ua_info["is_ios_safari"] = mapped[2]
            if browser_type in ["safari_ios", "chrome_ios"]:
                ua_info["platform"] = "iOS"
                ua_info["is_mobile"] = True
                ua_info["needs_hints"] = False
    
    print(f"\n[모바일 에뮬레이션]")
    print(f"  플랫폼: {ua_info['platform']}")
    print(f"  브라우저: {ua_info['browser']} {ua_info['browser_version']}")
    
    # 안드로이드 설정 (MODEL_SPECS 기반)
    if ua_info["platform"] == "Android":
        # 모델 선택 (없으면 랜덤)
        if model is None:
            model = random.choice(ANDROID_MODELS)
        
        # 모델 스펙 가져오기 (없으면 기본값)
        if model in MODEL_SPECS:
            spec = MODEL_SPECS[model]
            
            # Android 버전 (모델에 맞는 버전 중 랜덤)
            if platform_version is None:
                platform_version = random.choice(spec["android"])
            
            # 해상도/DPR (모델 고유값)
            preset = {
                "br_sr": spec["br_sr"],
                "device_sr": spec["device_sr"],
                "dpr": spec["dpr"]
            }
        else:
            # MODEL_SPECS에 없는 모델은 MODEL_ANDROID_VERSION_MAP에서 가져오기
            if platform_version is None:
                platform_version = MODEL_ANDROID_VERSION_MAP.get(model, MODEL_ANDROID_VERSION_MAP.get("_default", "14.0.0"))
            if preset is None:
                preset = {"br_sr": "412x915", "device_sr": "415x1100", "dpr": 2.625}
        
        print(f"  모델: {model}")
        print(f"  Android: {platform_version}")
        print(f"  해상도: {preset['br_sr']} / {preset['device_sr']} (DPR: {preset['dpr']})")
    
    # iOS 설정
    elif ua_info["platform"] == "iOS":
        if preset is None:
            preset = random.choice(MOBILE_CONFIG["iphone_presets"])
        model = ""
        m = re.search(r'OS\s+(\d+)[_.](\d+)', ua, re.I)
        if m:
            platform_version = f"{m.group(1)}.{m.group(2)}.0"
        else:
            platform_version = "18.2.0"
        print(f"  iOS 버전: {platform_version}")
        print(f"  해상도: {preset['br_sr']} (DPR: {preset['dpr']})")
    
    # 해상도 파싱
    if preset:
        br_w, br_h = map(int, preset["br_sr"].split("x"))
        dev_w, dev_h = map(int, preset["device_sr"].split("x"))
        dpr = preset["dpr"]
        # iOS는 프리셋에서 inner_height, outer_height 사용
        ios_inner_height = preset.get("inner_height")
        ios_outer_height = preset.get("outer_height")
    else:
        br_w, br_h = 412, 915
        dev_w, dev_h = 415, 1100
        dpr = 2.625
        ios_inner_height = None
        ios_outer_height = None
    
    is_mobile = ua_info["is_mobile"]
    platform = ua_info["platform"]
    browser = ua_info.get("browser", "")
    is_ios = platform == "iOS"
    is_firefox = ua_info.get("is_firefox", False)
    is_ios_safari = ua_info.get("is_ios_safari", False)
    
    # 뷰포트 크기 계산 (iOS는 프리셋 값 사용)
    if is_ios and ios_inner_height:
        viewport_height = ios_inner_height
    else:
        viewport_height = br_h
    
    if is_ios and ios_outer_height:
        outer_height = ios_outer_height
    elif is_mobile:
        outer_height = dev_h - 145
    else:
        outer_height = dev_h
    
    # 힌트 생성
    hints = None
    if ua_info.get("needs_hints", True) and is_mobile:
        hints = generate_client_hints(ua_info, browser, ua_info["browser_version"], model, platform_version)
    
    # 1. UA 설정 (Accept-Language 헤더 포함)
    accept_language = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    ua_params = {
        "userAgent": ua,
        "acceptLanguage": accept_language,
    }
    if hints:
        ua_params["userAgentMetadata"] = hints
    cdp.send("Emulation.setUserAgentOverride", ua_params)
    
    # 2. 디바이스 메트릭 설정
    cdp.send("Emulation.setDeviceMetricsOverride", {
        "width": br_w,
        "height": br_h,
        "deviceScaleFactor": dpr,
        "mobile": is_mobile,
        "screenWidth": dev_w,
        "screenHeight": dev_h,
    })
    
    # 3. 터치 에뮬레이션
    cdp.send("Emulation.setTouchEmulationEnabled", {
        "enabled": True,
        "maxTouchPoints": 5
    })
    cdp.send("Emulation.setEmitTouchEventsForMouse", {
        "enabled": True,
        "configuration": "mobile"
    })
    
    # JS 스푸핑 코드 생성 및 주입
    js_code = generate_js_spoof(ua_info, ua, model, platform_version, preset, hints)
    cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": js_code})
    
    print(f"[모바일 에뮬레이션 완료]")
    
    return {
        "ua": ua,
        "model": model,
        "preset": preset,
        "platform_version": platform_version,
    }


def generate_js_spoof(ua_info, ua, model, platform_version, preset, hints):
    """페이지 컨텍스트에 주입할 JS 스푸핑 코드 생성"""
    
    platform = ua_info["platform"]
    is_mobile = ua_info["is_mobile"]
    is_ios_safari = ua_info.get("is_ios_safari", False)
    is_firefox = ua_info.get("is_firefox", False)
    browser = ua_info.get("browser", "")
    
    # 브라우저별 플래그
    is_samsung = browser == "Samsung Internet"
    is_opera = browser == "Opera"
    is_edge = "Edg" in ua or "Edge" in browser
    is_chrome = browser in ["Chrome", "Google Chrome"] or (browser == "" and "Chrome" in ua and not is_edge and not is_opera and not is_samsung)
    is_ios = platform == "iOS"
    is_ios_chrome = is_ios and browser == "Chrome iOS"
    
    # 브라우저별 설정
    if is_ios or is_firefox:
        plugins_count = 5
    else:
        plugins_count = 0
    
    if is_samsung:
        languages_array = "['ko-KR', 'ko', 'en-US', 'en']"
        languages_count = 4
    elif is_opera and is_mobile:
        # Opera 모바일: languages 1개만
        languages_array = "['ko-KR']"
        languages_count = 1
    elif is_edge and is_mobile:
        languages_array = "['ko']"  # Edge 모바일은 ["ko"]만
        languages_count = 1
    elif is_ios:
        # iOS Safari: languages 1개만
        languages_array = "['ko-KR']"
        languages_count = 1
    elif is_chrome and is_mobile:
        languages_array = "['ko-KR', 'ko', 'en-US', 'en']"  # Chrome 모바일도 4개
        languages_count = 4
    elif is_firefox and is_mobile:
        # Firefox 모바일: languages 1개만
        languages_array = "['ko-KR']"
        languages_count = 1
    elif is_mobile:
        # Chrome/Samsung 모바일: languages 4개
        languages_array = "['ko-KR', 'ko', 'en-US', 'en']"
        languages_count = 4
    else:
        languages_array = "['ko-KR', 'ko', 'en-US', 'en']"
        languages_count = 4
    
    # language: Firefox는 "ko-KR", Edge는 "ko", 나머지는 "ko-KR"
    if is_firefox:
        language_single = "ko-KR"
    elif is_edge:
        language_single = "ko"
    else:
        language_single = "ko-KR"
    
    has_connection = not (is_ios or is_firefox)
    has_rtt = has_connection and not is_samsung and not is_opera
    hide_webrtc_ip = is_opera or is_ios
    block_webrtc = is_opera
    random_mobile_ip = generate_random_mobile_ip()
    
    # pdfViewerEnabled: iOS는 true, Firefox는 true, Android Chromium은 false
    if is_ios:
        pdf_viewer_enabled = "true"
    elif is_firefox:
        pdf_viewer_enabled = "true"
    elif is_mobile:
        pdf_viewer_enabled = "false"
    else:
        pdf_viewer_enabled = "true"
    
    # Firefox WebGL 설정 (실폰 확인)
    # webgl_vendor: "Mozilla"
    # webgl_renderer: "GPU명, or similar"
    # webgl_version: "WebGL 1.0" (짧은 버전)
    if is_firefox:
        gpu_name = MODEL_GPU_MAP.get(model, MODEL_GPU_MAP.get("_default", "Adreno (TM) 650"))
        webgl_renderer = f"{gpu_name}, or similar"
        webgl_vendor = "Mozilla"
        webgl_unmasked_vendor = MODEL_GPU_VENDOR_MAP.get(model, MODEL_GPU_VENDOR_MAP.get("_default", "Qualcomm"))
        webgl_unmasked_renderer = f"{gpu_name}, or similar"
    else:
        webgl_renderer = "WebKit WebGL"
        webgl_vendor = "WebKit"
        # 모바일은 모델별 GPU, iOS는 Apple GPU
        if is_ios:
            webgl_unmasked_vendor = "Apple Inc."
            webgl_unmasked_renderer = "Apple GPU"
        else:
            webgl_unmasked_vendor = MODEL_GPU_VENDOR_MAP.get(model, MODEL_GPU_VENDOR_MAP.get("_default", "Qualcomm"))
            webgl_unmasked_renderer = MODEL_GPU_MAP.get(model, MODEL_GPU_MAP.get("_default", "Adreno (TM) 650"))
    
    # deviceMemory: Firefox, iOS는 없음 (undefined), 모바일은 모델별, PC는 8
    if is_firefox:
        device_memory = None  # Firefox는 deviceMemory API 없음
    elif is_ios:
        device_memory = None  # iOS Safari는 deviceMemory API 없음
    elif is_mobile:
        device_memory = MODEL_MEMORY_MAP.get(model, MODEL_MEMORY_MAP.get("_default", 8))
    else:
        device_memory = 8
    
    # vendor: iOS는 Apple, Firefox는 빈 문자열, 나머지는 Google
    if is_ios:
        nav_vendor = "Apple Computer, Inc."
    elif is_firefox:
        nav_vendor = ""
    else:
        nav_vendor = "Google Inc."
    
    # hoverNone: Firefox는 true (hover: none), Chrome/Edge/Opera/Samsung 모바일은 false (hover: hover)
    if is_firefox:
        hover_none = "true"  # Firefox 모바일: hover: none
    elif is_ios:
        hover_none = "true"
    elif (is_chrome or is_edge or is_opera or is_samsung) and is_mobile:
        hover_none = "false"  # Chrome/Edge/Opera/Samsung 모바일은 hover 지원
    else:
        hover_none = "true" if is_mobile else "false"
    
    # doNotTrack: iOS는 undefined, Firefox는 "unspecified", 나머지는 null
    if is_ios:
        do_not_track = "undefined"
    elif is_firefox:
        do_not_track = '"unspecified"'
    else:
        do_not_track = "null"
    
    # audio_state: Firefox, iOS는 "suspended", 나머지는 "running"
    # audio_baseLatency: Firefox는 0, iOS는 0.00267, 나머지는 0.003
    if is_firefox:
        audio_state = "suspended"
        audio_base_latency = 0
    elif is_ios:
        audio_state = "suspended"
        audio_base_latency = 0.0026666666666666666  # iOS 실폰 값
    else:
        audio_state = "running"
        audio_base_latency = 0.003
    
    audio_sample_rate = 48000
    
    # hardwareConcurrency: iOS는 4, Android는 8
    hardware_concurrency = 4 if is_ios else 8
    
    # plugins/mimeTypes: Firefox는 5/2, iOS는 5/2, 나머지는 0/0
    if is_firefox:
        plugins_count = 5
        mime_types_count = 2
    elif is_ios:
        plugins_count = 5
        mime_types_count = 2  # 실폰 확인: 2
    else:
        plugins_count = 0
        mime_types_count = 0
    
    # userAgentData JS 스푸핑 여부
    # iOS는 userAgentData 없음 (Safari, Chrome 둘 다)
    # Firefox도 없음
    has_user_agent_data = not is_firefox and not is_ios
    
    if platform == "Android":
        nav_platform = "Linux armv81"  # 숫자 1 (실폰 확인)
    elif platform == "iOS":
        nav_platform = "iPhone"
    else:
        nav_platform = "Win32"
    
    # 해상도
    if preset:
        br_w, br_h = map(int, preset["br_sr"].split("x"))
        dev_w, dev_h = map(int, preset["device_sr"].split("x"))
        dpr = preset["dpr"]
        ios_inner_height = preset.get("inner_height")
        ios_outer_height = preset.get("outer_height")
    else:
        br_w, br_h = 412, 915
        dev_w, dev_h = 415, 1100
        dpr = 2.625
        ios_inner_height = None
        ios_outer_height = None
    
    # 뷰포트 크기 계산 (iOS는 프리셋 값 사용)
    if is_ios and ios_inner_height:
        viewport_height = ios_inner_height
    else:
        viewport_height = br_h
    
    if is_ios and ios_outer_height:
        outer_height = ios_outer_height
    elif is_mobile:
        outer_height = dev_h - 145
    else:
        outer_height = dev_h
    
    if is_firefox and is_mobile:
        dpr = 3.0
    
    # Android 버전 추출 (UA에서)
    android_version = ""
    if is_mobile and not is_ios:
        m = re.search(r'Android\s+(\d+)', ua)
        if m:
            android_version = m.group(1)
    
    hints_json = json.dumps(hints) if hints else "null"
    
    js_code = f"""
(function() {{
    'use strict';
    
    const CONFIG = {{
        ua: {json.dumps(ua)},
        platform: {json.dumps(nav_platform)},
        isMobile: {str(is_mobile).lower()},
        isIOS: {str(is_ios).lower()},
        isIOSSafari: {str(is_ios_safari).lower()},
        isIOSChrome: {str(is_ios_chrome).lower()},
        isFirefox: {str(is_firefox).lower()},
        isSamsung: {str(is_samsung).lower()},
        isOpera: {str(is_opera).lower()},
        isEdge: {str(is_edge).lower()},
        model: {json.dumps(model)},
        platformVersion: {json.dumps(platform_version)},
        androidVersion: {json.dumps(android_version)},
        maxTouchPoints: {5 if is_mobile else 0},
        hardwareConcurrency: {hardware_concurrency},
        deviceMemory: {device_memory if device_memory else 'undefined'},
        vendor: {json.dumps(nav_vendor)},
        dpr: {dpr},
        screenWidth: {dev_w},
        screenHeight: {dev_h},
        outerWidth: {dev_w},
        outerHeight: {outer_height},
        viewportWidth: {br_w},
        viewportHeight: {viewport_height},
        hints: {hints_json},
        pluginsCount: {plugins_count},
        mimeTypesCount: {mime_types_count},
        languagesArray: {languages_array},
        languageSingle: {json.dumps(language_single)},
        hasConnection: {str(has_connection).lower()},
        hideWebrtcIP: {str(hide_webrtc_ip).lower()},
        blockWebrtc: {str(block_webrtc).lower()},
        randomMobileIP: {json.dumps(random_mobile_ip)},
        hasUserAgentData: {str(has_user_agent_data).lower()},
        hasRtt: {str(has_rtt).lower()},
        hoverNone: {hover_none},
        doNotTrack: {do_not_track},
        audioSampleRate: {audio_sample_rate},
        audioState: {json.dumps(audio_state)},
        audioBaseLatency: {audio_base_latency},
        pdfViewerEnabled: {pdf_viewer_enabled},
        webglRenderer: {json.dumps(webgl_renderer)},
        webglVendor: {json.dumps(webgl_vendor)},
        webglUnmaskedVendor: {json.dumps(webgl_unmasked_vendor)},
        webglUnmaskedRenderer: {json.dumps(webgl_unmasked_renderer)}
    }};
    
    const safe = (fn) => {{ try {{ fn(); }} catch(e) {{ console.error('[Spoof Error]', e); }} }};
    
    // ========== navigator 스푸핑 ==========
    const NavProto = Navigator.prototype;
    
    // 스푸핑된 getter들을 저장할 Map
    const spoofedGetters = new Map();
    
    // Function.prototype.toString 스푸핑
    const originalToString = Function.prototype.toString;
    Function.prototype.toString = function() {{
        if (spoofedGetters.has(this)) {{
            return spoofedGetters.get(this);
        }}
        return originalToString.call(this);
    }};
    
    // native code처럼 보이게 하는 헬퍼 함수
    const makeNativeGetter = (propName, value) => {{
        const getter = function() {{ return value; }};
        // toString을 직접 추가하지 않고 Map에 저장
        spoofedGetters.set(getter, 'function get ' + propName + '() {{ [native code] }}');
        Object.defineProperty(getter, 'name', {{ value: 'get ' + propName, configurable: true }});
        Object.defineProperty(getter, 'length', {{ value: 0, configurable: true }});
        return getter;
    }};
    
    const spoofProperty = (obj, propName, value) => {{
        const getter = makeNativeGetter(propName, value);
        Object.defineProperty(obj, propName, {{ 
            get: getter, 
            set: undefined,
            configurable: true, 
            enumerable: true 
        }});
    }};
    
    // platform (prototype만 설정)
    safe(() => {{
        spoofProperty(NavProto, 'platform', CONFIG.platform);
    }});
    
    // userAgent (prototype만 설정)
    safe(() => {{
        spoofProperty(NavProto, 'userAgent', CONFIG.ua);
    }});
    
    // webdriver (prototype만 설정)
    // 실제 브라우저는 webdriver가 prototype에만 있어서 _.has(navigator, 'webdriver')가 false
    safe(() => {{
        spoofProperty(NavProto, 'webdriver', false);
        // navigator 객체에서 own property 제거 (있다면)
        try {{ delete navigator.webdriver; }} catch(e) {{}}
    }});
    
    // maxTouchPoints (prototype만 설정)
    safe(() => {{
        spoofProperty(NavProto, 'maxTouchPoints', CONFIG.maxTouchPoints);
    }});
    
    // hardwareConcurrency (prototype만 설정)
    safe(() => {{
        spoofProperty(NavProto, 'hardwareConcurrency', CONFIG.hardwareConcurrency);
    }});
    
    // deviceMemory (Firefox는 없음)
    if (CONFIG.deviceMemory !== undefined) {{
        safe(() => {{
            spoofProperty(NavProto, 'deviceMemory', CONFIG.deviceMemory);
        }});
    }} else {{
        // Firefox: deviceMemory 삭제
        safe(() => {{
            delete navigator.deviceMemory;
            delete Navigator.prototype.deviceMemory;
        }});
    }}
    
    // Firefox/iOS: window.chrome 삭제 (실제 Firefox/Safari에는 없음)
    if (CONFIG.isFirefox || CONFIG.isIOS) {{
        safe(() => {{
            // configurable: false라서 delete나 defineProperty 안 됨
            // 하지만 writable: true니까 직접 할당으로 덮어쓰기
            window.chrome = undefined;
        }});
    }}
    
    // vendor (prototype만 설정)
    safe(() => {{
        spoofProperty(NavProto, 'vendor', CONFIG.vendor);
    }});
    
    // ========== plugins 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            if (CONFIG.pluginsCount === 0) {{
                // Chromium 계열: plugins 0
                const emptyPlugins = {{
                    length: 0,
                    item: () => null,
                    namedItem: () => null,
                    refresh: () => {{}},
                    [Symbol.iterator]: function* () {{}},
                }};
                // PluginArray prototype 연결 (instanceof 체크 통과)
                try {{ Object.setPrototypeOf(emptyPlugins, PluginArray.prototype); }} catch(e) {{}}
                spoofProperty(NavProto, 'plugins', emptyPlugins);
            }} else if (CONFIG.pluginsCount === 5) {{
                // Firefox/iOS: plugins 5 (실폰 Firefox 기반)
                const firefoxPluginData = [
                    {{ name: 'PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer', version: '' }},
                    {{ name: 'Chrome PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer', version: '' }},
                    {{ name: 'Chromium PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer', version: '' }},
                    {{ name: 'Microsoft Edge PDF Viewer', description: 'Portable Document Format', filename: 'internal-pdf-viewer', version: '' }},
                    {{ name: 'WebKit built-in PDF', description: 'Portable Document Format', filename: 'internal-pdf-viewer', version: '' }}
                ];
                const firefoxPlugins = {{
                    length: 5,
                    item: (i) => i >= 0 && i < 5 ? firefoxPluginData[i] : null,
                    namedItem: (name) => firefoxPluginData.find(p => p.name === name) || null,
                    refresh: () => {{}},
                    [Symbol.iterator]: function* () {{ for(let i=0; i<5; i++) yield firefoxPluginData[i]; }},
                    0: firefoxPluginData[0],
                    1: firefoxPluginData[1],
                    2: firefoxPluginData[2],
                    3: firefoxPluginData[3],
                    4: firefoxPluginData[4]
                }};
                // PluginArray prototype 연결 (instanceof 체크 통과)
                try {{ Object.setPrototypeOf(firefoxPlugins, PluginArray.prototype); }} catch(e) {{}}
                spoofProperty(NavProto, 'plugins', firefoxPlugins);
            }}
        }});
        
        // mimeTypes 스푸핑
        safe(() => {{
            const mimeTypeData = [
                {{ type: 'application/pdf', description: 'Portable Document Format', suffixes: 'pdf' }},
                {{ type: 'text/pdf', description: 'Portable Document Format', suffixes: 'pdf' }}
            ];
            const mimeTypesObj = {{
                length: CONFIG.mimeTypesCount,
                item: (i) => i >= 0 && i < CONFIG.mimeTypesCount ? mimeTypeData[i] : null,
                namedItem: (name) => mimeTypeData.find(m => m.type === name) || null,
                [Symbol.iterator]: function* () {{ for(let i=0; i<CONFIG.mimeTypesCount; i++) yield mimeTypeData[i]; }},
                0: CONFIG.mimeTypesCount > 0 ? mimeTypeData[0] : undefined,
                1: CONFIG.mimeTypesCount > 1 ? mimeTypeData[1] : undefined
            }};
            // MimeTypeArray prototype 연결 (instanceof 체크 통과)
            try {{ Object.setPrototypeOf(mimeTypesObj, MimeTypeArray.prototype); }} catch(e) {{}}
            spoofProperty(NavProto, 'mimeTypes', mimeTypesObj);
        }});
    }}
    
    // ========== languages 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            // languages 배열은 frozen이어야 함
            // prototype에만 설정 (navigator 객체에 직접 설정하면 안 됨!)
            const frozenLanguages = Object.freeze([...CONFIG.languagesArray]);
            spoofProperty(NavProto, 'languages', frozenLanguages);
        }});
        
        safe(() => {{
            // prototype에만 설정
            spoofProperty(NavProto, 'language', CONFIG.languageSingle);
        }});
    }}
    
    // ========== connection 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            if (CONFIG.hasConnection) {{
                // 랜덤 값 생성
                const downlinkValue = (1 + Math.random() * 9).toFixed(2);  // 1~10 소수점
                const rttValue = Math.floor(Math.random() * 16) * 10;  // 0~150 (10단위)
                
                const mobileConnection = {{
                    type: 'cellular',
                    effectiveType: '4g',
                    downlink: parseFloat(downlinkValue),
                    rtt: rttValue,
                    saveData: false,
                    onchange: null,
                    addEventListener: function() {{}},
                    removeEventListener: function() {{}},
                    dispatchEvent: function() {{ return true; }},
                }};
                spoofProperty(NavProto, 'connection', mobileConnection);
            }} else {{
                spoofProperty(NavProto, 'connection', undefined);
            }}
        }});
    }}
    
    // ========== Canvas Font 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            // 실폰에서 감지되는 폰트 목록 (Chrome 모바일 기준 - 8개만!)
            const detectedFonts = new Set([
                'arial', 'verdana', 'times new roman', 'georgia', 
                'courier new', 'palatino', 'tahoma', 'helvetica'
            ]);
            
            // 기본 폰트 (항상 통과)
            const baseFonts = new Set([
                'sans-serif', 'serif', 'monospace', 'cursive', 'fantasy', 'system-ui'
            ]);
            
            // iOS용 폰트 (실폰 Safari 데이터 - 10개)
            const iosFonts = new Set([
                'arial', 'verdana', 'times new roman', 'georgia',
                'apple sd gothic neo', 'impact', 'trebuchet ms', 'palatino', 'helvetica', 'helvetica neue'
            ]);
            
            // Firefox용 폰트 (더 제한적)
            const firefoxFonts = new Set([
                'roboto'  // 실폰 Firefox: Roboto 1개만
            ]);
            
            // 현재 환경에 맞는 폰트 목록 선택
            let allowedFonts;
            if (CONFIG.isFirefox) {{
                allowedFonts = firefoxFonts;
            }} else if (CONFIG.isIOS) {{
                allowedFonts = iosFonts;
            }} else {{
                allowedFonts = detectedFonts;
            }}
            
            const extractFirstFont = (fontStr) => {{
                const match = fontStr.match(/(?:\\d+(?:px|pt|em|rem|%)\\s+)?([^,]+)/i);
                if (match) {{
                    return match[1].trim().toLowerCase().replace(/['"]/g, '');
                }}
                return '';
            }};
            
            const extractFallbackFont = (fontStr) => {{
                const parts = fontStr.split(',');
                if (parts.length > 1) {{
                    return parts[parts.length - 1].trim().toLowerCase();
                }}
                return 'sans-serif';
            }};
            
            // 폰트별 고유 width offset (폰트가 "있는 것처럼" 보이게)
            const fontOffsets = {{
                'arial': 0.1,
                'verdana': 0.15,
                'times new roman': 0.08,
                'georgia': 0.12,
                'courier new': 0.05,
                'palatino': 0.11,
                'tahoma': 0.09,
                'helvetica': 0.13,
                'roboto': 0.07,
                'noto sans': 0.06,
                'droid sans': 0.04
            }};
            
            const originalMeasureText = CanvasRenderingContext2D.prototype.measureText;
            CanvasRenderingContext2D.prototype.measureText = function(text) {{
                const result = originalMeasureText.call(this, text);
                const fontName = extractFirstFont(this.font);
                
                // 기본 폰트는 그대로 반환
                if (baseFonts.has(fontName)) {{
                    return result;
                }}
                
                // 허용된 폰트면 고유한 width 반환 (감지되게)
                if (allowedFonts.has(fontName)) {{
                    const offset = fontOffsets[fontName] || 0.001;
                    return {{
                        width: result.width + offset,
                        actualBoundingBoxLeft: result.actualBoundingBoxLeft,
                        actualBoundingBoxRight: result.actualBoundingBoxRight,
                        actualBoundingBoxAscent: result.actualBoundingBoxAscent,
                        actualBoundingBoxDescent: result.actualBoundingBoxDescent,
                        fontBoundingBoxAscent: result.fontBoundingBoxAscent,
                        fontBoundingBoxDescent: result.fontBoundingBoxDescent
                    }};
                }}
                
                // 허용되지 않은 폰트는 fallback과 같은 width 반환 (감지 안 되게)
                const originalFont = this.font;
                const fontSize = this.font.match(/(\\d+(?:px|pt|em|rem|%))/)?.[1] || '72px';
                const fallbackFont = extractFallbackFont(this.font);
                
                this.font = fontSize + ' ' + fallbackFont;
                const fallbackResult = originalMeasureText.call(this, text);
                this.font = originalFont;
                
                return {{
                    width: fallbackResult.width,
                    actualBoundingBoxLeft: fallbackResult.actualBoundingBoxLeft,
                    actualBoundingBoxRight: fallbackResult.actualBoundingBoxRight,
                    actualBoundingBoxAscent: fallbackResult.actualBoundingBoxAscent,
                    actualBoundingBoxDescent: fallbackResult.actualBoundingBoxDescent,
                    fontBoundingBoxAscent: fallbackResult.fontBoundingBoxAscent,
                    fontBoundingBoxDescent: fallbackResult.fontBoundingBoxDescent
                }};
            }};
        }});
    }}
    
    // ========== WebGL 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            // iOS vs Android WebGL 파라미터 분리
            const mobileWebGLParams = CONFIG.isIOS ? {{
                // iOS Safari 실폰 데이터
                3379: 16384,     // MAX_TEXTURE_SIZE
                34076: 16384,    // MAX_CUBE_MAP_TEXTURE_SIZE
                34024: 16384,    // MAX_RENDERBUFFER_SIZE
                3386: new Int32Array([16384, 16384]),  // MAX_VIEWPORT_DIMS
                34921: 16,       // MAX_VERTEX_ATTRIBS (iOS: 16)
                36347: 1024,     // MAX_VERTEX_UNIFORM_VECTORS (iOS: 1024)
                36349: 1024,     // MAX_FRAGMENT_UNIFORM_VECTORS (iOS: 1024)
                36348: 31,       // MAX_VARYING_VECTORS
                33901: new Float32Array([1, 511]),   // ALIASED_POINT_SIZE_RANGE (iOS: [1, 511])
                33902: new Float32Array([1, 1]),     // ALIASED_LINE_WIDTH_RANGE (iOS: [1, 1])
            }} : CONFIG.isSamsung ? {{
                // Samsung 브라우저 실폰 데이터
                3379: 4096,      // MAX_TEXTURE_SIZE
                34076: 4096,     // MAX_CUBE_MAP_TEXTURE_SIZE
                34024: 16384,    // MAX_RENDERBUFFER_SIZE
                3386: new Int32Array([16384, 16384]),  // MAX_VIEWPORT_DIMS
                34921: 32,       // MAX_VERTEX_ATTRIBS
                36347: 256,      // MAX_VERTEX_UNIFORM_VECTORS
                36349: 256,      // MAX_FRAGMENT_UNIFORM_VECTORS
                36348: 31,       // MAX_VARYING_VECTORS
                33901: new Float32Array([1, 1023]),  // ALIASED_POINT_SIZE_RANGE
                33902: new Float32Array([1, 8]),     // ALIASED_LINE_WIDTH_RANGE
            }} : CONFIG.isOpera ? {{
                // Opera 브라우저 실폰 데이터
                3379: 8192,      // MAX_TEXTURE_SIZE (실제: 8192)
                34076: 8192,     // MAX_CUBE_MAP_TEXTURE_SIZE (실제: 8192)
                34024: 16384,    // MAX_RENDERBUFFER_SIZE
                3386: new Int32Array([16384, 16384]),  // MAX_VIEWPORT_DIMS
                34921: 32,       // MAX_VERTEX_ATTRIBS
                36347: 256,      // MAX_VERTEX_UNIFORM_VECTORS
                36349: 256,      // MAX_FRAGMENT_UNIFORM_VECTORS
                36348: 31,       // MAX_VARYING_VECTORS
                33901: new Float32Array([1, 1023]),  // ALIASED_POINT_SIZE_RANGE
                33902: new Float32Array([1, 8]),     // ALIASED_LINE_WIDTH_RANGE
            }} : CONFIG.isFirefox ? {{
                // Android Firefox 실폰 데이터
                3379: 16384,     // MAX_TEXTURE_SIZE
                34076: 16384,    // MAX_CUBE_MAP_TEXTURE_SIZE
                34024: 16384,    // MAX_RENDERBUFFER_SIZE
                3386: new Int32Array([16384, 16384]),  // MAX_VIEWPORT_DIMS
                34921: 32,       // MAX_VERTEX_ATTRIBS
                36347: 256,      // MAX_VERTEX_UNIFORM_VECTORS
                36349: 256,      // MAX_FRAGMENT_UNIFORM_VECTORS
                36348: 32,       // MAX_VARYING_VECTORS (Firefox: 32)
                33901: new Float32Array([1, 1023]),  // ALIASED_POINT_SIZE_RANGE
                33902: new Float32Array([1, 8]),     // ALIASED_LINE_WIDTH_RANGE
            }} : {{
                // Android Chrome 실폰 데이터
                3379: 8192,      // MAX_TEXTURE_SIZE
                34076: 8192,     // MAX_CUBE_MAP_TEXTURE_SIZE
                34024: 16384,    // MAX_RENDERBUFFER_SIZE
                3386: new Int32Array([16384, 16384]),  // MAX_VIEWPORT_DIMS
                34921: 32,       // MAX_VERTEX_ATTRIBS (Android: 32)
                36347: 256,      // MAX_VERTEX_UNIFORM_VECTORS (Android: 256)
                36349: 256,      // MAX_FRAGMENT_UNIFORM_VECTORS (Android: 256)
                36348: 31,       // MAX_VARYING_VECTORS
                33901: new Float32Array([1, 1023]),  // ALIASED_POINT_SIZE_RANGE (Android: [1, 1023])
                33902: new Float32Array([1, 8]),     // ALIASED_LINE_WIDTH_RANGE (Android: [1, 8])
            }};
            
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {{
                // 7936 = VENDOR, 7937 = RENDERER, 7938 = VERSION, 35724 = SHADING_LANGUAGE_VERSION
                if (param === 7937) {{
                    return CONFIG.webglRenderer;
                }}
                if (param === 7936) {{
                    return CONFIG.webglVendor;
                }}
                // Firefox, iOS는 짧은 버전 문자열
                if (param === 7938 && (CONFIG.isFirefox || CONFIG.isIOS)) {{
                    return 'WebGL 1.0';
                }}
                if (param === 35724 && CONFIG.isFirefox) {{
                    return 'WebGL GLSL ES 1.0';
                }}
                if (param === 35724 && CONFIG.isIOS) {{
                    return 'WebGL GLSL ES 1.0 (1.0)';
                }}
                // 37445 = UNMASKED_VENDOR_WEBGL, 37446 = UNMASKED_RENDERER_WEBGL
                if (param === 37445) {{
                    return CONFIG.webglUnmaskedVendor;
                }}
                if (param === 37446) {{
                    return CONFIG.webglUnmaskedRenderer;
                }}
                // 모바일 파라미터 스푸핑
                if (param in mobileWebGLParams) {{
                    return mobileWebGLParams[param];
                }}
                return originalGetParameter.call(this, param);
            }};
            
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                // WebGL2 추가 파라미터
                const mobileWebGL2Params = {{
                    ...mobileWebGLParams,
                    36183: 4,  // MAX_SAMPLES
                }};
                
                const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(param) {{
                    if (param === 7937) {{
                        return CONFIG.webglRenderer;
                    }}
                    if (param === 7936) {{
                        return CONFIG.webglVendor;
                    }}
                    // Firefox, iOS는 짧은 버전 문자열
                    if (param === 7938 && (CONFIG.isFirefox || CONFIG.isIOS)) {{
                        return 'WebGL 2.0';
                    }}
                    if (param === 35724 && CONFIG.isFirefox) {{
                        return 'WebGL GLSL ES 3.00';
                    }}
                    if (param === 35724 && CONFIG.isIOS) {{
                        return 'WebGL GLSL ES 3.00 (3.0)';
                    }}
                    if (param === 37445) {{
                        return CONFIG.webglUnmaskedVendor;
                    }}
                    if (param === 37446) {{
                        return CONFIG.webglUnmaskedRenderer;
                    }}
                    if (param in mobileWebGL2Params) {{
                        return mobileWebGL2Params[param];
                    }}
                    return originalGetParameter2.call(this, param);
                }};
            }}
            
            // WebGL 확장 개수 스푸핑 (iOS: 33, Firefox: 28, 나머지: 27)
            // WEBGL_debug_renderer_info는 반드시 포함되어야 함
            const webglExtCount = CONFIG.isIOS ? 33 : (CONFIG.isFirefox ? 28 : 27);
            const originalGetSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
            WebGLRenderingContext.prototype.getSupportedExtensions = function() {{
                const extensions = originalGetSupportedExtensions.call(this);
                if (extensions) {{
                    // WEBGL_debug_renderer_info가 없으면 추가
                    if (extensions.indexOf('WEBGL_debug_renderer_info') === -1) {{
                        extensions.push('WEBGL_debug_renderer_info');
                    }}
                    // 확장 개수 조정 (WEBGL_debug_renderer_info 포함)
                    if (extensions.length > webglExtCount) {{
                        // WEBGL_debug_renderer_info는 유지하면서 자르기
                        const hasDebugInfo = extensions.indexOf('WEBGL_debug_renderer_info');
                        const sliced = extensions.slice(0, webglExtCount);
                        if (sliced.indexOf('WEBGL_debug_renderer_info') === -1) {{
                            sliced.push('WEBGL_debug_renderer_info');
                        }}
                        return sliced;
                    }}
                }}
                return extensions;
            }};
        }});
    }}
    
    // ========== Canvas 스푸핑 (노이즈 추가로 매번 다른 hash) ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            // toDataURL 오버라이드 - 결과에 직접 노이즈 주입
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
                // 원본 캔버스 복사
                const width = this.width;
                const height = this.height;
                
                if (width > 0 && height > 0) {{
                    try {{
                        const ctx = this.getContext('2d');
                        if (ctx) {{
                            // 현재 이미지 데이터 가져오기
                            const imageData = ctx.getImageData(0, 0, width, height);
                            const data = imageData.data;
                            
                            // 랜덤 위치 몇 개의 픽셀에 미세한 노이즈 추가
                            const numNoise = Math.min(10, Math.floor(data.length / 4));
                            for (let i = 0; i < numNoise; i++) {{
                                const idx = Math.floor(Math.random() * (data.length / 4)) * 4;
                                // RGB 값에 ±1~2 노이즈 (눈에 안 보임)
                                const noise = Math.random() > 0.5 ? 1 : -1;
                                data[idx] = Math.max(0, Math.min(255, data[idx] + noise));
                            }}
                            
                            ctx.putImageData(imageData, 0, 0);
                        }}
                    }} catch(e) {{
                        // getImageData 실패 시 무시
                    }}
                }}
                
                return originalToDataURL.call(this, type, quality);
            }};
            
            // toBlob도 오버라이드
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;
            if (originalToBlob) {{
                HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
                    const width = this.width;
                    const height = this.height;
                    
                    if (width > 0 && height > 0) {{
                        try {{
                            const ctx = this.getContext('2d');
                            if (ctx) {{
                                const imageData = ctx.getImageData(0, 0, width, height);
                                const data = imageData.data;
                                
                                const numNoise = Math.min(10, Math.floor(data.length / 4));
                                for (let i = 0; i < numNoise; i++) {{
                                    const idx = Math.floor(Math.random() * (data.length / 4)) * 4;
                                    const noise = Math.random() > 0.5 ? 1 : -1;
                                    data[idx] = Math.max(0, Math.min(255, data[idx] + noise));
                                }}
                                
                                ctx.putImageData(imageData, 0, 0);
                            }}
                        }} catch(e) {{}}
                    }}
                    
                    return originalToBlob.call(this, callback, type, quality);
                }};
            }}
        }});
    }}
    
    // ========== Audio 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            const OriginalAudioContext = window.AudioContext || window.webkitAudioContext;
            if (OriginalAudioContext) {{
                const originalCreateAnalyser = OriginalAudioContext.prototype.createAnalyser;
                // baseLatency 스푸핑은 생성자에서 처리
            }}
        }});
    }}
    
    // ========== API 존재 여부 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            // api_hid: 모바일은 false (속성 자체를 삭제)
            try {{
                delete navigator.hid;
            }} catch(e) {{}}
            // Navigator.prototype에서도 삭제
            try {{
                delete Navigator.prototype.hid;
            }} catch(e) {{}}
            
            // api_serial: Samsung/Firefox 모바일은 false, Opera는 true!
            if (CONFIG.isSamsung || CONFIG.isFirefox) {{
                try {{
                    delete navigator.serial;
                }} catch(e) {{}}
                try {{
                    delete Navigator.prototype.serial;
                }} catch(e) {{}}
            }}
            
            // Firefox 전용: 여러 API가 없음
            if (CONFIG.isFirefox) {{
                // appVersion: Firefox는 "5.0 (Android 버전)" 형식
                const appVersionValue = CONFIG.androidVersion ? `5.0 (Android ${{CONFIG.androidVersion}})` : '5.0 (Android)';
                try {{
                    spoofProperty(NavProto, 'appVersion', appVersionValue);
                }} catch(e) {{}}
                
                // productSub: Firefox는 "20100101"
                try {{
                    spoofProperty(NavProto, 'productSub', '20100101');
                }} catch(e) {{}}
                
                // performance.memory: Firefox는 없음 (undefined)
                try {{
                    Object.defineProperty(performance, 'memory', {{
                        get: () => undefined,
                        configurable: true
                    }});
                }} catch(e) {{}}
                
                // bluetooth: false
                try {{
                    delete navigator.bluetooth;
                    delete Navigator.prototype.bluetooth;
                }} catch(e) {{}}
                // usb: false
                try {{
                    delete navigator.usb;
                    delete Navigator.prototype.usb;
                }} catch(e) {{}}
                // vibrate: Firefox는 없음
                try {{
                    delete navigator.vibrate;
                    delete Navigator.prototype.vibrate;
                }} catch(e) {{}}
                // presentation: false
                try {{
                    delete navigator.presentation;
                    delete Navigator.prototype.presentation;
                }} catch(e) {{}}
                // getBattery: false
                try {{
                    delete navigator.getBattery;
                    delete Navigator.prototype.getBattery;
                }} catch(e) {{}}
            }}
            
            // iOS Safari 전용: 여러 API가 없음
            if (CONFIG.isIOS) {{
                // bluetooth: false
                try {{
                    delete navigator.bluetooth;
                    delete Navigator.prototype.bluetooth;
                }} catch(e) {{}}
                // usb: false
                try {{
                    delete navigator.usb;
                    delete Navigator.prototype.usb;
                }} catch(e) {{}}
                // serial: false
                try {{
                    delete navigator.serial;
                    delete Navigator.prototype.serial;
                }} catch(e) {{}}
                // vibrate: false
                try {{
                    delete navigator.vibrate;
                    delete Navigator.prototype.vibrate;
                }} catch(e) {{}}
                // presentation: false
                try {{
                    delete navigator.presentation;
                    delete Navigator.prototype.presentation;
                }} catch(e) {{}}
                // getBattery: false
                try {{
                    delete navigator.getBattery;
                    delete Navigator.prototype.getBattery;
                }} catch(e) {{}}
                
                // performance.memory: iOS는 없음 (undefined 반환)
                try {{
                    Object.defineProperty(performance, 'memory', {{
                        get: () => undefined,
                        configurable: true
                    }});
                }} catch(e) {{}}
            }}
        }});
    }}
    
    // ========== Battery 스푸핑 (Android Chrome) ==========
    if (CONFIG.isMobile && !CONFIG.isIOS && !CONFIG.isFirefox) {{
        safe(() => {{
            // 랜덤 배터리 레벨 (50~95%)
            const batteryLevel = 0.5 + Math.random() * 0.45;
            // 방전 시간 (3~8시간)
            const dischargingTime = Math.floor(10800 + Math.random() * 18000);
            
            const mockBattery = {{
                charging: false,
                chargingTime: Infinity,
                dischargingTime: dischargingTime,
                level: Math.round(batteryLevel * 100) / 100,
                addEventListener: function() {{}},
                removeEventListener: function() {{}},
                dispatchEvent: function() {{ return true; }}
            }};
            
            // oncharging... 속성들 추가
            ['onchargingchange', 'onchargingtimechange', 'ondischargingtimechange', 'onlevelchange'].forEach(prop => {{
                mockBattery[prop] = null;
            }});
            
            // getBattery 함수를 native처럼 보이게 설정
            const getBatteryFunc = function getBattery() {{
                return Promise.resolve(mockBattery);
            }};
            // toString을 spoofedGetters Map에 등록
            spoofedGetters.set(getBatteryFunc, 'function getBattery() {{ [native code] }}');
            Object.defineProperty(getBatteryFunc, 'name', {{ value: 'getBattery', configurable: true }});
            Object.defineProperty(getBatteryFunc, 'length', {{ value: 0, configurable: true }});
            
            Navigator.prototype.getBattery = getBatteryFunc;
        }});
    }}
    
    // ========== Media Query 스푸핑 ==========
    safe(() => {{
        const originalMatchMedia = window.matchMedia;
        // 세션 동안 일관된 값 유지 - 기본 light (실폰 기본값)
        // dark 모드는 약 20% 확률
        const isDarkMode = Math.random() > 0.8;
        
        window.matchMedia = function(query) {{
            const result = originalMatchMedia.call(window, query);
            
            // prefers-color-scheme: 기본 light (dark는 20% 확률)
            if (query.includes('prefers-color-scheme')) {{
                const wantsDark = query.includes('dark');
                const wantsLight = query.includes('light');
                return {{
                    matches: wantsDark ? isDarkMode : (wantsLight ? !isDarkMode : result.matches),
                    media: query,
                    onchange: null,
                    addListener: function() {{}},
                    removeListener: function() {{}},
                    addEventListener: function() {{}},
                    removeEventListener: function() {{}},
                    dispatchEvent: function() {{ return true; }}
                }};
            }}
            
            // prefers-reduced-motion: iOS는 true, 나머지는 false
            if (query.includes('prefers-reduced-motion')) {{
                const reducedMotion = CONFIG.isIOS ? true : false;
                const wantsReduced = query.includes('reduce');
                return {{
                    matches: wantsReduced ? reducedMotion : !reducedMotion,
                    media: query,
                    onchange: null,
                    addListener: function() {{}},
                    removeListener: function() {{}},
                    addEventListener: function() {{}},
                    removeEventListener: function() {{}},
                    dispatchEvent: function() {{ return true; }}
                }};
            }}
            
            return result;
        }};
    }});
    
    // ========== WebRTC IP 스푸핑 ==========
    safe(() => {{
        const OriginalRTCPeerConnection = window.RTCPeerConnection || window.webkitRTCPeerConnection;
        
        // iOS용 UUID.local 생성
        const generateUUIDLocal = () => {{
            const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {{
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            }});
            return uuid + '.local';
        }};
        const iosLocalIP = generateUUIDLocal();
        
        if (OriginalRTCPeerConnection) {{
            const wrappedRTCPeerConnection = function(config, constraints) {{
                const pc = new OriginalRTCPeerConnection(config, constraints);
                
                if (CONFIG.blockWebrtc) {{
                    let _onicecandidate = null;
                    Object.defineProperty(pc, 'onicecandidate', {{
                        get: () => _onicecandidate,
                        set: (handler) => {{
                            _onicecandidate = handler;
                        }},
                        configurable: true
                    }});
                    
                    const originalAddEventListener = pc.addEventListener.bind(pc);
                    pc.addEventListener = function(type, listener, options) {{
                        if (type === 'icecandidate') {{
                            return;
                        }}
                        return originalAddEventListener(type, listener, options);
                    }};
                    
                    return pc;
                }}
                
                const modifyCandidate = (candidateStr) => {{
                    if (!candidateStr) return candidateStr;
                    
                    if (CONFIG.hideWebrtcIP) {{
                        if (CONFIG.isIOS) {{
                            // iOS: UUID.local 형식으로 변환
                            let newCandidate = candidateStr;
                            newCandidate = newCandidate.replace(/([0-9]{{1,3}}\\.[0-9]{{1,3}}\\.[0-9]{{1,3}}\\.[0-9]{{1,3}})/g, iosLocalIP);
                            newCandidate = newCandidate.replace(/[a-f0-9-]+\\.local/g, iosLocalIP);
                            return newCandidate;
                        }} else {{
                            // Opera 등: IP 숨김
                            return candidateStr.replace(/([0-9]{{1,3}}\\.[0-9]{{1,3}}\\.[0-9]{{1,3}}\\.[0-9]{{1,3}})/g, '0.0.0.0');
                        }}
                    }} else {{
                        let newCandidate = candidateStr;
                        newCandidate = newCandidate.replace(/[a-f0-9-]+\\.local/g, CONFIG.randomMobileIP);
                        return newCandidate;
                    }}
                }};
                
                let _onicecandidate = null;
                Object.defineProperty(pc, 'onicecandidate', {{
                    get: () => _onicecandidate,
                    set: (handler) => {{
                        _onicecandidate = handler;
                        pc.addEventListener('icecandidate', (event) => {{
                            if (handler && event.candidate) {{
                                const modifiedEvent = {{
                                    ...event,
                                    candidate: {{
                                        ...event.candidate,
                                        candidate: modifyCandidate(event.candidate.candidate)
                                    }}
                                }};
                                handler(modifiedEvent);
                            }} else if (handler) {{
                                handler(event);
                            }}
                        }});
                    }},
                    configurable: true
                }});
                
                const originalAddEventListener = pc.addEventListener.bind(pc);
                pc.addEventListener = function(type, listener, options) {{
                    if (type === 'icecandidate') {{
                        return originalAddEventListener(type, function(event) {{
                            if (event.candidate) {{
                                const modifiedEvent = {{
                                    ...event,
                                    candidate: {{
                                        ...event.candidate,
                                        candidate: modifyCandidate(event.candidate.candidate)
                                    }}
                                }};
                                listener(modifiedEvent);
                            }} else {{
                                listener(event);
                            }}
                        }}, options);
                    }}
                    return originalAddEventListener(type, listener, options);
                }};
                
                return pc;
            }};
            
            wrappedRTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;
            window.RTCPeerConnection = wrappedRTCPeerConnection;
            if (window.webkitRTCPeerConnection) {{
                window.webkitRTCPeerConnection = wrappedRTCPeerConnection;
            }}
        }}
    }});
    
    // ========== 화면 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            Object.defineProperty(window, 'devicePixelRatio', {{
                get: () => CONFIG.dpr,
                configurable: true
            }});
        }});
        
        safe(() => {{
            Object.defineProperty(screen, 'width', {{ get: () => CONFIG.screenWidth, configurable: true }});
            Object.defineProperty(screen, 'height', {{ get: () => CONFIG.screenHeight, configurable: true }});
            Object.defineProperty(screen, 'availWidth', {{ get: () => CONFIG.screenWidth, configurable: true }});
            Object.defineProperty(screen, 'availHeight', {{ get: () => CONFIG.screenHeight, configurable: true }});
        }});
        
        safe(() => {{
            Object.defineProperty(window, 'innerWidth', {{ get: () => CONFIG.viewportWidth, configurable: true }});
            Object.defineProperty(window, 'innerHeight', {{ get: () => CONFIG.viewportHeight, configurable: true }});
            Object.defineProperty(window, 'outerWidth', {{ get: () => CONFIG.outerWidth, configurable: true }});
            Object.defineProperty(window, 'outerHeight', {{ get: () => CONFIG.outerHeight, configurable: true }});
        }});
        
        // Intl locale 스푸핑 (Firefox, iOS, Opera: ko-KR, 나머지: ko)
        safe(() => {{
            const targetLocale = (CONFIG.isFirefox || CONFIG.isIOS || CONFIG.isOpera) ? 'ko-KR' : 'ko';
            const OriginalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(locales, options) {{
                const instance = new OriginalDateTimeFormat(locales, options);
                const originalResolvedOptions = instance.resolvedOptions.bind(instance);
                instance.resolvedOptions = function() {{
                    const result = originalResolvedOptions();
                    result.locale = targetLocale;
                    return result;
                }};
                return instance;
            }};
            Intl.DateTimeFormat.prototype = OriginalDateTimeFormat.prototype;
            Intl.DateTimeFormat.supportedLocalesOf = OriginalDateTimeFormat.supportedLocalesOf;
        }});
    }}
    
    // ========== 터치 이벤트 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            window.ontouchstart = null;
            Object.defineProperty(window, 'ontouchstart', {{
                get: () => null,
                set: () => {{}},
                configurable: true,
                enumerable: true
            }});
        }});
        
        safe(() => {{
            if (typeof TouchEvent === 'undefined') {{
                window.TouchEvent = function TouchEvent() {{}};
            }}
        }});
        
        safe(() => {{
            const originalMatchMedia = window.matchMedia;
            window.matchMedia = function(query) {{
                const result = originalMatchMedia.call(window, query);
                
                // any-pointer 먼저 체크 (pointer보다 앞에!)
                // any-pointer: fine - iOS는 false, Android는 true (S펜 등)
                if (query.includes('any-pointer: fine') || query.includes('any-pointer:fine')) {{
                    return {{ ...result, matches: CONFIG.isIOS ? false : true }};
                }}
                // any-pointer: coarse (터치 가능) - 모바일은 true
                if (query.includes('any-pointer: coarse') || query.includes('any-pointer:coarse')) {{
                    return {{ ...result, matches: true }};
                }}
                
                // pointer: coarse (터치)
                if (query.includes('pointer: coarse') || query.includes('pointer:coarse')) {{
                    return {{ ...result, matches: true }};
                }}
                // pointer: fine (마우스) - 모바일은 false
                if (query.includes('pointer: fine') || query.includes('pointer:fine')) {{
                    return {{ ...result, matches: false }};
                }}
                
                // any-hover: hover - iOS는 false, Android는 true
                if (query.includes('any-hover: hover') || query.includes('any-hover:hover')) {{
                    return {{ ...result, matches: CONFIG.isIOS ? false : true }};
                }}
                // any-hover: none - iOS는 true, Android는 false
                if (query.includes('any-hover: none') || query.includes('any-hover:none')) {{
                    return {{ ...result, matches: CONFIG.isIOS ? true : false }};
                }}
                
                // hover: none
                if (query.includes('hover: none') || query.includes('hover:none')) {{
                    return {{ ...result, matches: CONFIG.hoverNone }};
                }}
                // hover: hover
                if (query.includes('hover: hover') || query.includes('hover:hover')) {{
                    return {{ ...result, matches: !CONFIG.hoverNone }};
                }}
                
                return result;
            }};
        }});
    }}
    
    // ========== orientation 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            const mobileOrientation = {{
                type: 'portrait-primary',
                angle: 0,
                onchange: null,
                addEventListener: function() {{}},
                removeEventListener: function() {{}},
                dispatchEvent: function() {{ return true; }},
            }};
            Object.defineProperty(screen, 'orientation', {{
                get: () => mobileOrientation,
                configurable: true,
                enumerable: true
            }});
        }});
    }}
    
    // ========== AudioContext 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            const OriginalAudioContext = window.AudioContext || window.webkitAudioContext;
            if (OriginalAudioContext) {{
                const WrappedAudioContext = function(options) {{
                    const ctx = new OriginalAudioContext(options);
                    Object.defineProperty(ctx, 'sampleRate', {{
                        get: () => CONFIG.audioSampleRate,
                        configurable: true
                    }});
                    // baseLatency 스푸핑 (Firefox: 0, iOS: 0.00267, 나머지: 0.003)
                    Object.defineProperty(ctx, 'baseLatency', {{
                        get: () => CONFIG.audioBaseLatency,
                        configurable: true
                    }});
                    // state 스푸핑 (Firefox, iOS: "suspended", 나머지: "running")
                    if (CONFIG.isFirefox || CONFIG.isIOS) {{
                        Object.defineProperty(ctx, 'state', {{
                            get: () => CONFIG.audioState,
                            configurable: true
                        }});
                    }}
                    return ctx;
                }};
                WrappedAudioContext.prototype = OriginalAudioContext.prototype;
                window.AudioContext = WrappedAudioContext;
                if (window.webkitAudioContext) {{
                    window.webkitAudioContext = WrappedAudioContext;
                }}
            }}
        }});
    }}
    
    // ========== userAgentData 스푸핑 ==========
    if (CONFIG.isMobile) {{
        safe(() => {{
            if (CONFIG.hasUserAgentData && CONFIG.hints) {{
                const mockUserAgentData = {{
                    brands: CONFIG.hints.brands,
                    mobile: CONFIG.hints.mobile,
                    platform: CONFIG.hints.platform,
                    getHighEntropyValues: async function(hints) {{
                        return {{
                            brands: CONFIG.hints.brands,
                            mobile: CONFIG.hints.mobile,
                            platform: CONFIG.hints.platform,
                            platformVersion: CONFIG.hints.platformVersion,
                            architecture: CONFIG.hints.architecture,
                            bitness: CONFIG.hints.bitness,
                            model: CONFIG.hints.model,
                            fullVersionList: CONFIG.hints.fullVersionList,
                            wow64: CONFIG.hints.wow64,
                            formFactors: CONFIG.hints.formFactors,
                        }};
                    }},
                    toJSON: function() {{
                        return {{
                            brands: CONFIG.hints.brands,
                            mobile: CONFIG.hints.mobile,
                            platform: CONFIG.hints.platform,
                        }};
                    }}
                }};
                Object.defineProperty(NavProto, 'userAgentData', {{
                    get: () => mockUserAgentData,
                    configurable: true,
                    enumerable: true
                }});
                spoofProperty(NavProto, 'userAgentData', mockUserAgentData);
            }} else {{
                // Firefox/iOS: userAgentData 속성 자체를 완전히 삭제
                // 실제 Firefox는 userAgentData 속성이 아예 없음
                try {{
                    delete Navigator.prototype.userAgentData;
                    delete navigator.userAgentData;
                }} catch(e) {{}}
                
                // prototype에서도 제거 시도
                if ('userAgentData' in Navigator.prototype) {{
                    Object.defineProperty(Navigator.prototype, 'userAgentData', {{
                        value: undefined,
                        writable: true,
                        configurable: true
                    }});
                    delete Navigator.prototype.userAgentData;
                }}
            }}
        }});
    }}
    
    // ========== pdfViewerEnabled 스푸핑 ==========
    safe(() => {{
        spoofProperty(NavProto, 'pdfViewerEnabled', CONFIG.pdfViewerEnabled);
    }});
    
    // ========== doNotTrack 스푸핑 ==========
    safe(() => {{
        spoofProperty(NavProto, 'doNotTrack', CONFIG.doNotTrack);
    }});
    
    // ========== Web Worker 스푸핑 ==========
    // Worker 내부에서도 동일한 값이 반환되도록 Worker 생성자를 가로챔
    safe(() => {{
        const OriginalWorker = window.Worker;
        
        // Worker 내부에 주입할 스푸핑 코드 (CONFIG 값 사용)
        // 주의: WorkerNavigator에 원래 없는 속성(productSub, maxTouchPoints, cookieEnabled 등)은
        // 실폰에서도 undefined이므로 스푸핑하지 않음
        const workerSpoofCode = `
            // Worker 내부 navigator + WebGL 스푸핑
            (function() {{
                const spoofedValues = {{
                    userAgent: ` + JSON.stringify(CONFIG.ua) + `,
                    platform: ` + JSON.stringify(CONFIG.platform) + `,
                    languages: Object.freeze(` + JSON.stringify(CONFIG.languagesArray) + `),
                    language: ` + JSON.stringify(CONFIG.languageSingle) + `,
                    hardwareConcurrency: ` + CONFIG.hardwareConcurrency + `,
                    deviceMemory: ` + (CONFIG.deviceMemory !== undefined ? CONFIG.deviceMemory : 'undefined') + `,
                    appVersion: ` + JSON.stringify(CONFIG.ua.replace('Mozilla/', '')) + `,
                    vendor: ` + JSON.stringify(CONFIG.vendor) + `,
                    appCodeName: "Mozilla",
                    appName: "Netscape",
                    product: "Gecko",
                    webglVendor: ` + JSON.stringify(CONFIG.webglVendor) + `,
                    webglRenderer: ` + JSON.stringify(CONFIG.webglRenderer) + `,
                    webglUnmaskedVendor: ` + JSON.stringify(CONFIG.webglUnmaskedVendor) + `,
                    webglUnmaskedRenderer: ` + JSON.stringify(CONFIG.webglUnmaskedRenderer) + `
                }};
                
                const WorkerNavProto = Object.getPrototypeOf(navigator);
                
                // navigator 속성 스푸핑 (WorkerNavigator에 원래 있는 속성만)
                Object.defineProperty(WorkerNavProto, 'userAgent', {{ get: () => spoofedValues.userAgent, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'platform', {{ get: () => spoofedValues.platform, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'languages', {{ get: () => spoofedValues.languages, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'language', {{ get: () => spoofedValues.language, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'hardwareConcurrency', {{ get: () => spoofedValues.hardwareConcurrency, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'appVersion', {{ get: () => spoofedValues.appVersion, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'appCodeName', {{ get: () => spoofedValues.appCodeName, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'appName', {{ get: () => spoofedValues.appName, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'product', {{ get: () => spoofedValues.product, configurable: true, enumerable: true }});
                Object.defineProperty(WorkerNavProto, 'onLine', {{ get: () => true, configurable: true, enumerable: true }});
                if (spoofedValues.deviceMemory !== undefined) {{
                    Object.defineProperty(WorkerNavProto, 'deviceMemory', {{ get: () => spoofedValues.deviceMemory, configurable: true, enumerable: true }});
                }}
                
                // Worker 내부 WebGL 스푸핑 (OffscreenCanvas용)
                if (typeof WebGLRenderingContext !== 'undefined') {{
                    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(param) {{
                        // 37445 = UNMASKED_VENDOR_WEBGL, 37446 = UNMASKED_RENDERER_WEBGL
                        if (param === 37445) return spoofedValues.webglUnmaskedVendor;
                        if (param === 37446) return spoofedValues.webglUnmaskedRenderer;
                        // 7936 = VENDOR, 7937 = RENDERER
                        if (param === 7936) return spoofedValues.webglVendor;
                        if (param === 7937) return spoofedValues.webglRenderer;
                        return originalGetParameter.call(this, param);
                    }};
                }}
                
                if (typeof WebGL2RenderingContext !== 'undefined') {{
                    const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter = function(param) {{
                        if (param === 37445) return spoofedValues.webglUnmaskedVendor;
                        if (param === 37446) return spoofedValues.webglUnmaskedRenderer;
                        if (param === 7936) return spoofedValues.webglVendor;
                        if (param === 7937) return spoofedValues.webglRenderer;
                        return originalGetParameter2.call(this, param);
                    }};
                }}
            }})();
        `;
        
        // Worker 생성자 래핑
        window.Worker = function(scriptURL, options) {{
            // Blob URL인 경우 - Blob을 통해 이미 스푸핑 코드가 주입됨
            if (scriptURL instanceof URL || (typeof scriptURL === 'string' && scriptURL.startsWith('blob:'))) {{
                return new OriginalWorker(scriptURL, options);
            }}
            
            // 일반 스크립트 URL인 경우
            try {{
                // 스크립트 내용을 가져와서 스푸핑 코드를 앞에 추가
                const xhr = new XMLHttpRequest();
                xhr.open('GET', scriptURL, false); // 동기 요청
                xhr.send();
                
                if (xhr.status === 200) {{
                    const originalCode = xhr.responseText;
                    const modifiedCode = workerSpoofCode + '\\n' + originalCode;
                    const blob = new OriginalBlob([modifiedCode], {{ type: 'application/javascript' }});
                    const blobURL = URL.createObjectURL(blob);
                    return new OriginalWorker(blobURL, options);
                }}
            }} catch (e) {{
                // 실패 시 원본 Worker 생성
            }}
            
            return new OriginalWorker(scriptURL, options);
        }};
        
        // Worker.prototype 복사
        window.Worker.prototype = OriginalWorker.prototype;
        Object.defineProperty(window.Worker, 'name', {{ value: 'Worker', configurable: true }});
        
        // Blob 생성도 가로채서 Worker용 Blob에 스푸핑 코드 주입
        const OriginalBlob = window.Blob;
        window.Blob = function(parts, options) {{
            // JavaScript Blob인 경우 스푸핑 코드 주입
            if (options && options.type && options.type.includes('javascript')) {{
                const originalCode = parts.join('');
                const modifiedCode = workerSpoofCode + '\\n' + originalCode;
                return new OriginalBlob([modifiedCode], options);
            }}
            return new OriginalBlob(parts, options);
        }};
        window.Blob.prototype = OriginalBlob.prototype;
        Object.defineProperty(window.Blob, 'name', {{ value: 'Blob', configurable: true }});
    }});
    
    console.log('[CDP Mobile Spoof] 설정 완료:', {{
        ua: CONFIG.ua.substring(0, 50) + '...',
        platform: CONFIG.platform,
        model: CONFIG.model,
        dpr: CONFIG.dpr,
        screen: CONFIG.screenWidth + 'x' + CONFIG.screenHeight,
        randomIP: CONFIG.randomMobileIP
    }});
    
    // ========== 추가 스푸핑 1: Error.prepareStackTrace ==========
    // CDP 스택 트레이스에서 의심스러운 문자열 필터링
    safe(() => {{
        const originalPrepareStackTrace = Error.prepareStackTrace;
        Error.prepareStackTrace = function(error, structuredStackTrace) {{
            if (originalPrepareStackTrace) {{
                return originalPrepareStackTrace(error, structuredStackTrace);
            }}
            return error.stack;
        }};
        
        // Error.captureStackTrace도 래핑
        if (Error.captureStackTrace) {{
            const originalCaptureStackTrace = Error.captureStackTrace;
            Error.captureStackTrace = function(targetObject, constructorOpt) {{
                originalCaptureStackTrace(targetObject, constructorOpt);
                // 스택에서 CDP/puppeteer 관련 문자열 제거
                if (targetObject.stack) {{
                    targetObject.stack = targetObject.stack
                        .split('\\n')
                        .filter(line => !line.includes('puppeteer') && 
                                       !line.includes('devtools') && 
                                       !line.includes('__puppeteer') &&
                                       !line.includes('__playwright'))
                        .join('\\n');
                }}
            }};
        }}
    }});
    
    // ========== 추가 스푸핑 2: Object.getOwnPropertyNames(window/navigator) ==========
    // window/navigator 객체에서 CDP/자동화 관련 속성 숨기기
    safe(() => {{
        const originalGetOwnPropertyNames = Object.getOwnPropertyNames;
        Object.getOwnPropertyNames = function(obj) {{
            const result = originalGetOwnPropertyNames.call(this, obj);
            
            // ★★★ navigator 객체: 빈 배열 반환 (rebrowser 테스트 통과용) ★★★
            // 실제 브라우저에서 Object.getOwnPropertyNames(navigator)는 빈 배열 반환
            // 모든 속성은 Navigator.prototype에서 상속받음
            if (obj === navigator) {{
                return [];
            }}
            
            // window 객체: CDP/자동화 관련 속성 필터링
            if (obj === window) {{
                // CDP/자동화 관련 속성 필터링
                const filtered = result.filter(prop => {{
                    return !prop.startsWith('cdc_') &&
                           !prop.startsWith('$cdc_') &&
                           !prop.includes('webdriver') &&
                           !prop.includes('__driver') &&
                           !prop.includes('__selenium') &&
                           !prop.includes('__puppeteer') &&
                           !prop.includes('__playwright') &&
                           !prop.includes('domAutomation');
                }});
                return filtered;
            }}
            return result;
        }};
        
        // Object.keys도 동일하게 처리
        const originalKeys = Object.keys;
        Object.keys = function(obj) {{
            const result = originalKeys.call(this, obj);
            
            // ★★★ navigator 객체: 빈 배열 반환 ★★★
            if (obj === navigator) {{
                return [];
            }}
            
            if (obj === window) {{
                return result.filter(prop => {{
                    return !prop.startsWith('cdc_') &&
                           !prop.startsWith('$cdc_') &&
                           !prop.includes('webdriver');
                }});
            }}
            return result;
        }};
    }});
    
    // ========== 추가 스푸핑 3: navigator.scheduling ==========
    // 스케줄링 API 스푸핑 (실제 브라우저와 동일하게)
    safe(() => {{
        if (!navigator.scheduling) {{
            const scheduling = {{
                isInputPending: function(options) {{
                    return false; // 입력 대기 중 아님
                }}
            }};
            Object.defineProperty(navigator, 'scheduling', {{
                get: () => scheduling,
                configurable: true,
                enumerable: true
            }});
        }}
    }});
    
    // ========== 추가 스푸핑 4: Date.getTimezoneOffset ==========
    // 한국 타임존 고정 (-540분 = UTC+9)
    safe(() => {{
        const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = function() {{
            return -540; // 한국 시간대 (UTC+9)
        }};
    }});
    
    // ========== 추가 스푸핑 5: iframe.contentWindow ==========
    // iframe 내부에도 스푸핑 전파
    safe(() => {{
        const originalCreateElement = document.createElement;
        document.createElement = function(tagName) {{
            const element = originalCreateElement.call(document, tagName);
            
            if (tagName.toLowerCase() === 'iframe') {{
                // iframe이 DOM에 추가될 때 스푸핑 전파
                const originalAppendChild = element.appendChild;
                
                // load 이벤트에서 스푸핑 적용
                element.addEventListener('load', function() {{
                    try {{
                        const iframeWindow = element.contentWindow;
                        const iframeNavigator = iframeWindow.navigator;
                        const iframeNavProto = Object.getPrototypeOf(iframeNavigator);
                        
                        // webdriver 스푸핑
                        Object.defineProperty(iframeNavProto, 'webdriver', {{
                            get: () => false,
                            configurable: true
                        }});
                        
                        // userAgent 스푸핑
                        Object.defineProperty(iframeNavProto, 'userAgent', {{
                            get: () => CONFIG.userAgent,
                            configurable: true
                        }});
                        
                        // platform 스푸핑
                        Object.defineProperty(iframeNavProto, 'platform', {{
                            get: () => CONFIG.platform,
                            configurable: true
                        }});
                    }} catch(e) {{
                        // cross-origin iframe은 접근 불가 - 무시
                    }}
                }});
            }}
            
            return element;
        }};
    }});
    
    // ========== 추가 스푸핑 6: navigator.product ==========
    // Main thread에서도 "Gecko" 반환 (모든 브라우저 공통)
    safe(() => {{
        spoofProperty(NavProto, 'product', 'Gecko');
    }});
    
}})();
"""
    return js_code


# ============================================
# 터치 포인트 헬퍼 함수
# ============================================
def create_touch_point(x, y):
    """
    모바일 손가락 터치를 시뮬레이션하는 터치 포인트 생성
    압력(force)과 반지름(radiusX, radiusY) 추가
    """
    props = CONFIG["touch_properties"]
    
    # 손가락 반지름 랜덤 생성 (약간 타원형으로)
    base_radius = random.uniform(props["radius_min"], props["radius_max"])
    radius_x = base_radius + random.uniform(-2, 2)
    radius_y = base_radius + random.uniform(-2, 2)
    
    # 터치 압력 랜덤 생성
    force = random.uniform(props["force_min"], props["force_max"])
    
    return {
        "x": x,
        "y": y,
        "radiusX": radius_x,
        "radiusY": radius_y,
        "force": force
    }


# ============================================
# 터치 스크롤
# ============================================
def do_touch_scroll(cdp, distance, show_effect=True):
    """터치 스크롤 한 번 실행 (랜덤화 적용) + 시각적 피드백"""
    viewport = CONFIG["viewport"]
    scroll_config = CONFIG["scroll"]
    touch_random = CONFIG["touch_random"]
    
    # 랜덤화된 거리
    distance_variation = random.randint(-scroll_config["distance_random"], scroll_config["distance_random"])
    actual_distance = distance + distance_variation if distance > 0 else distance - distance_variation
    
    # 랜덤화된 X 좌표 (중앙 ± x_range)
    center_x = viewport["width"] // 2
    x = center_x + random.randint(-touch_random["x_range"], touch_random["x_range"])
    
    # 랜덤화된 Y 시작 위치
    base_start_y = int(viewport["height"] * 0.7)
    start_y = base_start_y + random.randint(-touch_random["y_range"], touch_random["y_range"])
    end_y = start_y - actual_distance
    
    print(f"[터치 스크롤] 시작: ({x}, {start_y}) → 끝: ({x}, {end_y}), 거리: {actual_distance}px")
    
    # 시각적 피드백 - 스크롤 시작점에 파란 점, 경로 표시
    if show_effect:
        cdp.send("Runtime.evaluate", {
            "expression": f"""
            (function() {{
                // 시작점 (파란색)
                const startDot = document.createElement('div');
                startDot.style.cssText = `
                    position:fixed; left:{x-10}px; top:{start_y-10}px;
                    width:20px; height:20px; background:rgba(0,100,255,0.8);
                    border-radius:50%; z-index:999999;
                    pointer-events:none;
                `;
                document.body.appendChild(startDot);
                
                // 끝점 (초록색)
                const endDot = document.createElement('div');
                endDot.style.cssText = `
                    position:fixed; left:{x-10}px; top:{end_y-10}px;
                    width:20px; height:20px; background:rgba(0,255,100,0.8);
                    border-radius:50%; z-index:999999;
                    pointer-events:none;
                `;
                document.body.appendChild(endDot);
                
                // 경로 선
                const line = document.createElement('div');
                line.style.cssText = `
                    position:fixed; left:{x-2}px; top:{min(start_y, end_y)}px;
                    width:4px; height:{abs(actual_distance)}px;
                    background:linear-gradient(to bottom, rgba(0,100,255,0.5), rgba(0,255,100,0.5));
                    z-index:999998; pointer-events:none;
                `;
                document.body.appendChild(line);
                
                setTimeout(() => {{
                    startDot.remove();
                    endDot.remove();
                    line.remove();
                }}, 800);
            }})()
            """.replace("{min(start_y, end_y)}", str(min(start_y, end_y))).replace("{abs(actual_distance)}", str(abs(int(actual_distance))))
        })
    
    # touchStart (압력/반지름 포함)
    touch_point = create_touch_point(x, start_y)
    print(f"[터치 시작] force: {touch_point['force']:.2f}, radius: ({touch_point['radiusX']:.1f}, {touch_point['radiusY']:.1f})")
    
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [touch_point]
    })
    
    # touchMove (여러 스텝으로 나눠서)
    steps = scroll_config["steps"]
    step_distance = actual_distance / steps
    current_y = start_y
    
    for i in range(steps):
        current_y -= step_distance
        # X 좌표도 약간씩 흔들림 추가
        x_wobble = x + random.randint(-3, 3)
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [create_touch_point(x_wobble, int(current_y))]
        })
        time.sleep(scroll_config["step_delay"])
    
    # touchEnd
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchEnd",
        "touchPoints": []
    })
    
    print(f"[터치 스크롤 완료] {steps}스텝")
    
    # 읽기 멈춤 (확률 기반)
    maybe_reading_pause()


def maybe_reading_pause():
    """스크롤 후 확률적으로 읽기 멈춤"""
    pause_config = CONFIG["reading_pause"]
    
    if not pause_config["enabled"]:
        return
    
    if random.random() < pause_config["probability"]:
        pause_time = random.uniform(pause_config["min_time"], pause_config["max_time"])
        print(f"[읽기 멈춤] {pause_time:.1f}초 대기...")
        time.sleep(pause_time)


def do_pull_to_refresh(cdp):
    """
    모바일 방식 새로고침 (Pull to Refresh)
    화면 상단에서 아래로 드래그
    """
    viewport = CONFIG["viewport"]
    center_x = viewport["width"] // 2
    
    print("[새로고침] Pull to Refresh 실행...")
    
    # 1. 먼저 페이지 맨 위로 스크롤
    cdp.send("Runtime.evaluate", {
        "expression": "window.scrollTo(0, 0)"
    })
    time.sleep(0.3)
    
    # 2. 시각적 표시
    cdp.send("Runtime.evaluate", {
        "expression": f"""
        (function() {{
            const arrow = document.createElement('div');
            arrow.innerHTML = '↓ REFRESH ↓';
            arrow.style.cssText = `
                position:fixed; left:50%; top:150px;
                transform:translateX(-50%);
                font-size:24px; color:red; font-weight:bold;
                z-index:999999; background:yellow; padding:5px 15px;
            `;
            document.body.appendChild(arrow);
            setTimeout(() => arrow.remove(), 1500);
        }})()
        """
    })
    
    # 3. 상단에서 시작해서 아래로 길게 당기기
    start_y = 100
    end_y = viewport["height"] - 100
    start_x = center_x + random.randint(-20, 20)
    
    # touchStart (압력/반지름 포함)
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [create_touch_point(start_x, start_y)]
    })
    time.sleep(0.05)
    
    # touchMove (천천히 아래로 드래그)
    steps = 30
    for i in range(steps):
        current_y = start_y + (end_y - start_y) * (i + 1) / steps
        x_wobble = center_x + random.randint(-5, 5)
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [create_touch_point(x_wobble, int(current_y))]
        })
        time.sleep(0.02)
    
    # 끝에서 유지 (새로고침 트리거 대기)
    time.sleep(0.5)
    
    # touchEnd
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchEnd",
        "touchPoints": []
    })
    
    print("[새로고침] 완료, 페이지 로딩 대기...")
    time.sleep(CONFIG["retry"]["after_refresh_delay"])


def check_page_error(cdp):
    """
    페이지 오류 확인 (VPN/프록시 오류 등)
    
    Returns:
        True: 오류 있음
        False: 정상
    """
    error_texts = CONFIG["retry"]["error_texts"]
    
    js_code = """
    (function() {
        const bodyText = document.body ? document.body.innerText : '';
        const errorTexts = ERROR_TEXTS_PLACEHOLDER;
        
        for (let errorText of errorTexts) {
            if (bodyText.includes(errorText)) {
                return { hasError: true, errorText: errorText };
            }
        }
        return { hasError: false };
    })()
    """.replace("ERROR_TEXTS_PLACEHOLDER", json.dumps(error_texts))
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    value = result.get("result", {}).get("value", {"hasError": False})
    
    if value.get("hasError"):
        print(f"[오류 감지] 페이지 오류: {value.get('errorText')}")
        return True
    
    return False


def do_touch_click(cdp, x, y, duration=0.05, show_effect=True):
    """터치 클릭 (탭) 실행 + 시각적 피드백"""
    # 약간의 랜덤 지연
    time.sleep(random.uniform(0.01, 0.03))
    
    print(f"[터치 클릭 시작] x: {x:.1f}, y: {y:.1f}")
    
    # 시각적 피드백 - 클릭 위치에 빨간 점 표시
    if show_effect:
        cdp.send("Runtime.evaluate", {
            "expression": f"""
            (function() {{
                const dot = document.createElement('div');
                dot.style.cssText = `
                    position:fixed; left:{x-15}px; top:{y-15}px;
                    width:30px; height:30px; background:rgba(255,0,0,0.7);
                    border-radius:50%; z-index:999999;
                    pointer-events:none; transition:all 0.3s;
                    box-shadow: 0 0 10px red;
                `;
                document.body.appendChild(dot);
                setTimeout(() => {{
                    dot.style.transform = 'scale(1.5)';
                    dot.style.opacity = '0';
                }}, 100);
                setTimeout(() => dot.remove(), 500);
            }})()
            """
        })
    
    # touchStart (압력/반지름 포함)
    touch_point = create_touch_point(x, y)
    print(f"[터치 속성] force: {touch_point['force']:.2f}, radius: ({touch_point['radiusX']:.1f}, {touch_point['radiusY']:.1f})")
    
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [touch_point]
    })
    
    # 클릭 유지 시간 (랜덤화)
    hold_time = duration + random.uniform(0, 0.03)
    print(f"[터치 홀드] {hold_time:.3f}초")
    time.sleep(hold_time)
    
    # touchEnd
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchEnd",
        "touchPoints": []
    })
    
    print(f"[터치 클릭 완료]")


def do_triple_touch(cdp, x, y):
    """트리플 터치 (전체선택)"""
    print(f"[트리플 터치] x: {x:.1f}, y: {y:.1f}")
    
    for i in range(3):
        touch_point = create_touch_point(x, y)
        
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [touch_point]
        })
        time.sleep(random.uniform(0.03, 0.05))
        
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": []
        })
        time.sleep(random.uniform(0.03, 0.06))
    
    print(f"[트리플 터치 완료]")


def check_text_selected(cdp):
    """텍스트 선택 여부 확인"""
    result = cdp.send("Runtime.evaluate", {
        "expression": "window.getSelection().toString().length > 0",
        "returnByValue": True
    })
    return result.get("result", {}).get("value", False)


def do_history_back(cdp):
    """브라우저 뒤로가기 (history.back)"""
    print(f"[뒤로가기] history.back() 실행")
    
    cdp.send("Runtime.evaluate", {
        "expression": "history.back()"
    })
    
    # 페이지 이동 대기
    time.sleep(random.uniform(1.0, 2.0))
    print(f"[뒤로가기 완료]")


def get_element_bounds(cdp, selector=None, text=None):
    """요소의 위치와 크기 가져오기"""
    if text:
        js_code = f"""
        (function() {{
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            
            let node;
            while (node = walker.nextNode()) {{
                if (node.textContent.trim().includes("{text}")) {{
                    const el = node.parentElement;
                    const rect = el.getBoundingClientRect();
                    return {{
                        found: true,
                        x: rect.left,
                        y: rect.top,
                        width: rect.width,
                        height: rect.height,
                        centerX: rect.left + rect.width / 2,
                        centerY: rect.top + rect.height / 2
                    }};
                }}
            }}
            return {{ found: false }};
        }})()
        """
    else:
        js_code = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (el) {{
                const rect = el.getBoundingClientRect();
                return {{
                    found: true,
                    x: rect.left,
                    y: rect.top,
                    width: rect.width,
                    height: rect.height,
                    centerX: rect.left + rect.width / 2,
                    centerY: rect.top + rect.height / 2
                }};
            }}
            return {{ found: false }};
        }})()
        """
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    return result.get("result", {}).get("value", {"found": False})


def wait_for_element(cdp, selectors, timeout=None, interval=None, after_delay=True):
    """
    요소가 나타날 때까지 대기
    
    Args:
        cdp: CDP 연결
        selectors: selector 리스트 (우선순위대로)
        timeout: 최대 대기 시간 (초)
        interval: 체크 간격 (초)
        after_delay: 요소 발견 후 추가 딜레이 적용 여부
    
    Returns:
        {"found": True/False, "selector": 찾은 selector, "bounds": 요소 정보}
    """
    wait_config = CONFIG["wait"]
    timeout = timeout or wait_config["timeout"]
    interval = interval or wait_config["interval"]
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        for selector in selectors:
            bounds = get_element_bounds(cdp, selector=selector)
            if bounds.get("found") and bounds.get("height", 0) > 0:
                print(f"[대기 완료] 요소 발견: {selector} ({time.time() - start_time:.1f}초)")
                
                # 요소 발견 후 추가 딜레이
                if after_delay:
                    delay = wait_config["after_found_delay"]
                    delay_random = wait_config["after_found_delay_random"]
                    sleep_time = delay + random.uniform(0, delay_random)
                    time.sleep(sleep_time)
                
                return {"found": True, "selector": selector, "bounds": bounds}
        
        time.sleep(interval)
    
    print(f"[대기 실패] 요소를 찾지 못함 ({timeout}초 초과)")
    return {"found": False, "selector": None, "bounds": None}


def wait_for_element_with_retry(cdp, selectors, timeout=None, interval=None, after_delay=True):
    """
    요소가 나타날 때까지 대기 (30번 x 2회, 메인 재이동 포함)
    페이지 오류 감지시 ERROR 반환
    30번 x 2회 모두 실패 시 ERROR 반환 (종료)
    
    Args:
        cdp: CDP 연결
        selectors: selector 리스트 (우선순위대로)
        timeout: 최대 대기 시간 (초)
        interval: 체크 간격 (초)
        after_delay: 요소 발견 후 추가 딜레이 적용 여부
    
    Returns:
        {"found": True/False, "selector": 찾은 selector, "bounds": 요소 정보, "error": 오류여부}
    """
    max_retry = CONFIG["retry"]["max_element_retry"]  # 30
    max_full_retry = CONFIG["retry"]["max_full_retry"]  # 2
    
    for full_round in range(max_full_retry):
        if full_round > 0:
            print(f"\n[요소 대기 재시도 {full_round + 1}/{max_full_retry}] 메인으로 이동 후 다시 시도...")
            cdp.navigate(CONFIG["naver_mobile_url"])
            time.sleep(CONFIG["retry"]["after_refresh_delay"])
        
        for retry_count in range(1, max_retry + 1):
            # 페이지 오류 체크
            if check_page_error(cdp):
                print(f"[오류] 페이지 오류 감지!")
                return {"found": False, "selector": None, "bounds": None, "error": True}
            
            # 요소 대기
            result = wait_for_element(cdp, selectors, timeout=timeout, interval=interval, after_delay=after_delay)
            
            if result["found"]:
                return {"found": True, "selector": result["selector"], "bounds": result["bounds"], "error": False}
            
            if retry_count < max_retry:
                print(f"[재시도 {retry_count}/{max_retry}] 요소를 찾지 못함, 다시 시도...")
                time.sleep(0.5)
        
        print(f"[실패] 요소 대기 {max_retry}번 실패")
    
    # 전체 재시도 모두 실패 → 종료
    print(f"[오류] 요소 대기 {max_retry}번 x {max_full_retry}회 모두 실패")
    return {"found": False, "selector": None, "bounds": None, "error": True}


def wait_for_any_element(cdp, selector_groups, timeout=None):
    """
    여러 그룹 중 하나라도 나타나면 반환
    
    Args:
        cdp: CDP 연결
        selector_groups: {"이름": [selectors], ...}
        timeout: 최대 대기 시간
    
    Returns:
        {"found": True/False, "group": 그룹 이름, "selector": 찾은 selector}
    """
    wait_config = CONFIG["wait"]
    timeout = timeout or wait_config["timeout"]
    interval = wait_config["interval"]
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        for group_name, selectors in selector_groups.items():
            for selector in selectors:
                bounds = get_element_bounds(cdp, selector=selector)
                if bounds.get("found") and bounds.get("height", 0) > 0:
                    print(f"[대기 완료] {group_name} 발견: {selector}")
                    return {"found": True, "group": group_name, "selector": selector, "bounds": bounds}
        
        time.sleep(interval)
    
    return {"found": False, "group": None, "selector": None, "bounds": None}


def find_domain_links(cdp, domain):
    """
    도메인의 메인 링크들 찾기 (서브링크 제외)
    
    Args:
        cdp: CDP 연결
        domain: 타겟 도메인 (예: sidecut.co.kr)
    
    Returns:
        {"found": True/False, "links": [링크 정보들], "count": 개수}
    """
    # 도메인의 . 을 이스케이프 처리
    domain_escaped = domain.replace('.', '\\\\.')
    
    js_code = """
    (function() {
        // 도메인이 포함된 모든 a 태그 찾기
        const allLinks = document.querySelectorAll('a[href*="DOMAIN_PLACEHOLDER"]');
        const mainLinks = [];
        
        allLinks.forEach((link, index) => {
            const href = link.getAttribute('href');
            // 메인 페이지 링크만 (/ 로 끝나거나 도메인만 있는 경우)
            // 서브링크 제외 (/lessons, /about 등)
            if (href && (
                href.endsWith('DOMAIN_PLACEHOLDER/') || 
                href.endsWith('DOMAIN_PLACEHOLDER') ||
                href.match(/https?:\\/\\/DOMAIN_ESCAPED\\/?$/)
            )) {
                const rect = link.getBoundingClientRect();
                // 화면에 보이는 링크만
                if (rect.height > 0 && rect.top >= 0 && rect.top < window.innerHeight) {
                    mainLinks.push({
                        index: index,
                        href: href,
                        x: rect.left,
                        y: rect.top,
                        width: rect.width,
                        height: rect.height,
                        centerX: rect.left + rect.width / 2,
                        centerY: rect.top + rect.height / 2
                    });
                }
            }
        });
        
        return {
            found: mainLinks.length > 0,
            links: mainLinks,
            count: mainLinks.length
        };
    })()
    """.replace("DOMAIN_PLACEHOLDER", domain).replace("DOMAIN_ESCAPED", domain_escaped)
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    return result.get("result", {}).get("value", {"found": False, "links": [], "count": 0})


def get_web_domain_links(cdp, domain):
    """
    통합 페이지에서 웹사이트 영역의 도메인 링크 가져오기 (광고 제외)
    - 도메인, 제목, 설명 링크 모두 포함
    - 공통 부모 컨테이너(iHhwD75sS6ExHVLVl9Mi) 기준으로 찾기
    - 파워링크/광고 영역 제외
    - 경로가 포함된 경우 정확한 경로 매칭 (예: skincora.com/coratherapy.php)
    
    Returns:
        {"found": True/False, "links": [링크들], "count": 개수, "debug": 디버그정보}
    """
    # 도메인에 경로가 포함되어 있는지 확인 (/ 뒤에 뭔가 있으면 경로)
    has_path = '/' in domain and not domain.endswith('/')
    
    print(f"\n[도메인 검색] ========================================")
    print(f"[도메인 검색] 타겟: {domain}")
    print(f"[도메인 검색] hasPath: {has_path}")
    
    js_code = """
    (function() {
        const targetDomain = "DOMAIN_PLACEHOLDER";
        const hasPath = HAS_PATH_PLACEHOLDER;
        
        const baseDomain = targetDomain.split('/')[0];
        const allLinks = document.querySelectorAll('a[href*="' + baseDomain + '"]');
        const webLinks = [];
        const debugInfo = {
            totalFound: allLinks.length,
            allHrefs: [],
            matchResults: [],
            excluded: {
                noHref: 0,
                notMatch: 0,
                isAd: 0,
                notWebArea: 0,
                noSize: 0
            }
        };
        
        allLinks.forEach((link, index) => {
            const href = link.getAttribute('href');
            const debugEntry = {
                index: index,
                href: href || '(없음)',
                endsWithTarget: false,
                endsWithTargetSlash: false,
                isMatch: false,
                isAd: false,
                isWebArea: false,
                excluded: null,
                heatmapTarget: link.getAttribute('data-heatmap-target') || '(없음)'
            };
            
            if (!href) {
                debugEntry.excluded = 'noHref';
                debugInfo.excluded.noHref++;
                debugInfo.matchResults.push(debugEntry);
                return;
            }
            
            debugInfo.allHrefs.push(href);
            
            // 경로 매칭 체크
            let isMatch = false;
            debugEntry.endsWithTarget = href.endsWith(targetDomain);
            debugEntry.endsWithTargetSlash = href.endsWith(targetDomain + '/');
            
            if (hasPath) {
                // 경로가 지정된 경우: 정확한 경로 매칭
                if (href.endsWith(targetDomain) || href.endsWith(targetDomain + '/')) {
                    isMatch = true;
                }
            } else {
                // 경로가 없는 경우: 메인 도메인만 (서브링크 제외)
                if (href.endsWith(targetDomain + '/') || href.endsWith(targetDomain)) {
                    isMatch = true;
                }
            }
            
            debugEntry.isMatch = isMatch;
            
            if (!isMatch) {
                debugEntry.excluded = 'notMatch';
                debugInfo.excluded.notMatch++;
                debugInfo.matchResults.push(debugEntry);
                return;
            }
            
            // 서브링크(.sublink) 제외 - 메인 결과의 서브링크는 위치 겹침 문제 있음
            const heatmapTarget = link.getAttribute('data-heatmap-target');
            debugEntry.isSublink = (heatmapTarget === '.sublink');
            if (heatmapTarget === '.sublink') {
                debugEntry.excluded = 'isSublink';
                debugInfo.excluded.isSublink = (debugInfo.excluded.isSublink || 0) + 1;
                debugInfo.matchResults.push(debugEntry);
                return;
            }
            
            // 광고 영역 제외
            let parent = link.parentElement;
            let isAd = false;
            while (parent) {
                if (parent.classList && (
                    parent.classList.contains('tit_area') ||
                    parent.classList.contains('ad_area') ||
                    parent.classList.contains('powerlink')
                )) {
                    isAd = true;
                    break;
                }
                parent = parent.parentElement;
            }
            
            debugEntry.isAd = isAd;
            if (isAd) {
                debugEntry.excluded = 'isAd';
                debugInfo.excluded.isAd++;
                debugInfo.matchResults.push(debugEntry);
                return;
            }
            
            // 웹사이트 영역 체크 (공통 부모 컨테이너 기준)
            let isWebArea = false;
            parent = link.parentElement;
            
            while (parent) {
                // 1. 부모 중에 type-web 클래스가 있는지
                if (parent.classList && parent.classList.contains('type-web')) {
                    isWebArea = true;
                    break;
                }
                // 2. 부모 중에 data-sds-comp="Profile"이 있는지
                if (parent.getAttribute && parent.getAttribute('data-sds-comp') === 'Profile') {
                    isWebArea = true;
                    break;
                }
                // 3. 부모 중에 type-web을 포함하는 자식이 있는 컨테이너인지 (제목/설명용)
                if (parent.querySelector && parent.querySelector('.type-web')) {
                    isWebArea = true;
                    break;
                }
                parent = parent.parentElement;
            }
            
            debugEntry.isWebArea = isWebArea;
            if (!isWebArea) {
                debugEntry.excluded = 'notWebArea';
                debugInfo.excluded.notWebArea++;
                debugInfo.matchResults.push(debugEntry);
                return;
            }
            
            const rect = link.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                debugEntry.excluded = null;  // 통과!
                debugInfo.matchResults.push(debugEntry);
                webLinks.push({
                    index: index,
                    href: href,
                    x: rect.left,
                    y: rect.top,
                    width: rect.width,
                    height: rect.height,
                    centerX: rect.left + rect.width / 2,
                    centerY: rect.top + rect.height / 2,
                    heatmapTarget: link.getAttribute('data-heatmap-target') || ''
                });
            } else {
                debugEntry.excluded = 'noSize';
                debugInfo.excluded.noSize++;
                debugInfo.matchResults.push(debugEntry);
            }
        });
        
        return {
            found: webLinks.length > 0,
            links: webLinks,
            count: webLinks.length,
            debug: debugInfo
        };
    })()
    """.replace("DOMAIN_PLACEHOLDER", domain).replace("HAS_PATH_PLACEHOLDER", "true" if has_path else "false")
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    data = result.get("result", {}).get("value", {"found": False, "links": [], "count": 0, "debug": {}})
    
    # 디버그 정보 출력
    debug = data.get("debug", {})
    print(f"[도메인 검색] 찾은 전체 링크 (baseDomain 포함): {debug.get('totalFound', 0)}개")
    
    # 모든 href 출력 (처음 10개만)
    all_hrefs = debug.get('allHrefs', [])
    print(f"[도메인 검색] href 목록 ({len(all_hrefs)}개):")
    for i, href in enumerate(all_hrefs[:15]):
        print(f"  [{i+1}] {href}")
    if len(all_hrefs) > 15:
        print(f"  ... 외 {len(all_hrefs) - 15}개")
    
    # 매칭 결과 상세
    match_results = debug.get('matchResults', [])
    print(f"\n[도메인 검색] 매칭 결과 상세:")
    for entry in match_results[:20]:
        href = entry.get('href', '')[:80]
        ends_target = entry.get('endsWithTarget', False)
        ends_slash = entry.get('endsWithTargetSlash', False)
        is_match = entry.get('isMatch', False)
        excluded = entry.get('excluded', '')
        heatmap = entry.get('heatmapTarget', '')
        
        status = "✅ 통과" if excluded is None else f"❌ 제외({excluded})"
        print(f"  href={href}")
        print(f"    → endsWith(target)={ends_target}, endsWith(target/)={ends_slash}, isMatch={is_match}")
        print(f"    → heatmapTarget={heatmap}, 결과={status}")
    
    # 제외 통계
    excluded = debug.get('excluded', {})
    print(f"\n[도메인 검색] 제외 통계:")
    print(f"  - noHref: {excluded.get('noHref', 0)}")
    print(f"  - notMatch: {excluded.get('notMatch', 0)}")
    print(f"  - isSublink: {excluded.get('isSublink', 0)}")
    print(f"  - isAd: {excluded.get('isAd', 0)}")
    print(f"  - notWebArea: {excluded.get('notWebArea', 0)}")
    print(f"  - noSize: {excluded.get('noSize', 0)}")
    
    # 최종 매칭된 링크
    print(f"\n[도메인 검색] ✅ 최종 매칭 링크: {data.get('count', 0)}개")
    for i, link in enumerate(data.get('links', [])):
        print(f"  [{i+1}] href={link.get('href', '')}")
        print(f"      x={link.get('x', 0):.0f}, y={link.get('y', 0):.0f}, w={link.get('width', 0):.0f}, h={link.get('height', 0):.0f}")
        print(f"      heatmapTarget={link.get('heatmapTarget', '')}")
    
    print(f"[도메인 검색] ========================================\n")
    
    return data


def get_current_url(cdp):
    """현재 페이지 URL 가져오기"""
    result = cdp.send("Runtime.evaluate", {
        "expression": "window.location.href",
        "returnByValue": True
    })
    return result.get("result", {}).get("value", "")


def is_page_loaded(cdp):
    """페이지 로딩 완료 여부 확인"""
    result = cdp.send("Runtime.evaluate", {
        "expression": "document.readyState",
        "returnByValue": True
    })
    state = result.get("result", {}).get("value", "")
    return state == "complete"


def wait_for_page_load(cdp, before_url, timeout=120, check_interval=0.5):
    """
    페이지 로딩 완료 대기
    - URL 변경 확인
    - document.readyState === 'complete' 확인
    
    Args:
        cdp: CDP 연결
        before_url: 클릭 전 URL
        timeout: 최대 대기 시간 (초)
        check_interval: 체크 간격 (초)
    
    Returns:
        True: 로딩 완료
        False: 타임아웃
    """
    start_time = time.time()
    url_changed = False
    
    print(f"[페이지 로딩 대기] 최대 {timeout}초...")
    
    while time.time() - start_time < timeout:
        current_url = get_current_url(cdp)
        
        # URL 변경 확인
        if current_url != before_url:
            url_changed = True
            
            # URL 변경 후 로딩 완료 확인
            if is_page_loaded(cdp):
                elapsed = time.time() - start_time
                print(f"[페이지 로딩 완료] {elapsed:.1f}초 소요")
                
                # 로딩 완료 후 대기 (사람처럼 페이지 훑어보기)
                page_load_config = CONFIG["page_load"]
                after_load_delay = random.uniform(
                    page_load_config["after_load_min"],
                    page_load_config["after_load_max"]
                )
                print(f"[로딩 후 대기] {after_load_delay:.1f}초...")
                time.sleep(after_load_delay)
                
                return True
        
        # 진행 상황 표시 (10초마다)
        elapsed = time.time() - start_time
        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
            status = "URL 변경됨, 로딩 중..." if url_changed else "URL 변경 대기 중..."
            print(f"[대기 중] {int(elapsed)}초 경과... ({status})")
        
        time.sleep(check_interval)
    
    print(f"[타임아웃] {timeout}초 초과")
    return False


def click_web_domain_link(cdp, domain):
    """
    통합 페이지 웹사이트 영역에서 도메인 링크를 찾아 랜덤 클릭
    스크롤하면서 찾음
    화면에 보이면 한번 더 랜덤 스크롤 후 클릭 (더 자연스럽게)
    클릭 후 URL 변경 확인, 안 됐으면 다른 링크로 재시도 (최대 3회)
    
    Returns:
        True: 찾아서 클릭함
        False: 못 찾음
    """
    viewport = CONFIG["viewport"]
    scroll_config = CONFIG["scroll"]
    max_scrolls = CONFIG["max_scrolls_total"]
    
    visible_top = viewport["height"] * 0.2
    visible_bottom = viewport["height"] * 0.8
    
    scroll_count = 0
    same_position_count = 0
    
    while scroll_count < max_scrolls:
        # 웹사이트 영역에서 도메인 링크 찾기
        web_links = get_web_domain_links(cdp, domain)
        
        if web_links["found"]:
            # 화면 중앙 영역에 있는 링크들 필터링
            visible_links = []
            for link in web_links["links"]:
                if visible_top <= link["centerY"] <= visible_bottom:
                    visible_links.append(link)
            
            # 화면에 보이는 링크가 있으면
            if visible_links:
                # 한번 더 랜덤 스크롤 (자연스럽게)
                extra_scroll = random.randint(50, 150) * random.choice([1, -1])
                do_touch_scroll(cdp, extra_scroll)
                time.sleep(random.uniform(0.3, 0.5))
                
                # 스크롤 후 다시 위치 확인
                web_links = get_web_domain_links(cdp, domain)
                visible_links = []
                for link in web_links["links"]:
                    if visible_top <= link["centerY"] <= visible_bottom:
                        visible_links.append(link)
                
                if visible_links:
                    print(f"[통합] 웹사이트 영역에서 {domain} 발견! {len(visible_links)}개 링크 (스크롤 {scroll_count}회)")
                    
                    # 찾은 링크들 로그 (x, width 포함)
                    for i, link in enumerate(visible_links):
                        print(f"  링크{i+1}: x={link['x']:.0f}, y={link['y']:.0f}, w={link['width']:.0f}, h={link['height']:.0f}")
                        print(f"          href={link['href']}")
                    
                    # 클릭 전 URL 저장
                    before_url = get_current_url(cdp)
                    
                    # 최대 3회 클릭 시도
                    clicked_indices = []
                    for click_attempt in range(3):
                        # 아직 클릭 안 한 링크 중에서 선택
                        available_links = [link for i, link in enumerate(visible_links) if i not in clicked_indices]
                        if not available_links:
                            available_links = visible_links  # 다 시도했으면 다시 전체에서
                        
                        selected = random.choice(available_links)
                        selected_index = visible_links.index(selected)
                        clicked_indices.append(selected_index)
                        
                        time.sleep(random.uniform(0.3, 0.5))
                        
                        x = selected["x"] + random.uniform(selected["width"] * 0.1, selected["width"] * 0.9)
                        y = selected["y"] + random.uniform(selected["height"] * 0.2, selected["height"] * 0.8)
                        
                        print(f"[클릭 시도 {click_attempt + 1}/3] 링크{selected_index+1} 선택")
                        print(f"  → 선택된 href: {selected.get('href', '')}")
                        print(f"  → 좌표: x={x:.1f}, y={y:.1f}")
                        
                        # 클릭 좌표의 실제 요소 확인
                        element_check = cdp.send("Runtime.evaluate", {
                            "expression": f"""
                            (function() {{
                                const el = document.elementFromPoint({x}, {y});
                                if (!el) return {{ found: false }};
                                
                                // 가장 가까운 a 태그 찾기
                                const link = el.closest('a');
                                return {{
                                    found: true,
                                    tagName: el.tagName,
                                    className: el.className.substring(0, 50),
                                    linkHref: link ? link.getAttribute('href') : '(a태그 없음)',
                                    linkHeatmap: link ? link.getAttribute('data-heatmap-target') : ''
                                }};
                            }})()
                            """,
                            "returnByValue": True
                        })
                        el_info = element_check.get("result", {}).get("value", {})
                        print(f"  → 클릭 좌표의 실제 요소:")
                        print(f"     tagName={el_info.get('tagName', '?')}, class={el_info.get('className', '?')[:30]}")
                        print(f"     linkHref={el_info.get('linkHref', '?')}")
                        print(f"     linkHeatmap={el_info.get('linkHeatmap', '?')}")
                        
                        do_touch_click(cdp, x, y)
                        
                        # 3초 대기 후 URL 변경 확인
                        time.sleep(3)
                        after_url = get_current_url(cdp)
                        
                        if after_url != before_url:
                            print(f"[성공] 페이지 이동 확인!")
                            return True
                        else:
                            print(f"[재시도] URL 변경 없음, 다른 링크 시도...")
                    
                    # 3회 모두 실패
                    print(f"[실패] 3회 클릭 시도 모두 실패")
                    return False
            
            # 링크는 있지만 화면 밖 → 스크롤
            first_link = web_links["links"][0]
            if first_link["centerY"] > visible_bottom:
                scroll_distance = scroll_config["distance"]
            else:
                scroll_distance = -scroll_config["distance"]
            
            before_scroll = get_scroll_position(cdp)
            do_touch_scroll(cdp, scroll_distance)
            time.sleep(0.3)
            after_scroll = get_scroll_position(cdp)
            scroll_count += 1
        else:
            # 링크 없음 → 아래로 스크롤
            before_scroll = get_scroll_position(cdp)
            do_touch_scroll(cdp, scroll_config["distance"])
            time.sleep(0.3)
            after_scroll = get_scroll_position(cdp)
            scroll_count += 1
        
        # 스크롤 횟수 로그 (5회마다)
        if scroll_count % 5 == 0:
            print(f"[4.5단계] 스크롤 {scroll_count}/{max_scrolls}회...")
        
        # 페이지 끝 감지
        if abs(after_scroll - before_scroll) < 10:
            same_position_count += 1
            if same_position_count >= 2:
                print(f"[통합] 페이지 끝 도달, 웹사이트 영역에 {domain} 없음 (스크롤 {scroll_count}회)")
                return False
        else:
            same_position_count = 0
        
        delay = scroll_config["delay"] + random.uniform(-scroll_config["delay_random"], scroll_config["delay_random"])
        time.sleep(delay)
    
    print(f"[통합] {domain} 링크를 찾을 수 없음 (스크롤 {scroll_count}회)")
    return False


def get_all_domain_links(cdp, domain):
    """
    더보기 페이지에서 도메인 링크 가져오기
    - 도메인, 제목, 설명 링크 모두 포함
    - 공통 부모 컨테이너 기준으로 찾기
    - 경로가 포함된 경우 정확한 경로 매칭 (예: skincora.com/coratherapy.php)
    
    Returns:
        {"found": True/False, "links": [링크들], "count": 개수}
    """
    # 도메인에 경로가 포함되어 있는지 확인 (/ 뒤에 뭔가 있으면 경로)
    has_path = '/' in domain and not domain.endswith('/')
    
    js_code = """
    (function() {
        const targetDomain = "DOMAIN_PLACEHOLDER";
        const hasPath = HAS_PATH_PLACEHOLDER;
        
        const allLinks = document.querySelectorAll('a[href*="' + targetDomain.split('/')[0] + '"]');
        const mainLinks = [];
        
        allLinks.forEach((link, index) => {
            const href = link.getAttribute('href');
            
            if (!href) return;
            
            // 경로 매칭 체크
            let isMatch = false;
            if (hasPath) {
                // 경로가 지정된 경우: 정확한 경로 매칭
                if (href.endsWith(targetDomain) || href.endsWith(targetDomain + '/')) {
                    isMatch = true;
                }
            } else {
                // 경로가 없는 경우: 메인 도메인만 (서브링크 제외)
                if (href.endsWith(targetDomain + '/') || href.endsWith(targetDomain)) {
                    isMatch = true;
                }
            }
            
            if (!isMatch) return;
            
            // 서브링크(.sublink) 제외 - 메인 결과의 서브링크는 위치 겹침 문제 있음
            const heatmapTarget = link.getAttribute('data-heatmap-target');
            if (heatmapTarget === '.sublink') {
                return;
            }
            
            // 웹사이트 영역 체크 (공통 부모 컨테이너 기준)
            let isWebArea = false;
            let parent = link.parentElement;
            
            while (parent) {
                // 1. 부모 중에 type-web 클래스가 있는지
                if (parent.classList && parent.classList.contains('type-web')) {
                    isWebArea = true;
                    break;
                }
                // 2. 부모 중에 data-sds-comp="Profile"이 있는지
                if (parent.getAttribute && parent.getAttribute('data-sds-comp') === 'Profile') {
                    isWebArea = true;
                    break;
                }
                // 3. 부모 중에 type-web을 포함하는 자식이 있는 컨테이너인지 (제목/설명용)
                if (parent.querySelector && parent.querySelector('.type-web')) {
                    isWebArea = true;
                    break;
                }
                parent = parent.parentElement;
            }
            
            if (!isWebArea) return;
            
            const rect = link.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                mainLinks.push({
                    index: index,
                    href: href,
                    x: rect.left,
                    y: rect.top,
                    width: rect.width,
                    height: rect.height,
                    centerX: rect.left + rect.width / 2,
                    centerY: rect.top + rect.height / 2
                });
            }
        });
        
        return {
            found: mainLinks.length > 0,
            links: mainLinks,
            count: mainLinks.length
        };
    })()
    """.replace("DOMAIN_PLACEHOLDER", domain).replace("HAS_PATH_PLACEHOLDER", "true" if has_path else "false")
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    return result.get("result", {}).get("value", {"found": False, "links": [], "count": 0})


def get_scroll_position(cdp):
    """현재 스크롤 Y 위치 가져오기"""
    result = cdp.send("Runtime.evaluate", {
        "expression": "window.scrollY || document.documentElement.scrollTop",
        "returnByValue": True
    })
    return result.get("result", {}).get("value", 0)


def click_domain_link(cdp, domain):
    """
    도메인 메인 링크를 터치 스크롤로 찾아가서 랜덤 클릭
    페이지 전체를 스크롤하면서 찾음
    페이지 끝에 도달하면 스크롤 중단
    화면에 보이면 한번 더 랜덤 스크롤 후 클릭 (더 자연스럽게)
    
    Args:
        cdp: CDP 연결
        domain: 타겟 도메인
    
    Returns:
        True/False
    """
    viewport = CONFIG["viewport"]
    scroll_config = CONFIG["scroll"]
    max_scrolls = 30  # 최대 스크롤 횟수
    
    # 화면 중앙 영역 (이 범위 안에 들어오면 클릭)
    visible_top = viewport["height"] * 0.2
    visible_bottom = viewport["height"] * 0.8
    
    scroll_count = 0
    same_position_count = 0  # 스크롤 위치가 안 변한 횟수
    
    while scroll_count < max_scrolls:
        # 현재 보이는 모든 메인 링크 가져오기
        all_links = get_all_domain_links(cdp, domain)
        
        if all_links["found"]:
            # 화면 중앙 영역에 있는 링크들 필터링
            visible_links = []
            for link in all_links["links"]:
                if visible_top <= link["centerY"] <= visible_bottom:
                    visible_links.append(link)
            
            # 화면에 보이는 링크가 있으면
            if visible_links:
                # 한번 더 랜덤 스크롤 (자연스럽게)
                extra_scroll = random.randint(50, 150) * random.choice([1, -1])
                do_touch_scroll(cdp, extra_scroll)
                time.sleep(random.uniform(0.3, 0.5))
                
                # 스크롤 후 다시 위치 확인
                all_links = get_all_domain_links(cdp, domain)
                visible_links = []
                for link in all_links["links"]:
                    if visible_top <= link["centerY"] <= visible_bottom:
                        visible_links.append(link)
                
                if visible_links:
                    print(f"[발견] {domain} 링크! 화면에 보이는 {len(visible_links)}개 링크")
                    
                    # 찾은 링크들 로그 (x, width 포함)
                    for i, link in enumerate(visible_links):
                        print(f"  링크{i+1}: x={link['x']:.0f}, y={link['y']:.0f}, w={link['width']:.0f}, h={link['height']:.0f}")
                        print(f"          href={link['href']}")
                    
                    # 클릭 전 URL 저장
                    before_url = get_current_url(cdp)
                    
                    # 최대 3회 클릭 시도
                    clicked_indices = []
                    for click_attempt in range(3):
                        # 아직 클릭 안 한 링크 중에서 선택
                        available_links = [link for i, link in enumerate(visible_links) if i not in clicked_indices]
                        if not available_links:
                            available_links = visible_links  # 다 시도했으면 다시 전체에서
                        
                        selected = random.choice(available_links)
                        selected_index = visible_links.index(selected)
                        clicked_indices.append(selected_index)
                        
                        time.sleep(random.uniform(0.3, 0.5))
                        
                        # 선택된 링크 영역 안에서 랜덤 좌표 클릭
                        x = selected["x"] + random.uniform(selected["width"] * 0.1, selected["width"] * 0.9)
                        y = selected["y"] + random.uniform(selected["height"] * 0.2, selected["height"] * 0.8)
                        
                        print(f"[클릭 시도 {click_attempt + 1}/3] 링크{selected_index+1} 선택, 좌표 x: {x:.1f}, y: {y:.1f}")
                        do_touch_click(cdp, x, y)
                        
                        # 3초 대기 후 URL 변경 확인
                        time.sleep(3)
                        after_url = get_current_url(cdp)
                        
                        if after_url != before_url:
                            print(f"[성공] 페이지 이동 확인!")
                            return True
                        else:
                            print(f"[재시도] URL 변경 없음, 다른 링크 시도...")
                    
                    # 3회 모두 실패
                    print(f"[실패] 3회 클릭 시도 모두 실패")
                    return False
            
            # 링크는 있지만 화면 밖 → 스크롤해서 이동
            first_link = all_links["links"][0]
            link_center_y = first_link["centerY"]
            
            # 스크롤 방향 결정
            if link_center_y > visible_bottom:
                scroll_distance = scroll_config["distance"] + random.uniform(-scroll_config["distance_random"], scroll_config["distance_random"])
            else:
                scroll_distance = -(scroll_config["distance"] + random.uniform(-scroll_config["distance_random"], scroll_config["distance_random"]))
            
            # 스크롤 전 위치
            before_scroll = get_scroll_position(cdp)
            do_touch_scroll(cdp, scroll_distance)
            time.sleep(0.1)
            # 스크롤 후 위치
            after_scroll = get_scroll_position(cdp)
            
            scroll_count += 1
        else:
            # 링크 없음 → 아래로 스크롤하면서 찾기
            # 스크롤 전 위치
            before_scroll = get_scroll_position(cdp)
            do_touch_scroll(cdp, scroll_config["distance"])
            time.sleep(0.1)
            # 스크롤 후 위치
            after_scroll = get_scroll_position(cdp)
            
            scroll_count += 1
        
        # 페이지 끝 감지: 스크롤 위치가 안 변했으면
        if abs(after_scroll - before_scroll) < 10:
            same_position_count += 1
            if same_position_count >= 2:
                print(f"[페이지 끝] 더 이상 스크롤 불가, 다음 페이지로...")
                return False
        else:
            same_position_count = 0
        
        # 랜덤 딜레이
        delay = scroll_config["delay"] + random.uniform(-scroll_config["delay_random"], scroll_config["delay_random"])
        time.sleep(delay)
        
        if scroll_count % 5 == 0:
            print(f"[스크롤] {scroll_count}회 검색 중...")
    
    print(f"[오류] {domain} 링크를 찾을 수 없음 (스크롤 {max_scrolls}회)")
    return False


def touch_click_element(cdp, selector=None, text=None, random_offset=True):
    """요소를 찾아서 터치 클릭"""
    bounds = get_element_bounds(cdp, selector=selector, text=text)
    
    if not bounds.get("found"):
        print(f"[오류] 요소를 찾을 수 없음: {selector or text}")
        return False
    
    if random_offset:
        # 요소 영역 안에서 랜덤 위치 클릭
        x = bounds["x"] + random.uniform(bounds["width"] * 0.2, bounds["width"] * 0.8)
        y = bounds["y"] + random.uniform(bounds["height"] * 0.2, bounds["height"] * 0.8)
    else:
        x = bounds["centerX"]
        y = bounds["centerY"]
    
    do_touch_click(cdp, int(x), int(y))
    return True

def get_target_position(cdp, target_text):
    """타겟 텍스트 위치 찾기"""
    js_code = f"""
    (function() {{
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        let node;
        while (node = walker.nextNode()) {{
            if (node.textContent.trim().includes("{target_text}")) {{
                const el = node.parentElement;
                const rect = el.getBoundingClientRect();
                return {{
                    found: true,
                    top: rect.top,
                    bottom: rect.bottom,
                    viewportHeight: window.innerHeight
                }};
            }}
        }}
        return {{ found: false }};
    }})()
    """
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    return result.get("result", {}).get("value", {"found": False})

def is_target_visible(position_info):
    """타겟이 화면에 보이는지 확인"""
    if not position_info.get("found"):
        return False
    
    top = position_info["top"]
    viewport_height = position_info["viewportHeight"]
    
    return 0 <= top <= viewport_height * 0.8

# ============================================
# 검색 프로세스 (1~7단계)
# ============================================
def run_search_process(cdp, search_keyword, target_domain, search_in_total, go_to_more=True, start_mode="new", is_last=False):
    """
    검색 프로세스 1~7단계 실행
    
    Args:
        start_mode: "new"=네이버 메인부터, "continue"=현재 페이지에서 검색
    
    Returns:
        "DONE": 성공
        "RETRY": 재시도 필요 (검색창 클릭 실패, 검색 결과 대기 실패 등)
        "ERROR": 페이지 오류 → 종료
        "NOTFOUND": 도메인 못 찾음 → 종료
    """
    viewport = CONFIG["viewport"]
    
    # ========================================
    # 1단계: 네이버 이동 (start_mode에 따라)
    # ========================================
    if start_mode == "new":
        print("\n[1단계] 네이버 모바일 메인 이동...")
        cdp.navigate(CONFIG["naver_mobile_url"])
        
        # 페이지 로딩 완료 대기 (무조건 10초)
        print("[대기] 페이지 로딩 대기 10초...")
        time.sleep(10)
        print("[로딩 완료]")
    else:
        print("\n[1단계] continue 모드 - 현재 페이지에서 시작")
        time.sleep(random.uniform(0.3, 0.5))
    
    # ========================================
    # 2단계: 검색창 터치 클릭
    # ========================================
    print("\n[2단계] 검색창 터치...")
    
    # continue 모드일 때는 검색창 selector가 다름 (더보기 페이지 = nx_query)
    if start_mode == "continue":
        # 더보기 페이지 검색창 (nx_query) + 통합 페이지 검색창 (query) 둘 다 시도
        search_selectors = CONFIG["selectors"]["search_more"] + CONFIG["selectors"]["search_real"]
    else:
        search_selectors = CONFIG["selectors"]["search_fake"]
    
    click_retry = 0
    max_click_retry = CONFIG["retry"]["max_element_retry"]
    clicks_before_reload = 5
    
    # 검색창 초기 위치 (두 가지 모두 체크)
    initial_query_pos = get_element_bounds(cdp, selector="input#query")
    if not initial_query_pos.get("found"):
        initial_query_pos = get_element_bounds(cdp, selector="input#nx_query")
    initial_y = initial_query_pos.get("centerY", -999) if initial_query_pos.get("found") else -999
    
    search_mode_success = False
    
    while click_retry < max_click_retry:
        click_retry += 1
        
        # 5번마다 메인 재이동 (continue 모드에서도)
        if click_retry > 1 and (click_retry - 1) % clicks_before_reload == 0:
            print(f"[재이동] {clicks_before_reload}번 시도 실패, 네이버 메인으로 다시 이동...")
            cdp.navigate(CONFIG["naver_mobile_url"])
            
            reload_delay = CONFIG["retry"]["after_refresh_delay"]
            print(f"[대기] 페이지 로드 {reload_delay}초 대기...")
            time.sleep(reload_delay)
            
            initial_query_pos = get_element_bounds(cdp, selector="input#query")
            initial_y = initial_query_pos.get("centerY", -999) if initial_query_pos.get("found") else -999
            search_selectors = CONFIG["selectors"]["search_fake"]  # 메인으로 갔으니 fake로 변경
        
        # 페이지 오류 체크
        if check_page_error(cdp):
            print("[오류] 페이지 오류 감지!")
            return "ERROR"
        
        # 검색창 찾기
        wait_result = wait_for_element(cdp, search_selectors, timeout=3, after_delay=False)
        
        if not wait_result["found"]:
            print(f"[재시도 {click_retry}/{max_click_retry}] 검색창을 찾을 수 없음")
            time.sleep(0.5)
            continue
        
        bounds = wait_result["bounds"]
        
        if bounds["centerY"] < 0 or bounds["centerY"] > viewport["height"]:
            print(f"[재시도 {click_retry}/{max_click_retry}] 검색창이 화면 밖에 있음")
            time.sleep(0.5)
            continue
        
        click_x = bounds["centerX"] + random.uniform(-bounds["width"]*0.3, bounds["width"]*0.3)
        click_y = bounds["centerY"] + random.uniform(-bounds["height"]*0.2, bounds["height"]*0.2)
        do_touch_click(cdp, click_x, click_y)
        
        print(f"[클릭 {click_retry}/{max_click_retry}] 검색창 클릭, 결과 확인 중...")
        time.sleep(0.5)
        
        # continue 모드일 때는 검색창 활성화 체크 방식이 다름
        if start_mode == "continue":
            # 더보기 페이지는 nx_query, 통합은 query
            new_query_pos = get_element_bounds(cdp, selector="input#nx_query")
            if not new_query_pos.get("found"):
                new_query_pos = get_element_bounds(cdp, selector="input#query")
            
            if new_query_pos.get("found"):
                print(f"[성공] 검색창 활성화됨!")
                search_mode_success = True
                break
        else:
            new_query_pos = get_element_bounds(cdp, selector="input#query")
            
            if new_query_pos.get("found"):
                new_y = new_query_pos["centerY"]
                
                if new_y != initial_y and 0 <= new_y <= viewport["height"]:
                    print(f"[성공] 검색 모드 전환됨!")
                    click_x = new_query_pos["centerX"] + random.uniform(-new_query_pos["width"]*0.3, new_query_pos["width"]*0.3)
                    click_y = new_query_pos["centerY"] + random.uniform(-new_query_pos["height"]*0.2, new_query_pos["height"]*0.2)
                    do_touch_click(cdp, click_x, click_y)
                    search_mode_success = True
                    break
                else:
                    print(f"[대기 {click_retry}] 아직 로딩 중...")
                    time.sleep(0.5)
            else:
                print(f"[재시도 {click_retry}/{max_click_retry}] input#query를 찾을 수 없음")
            time.sleep(0.5)
    
    if not search_mode_success:
        print(f"[실패] 검색창 클릭 {max_click_retry}번 실패")
        return "RETRY"
    
    time.sleep(random.uniform(0.3, 0.5))
    
    # ========================================
    # 3단계: 검색어 입력
    # ========================================
    print(f"\n[3단계] 검색어 입력: {search_keyword}")
    
    # continue 모드일 때 기존 텍스트 삭제 (트리플 터치로 전체선택)
    if start_mode == "continue":
        print("[검색창 초기화] 트리플 터치로 전체 선택...")
        
        # 검색창 위치 가져오기
        search_bounds = get_element_bounds(cdp, selector="input#nx_query")
        if not search_bounds.get("found"):
            search_bounds = get_element_bounds(cdp, selector="input#query")
        
        if search_bounds.get("found"):
            select_x = search_bounds["centerX"]
            select_y = search_bounds["centerY"]
            
            max_select_retry = 5
            select_success = False
            
            for select_try in range(1, max_select_retry + 1):
                # 트리플 터치
                do_triple_touch(cdp, select_x, select_y)
                time.sleep(0.3)
                
                # 선택 확인
                if check_text_selected(cdp):
                    print(f"[선택 성공] 텍스트 선택됨!")
                    select_success = True
                    break
                else:
                    print(f"[선택 실패 {select_try}/{max_select_retry}] 텍스트 선택 안 됨")
                    time.sleep(0.3)
            
            # 5번 실패 시 일시정지
            if not select_success:
                print("\033[91m" + "=" * 50 + "\033[0m")
                print("\033[91m[오류] 검색창 텍스트 선택 5번 실패!\033[0m")
                print("\033[91m[오류] 수동으로 확인 필요\033[0m")
                print("\033[91m" + "=" * 50 + "\033[0m")
                input("[일시정지] Enter 누르면 계속...")
        
        time.sleep(0.1)
    
    cdp.type_text(search_keyword)
    time.sleep(random.uniform(0.3, 0.5))
    
    # ========================================
    # 4단계: 검색 실행
    # ========================================
    search_mode = CONFIG["search_mode"]
    if search_mode == 3:
        search_mode = random.choice([1, 2])
    
    mode_name = "엔터" if search_mode == 1 else "돋보기"
    print(f"\n[4단계] 검색 실행... (모드: {mode_name})")
    
    if search_mode == 1:
        cdp.press_enter()
    else:
        btn_selectors = CONFIG["selectors"]["search_button"]
        btn_clicked = False
        for selector in btn_selectors:
            bounds = get_element_bounds(cdp, selector=selector)
            if bounds.get("found"):
                click_x = bounds["centerX"] + random.uniform(-5, 5)
                click_y = bounds["centerY"] + random.uniform(-3, 3)
                do_touch_click(cdp, click_x, click_y)
                btn_clicked = True
                break
        
        if not btn_clicked:
            cdp.press_enter()
    
    # 검색 결과 대기 (메인 이동 없이 단순 대기)
    print("[대기] 검색 결과 요소 대기...")
    result_selectors = CONFIG["selectors"]["search_result"]
    
    # 1차 시도: 검색 결과 대기
    wait_result = wait_for_element(cdp, result_selectors, timeout=10, after_delay=True)
    
    if not wait_result["found"]:
        # 1차 실패 → 엔터로 재시도
        print("[재시도] 검색 결과 없음, 엔터로 재검색...")
        cdp.press_enter()
        time.sleep(2)
        
        # 2차 시도
        wait_result = wait_for_element(cdp, result_selectors, timeout=10, after_delay=True)
        
        if not wait_result["found"]:
            # 2차 실패 → ERROR
            print("[실패] 검색 결과를 찾을 수 없음")
            return "ERROR"
    
    # ========================================
    # 4.5단계: 통합 페이지에서 먼저 찾기 (옵션)
    # ========================================
    if search_in_total:
        print(f"\n[4.5단계] 통합 페이지에서 '{target_domain}' 웹사이트 영역 찾기...")
        
        if click_web_domain_link(cdp, target_domain):
            print(f"[성공] 통합 페이지에서 {target_domain} 클릭 완료!")
            
            # === 8단계: 타겟 사이트 체류 ===
            print("\n[8단계] 타겟 사이트 체류 중...")
            
            # 체류 시간 (10~20초)
            stay_time = random.uniform(CONFIG["stay_min"], CONFIG["stay_max"])
            print(f"[체류] {stay_time:.1f}초 대기...")
            time.sleep(stay_time)
            
            # 마지막 키워드가 아니면 뒤로가기
            if not is_last:
                print("\n[9단계] 뒤로가기로 검색 페이지 복귀...")
                do_history_back(cdp)
                time.sleep(random.uniform(1.0, 2.0))
                print("[복귀 완료] 검색 결과 페이지로 돌아옴")
            else:
                print("\n[9단계] 마지막 키워드 - 뒤로가기 생략")
            
            return "DONE"
        
        if go_to_more:
            print(f"[결과] 통합 페이지에 {target_domain} 없음, 더보기로 이동...")
        else:
            print(f"[결과] 통합 페이지에 {target_domain} 없음 (더보기 이동 OFF)")
            return "NOTFOUND"
    
    # 더보기로 이동 안 하는 경우
    if not go_to_more:
        print(f"[종료] go_to_more=False, 더보기 이동 안 함")
        return "NOTFOUND"
    
    # ========================================
    # 5단계: 검색결과 더보기까지 스크롤
    # ========================================
    print(f"\n[5단계] '{CONFIG['target_text']}' 까지 스크롤...")
    
    step5_full_retry = CONFIG["retry"]["step5_full_retry"]
    step5_success = False
    
    for step5_round in range(step5_full_retry + 1):  # 0, 1 (1회 재시도면 총 2번)
        if step5_round > 0:
            print(f"\n[5단계 재시도 {step5_round}/{step5_full_retry}] 처음부터 다시 시도 필요...")
            return "RETRY"  # 1단계부터 다시
        
        position = None
        for find_attempt in range(5):
            position = get_target_position(cdp, CONFIG["target_text"])
            if position.get("found"):
                break
            time.sleep(0.5)
        
        if not position or not position.get("found"):
            print(f"[5단계] 타겟 텍스트를 찾을 수 없음")
            continue
        
        scroll_count = 0
        max_scrolls = CONFIG["max_scrolls"]
        
        while not is_target_visible(position) and scroll_count < max_scrolls:
            if position["top"] < 0:
                do_touch_scroll(cdp, -CONFIG["scroll"]["distance"])
            else:
                do_touch_scroll(cdp, CONFIG["scroll"]["distance"])
            
            scroll_count += 1
            
            delay = CONFIG["scroll"]["delay"]
            delay_random = CONFIG["scroll"]["delay_random"]
            time.sleep(delay + random.uniform(-delay_random, delay_random))
            
            position = get_target_position(cdp, CONFIG["target_text"])
        
        if scroll_count >= max_scrolls:
            print(f"[5단계] 최대 스크롤 도달, 타겟 못 찾음")
            continue
        
        step5_success = True
        break
    
    if not step5_success:
        print(f"[오류] 5단계 실패")
        return "NOTFOUND"
    
    # ========================================
    # 6단계: 검색결과 더보기 클릭
    # ========================================
    print(f"\n[6단계] '{CONFIG['target_text']}' 클릭...")
    
    step6_click_retry = CONFIG["retry"]["step6_click_retry"]
    page_load_config = CONFIG["page_load"]
    step6_success = False
    
    # 클릭 전 URL 저장
    before_url = get_current_url(cdp)
    
    # 더보기 발견 후 잠깐 대기 (스크롤 안정화)
    print(f"[6단계] 클릭 전 안정화 대기...")
    time.sleep(random.uniform(0.5, 1.0))
    
    for click_try in range(1, step6_click_retry + 1):
        time.sleep(random.uniform(0.3, 0.6))
        
        if touch_click_element(cdp, text=CONFIG["target_text"], random_offset=True):
            print(f"[6단계] 클릭 시도 {click_try}, 페이지 로딩 대기...")
            
            # 10초 단위로 체크하면서 재클릭
            reclick_interval = 10  # 10초마다 재클릭 시도
            max_reclick = 5  # 최대 5번 재클릭 (총 50초)
            
            for reclick_try in range(max_reclick):
                # 10초 대기하면서 URL 변경 체크
                for _ in range(20):  # 0.5초 * 20 = 10초
                    current_url = get_current_url(cdp)
                    if current_url != before_url and is_page_loaded(cdp):
                        print(f"[6단계] 페이지 로딩 완료!")
                        # 로딩 완료 후 대기
                        after_load_delay = random.uniform(
                            page_load_config["after_load_min"],
                            page_load_config["after_load_max"]
                        )
                        print(f"[로딩 후 대기] {after_load_delay:.1f}초...")
                        time.sleep(after_load_delay)
                        step6_success = True
                        break
                    time.sleep(0.5)
                
                if step6_success:
                    break
                
                # URL 안 바뀌면 재클릭
                if reclick_try < max_reclick - 1:
                    print(f"[6단계] URL 변경 없음, 재클릭 시도 {reclick_try + 2}/{max_reclick}...")
                    touch_click_element(cdp, text=CONFIG["target_text"], random_offset=True)
            
            if step6_success:
                break
            else:
                print(f"[6단계] 페이지 로딩 타임아웃 (50초)")
                if page_load_config["retry_count"] > 0:
                    print(f"[6단계] 처음부터 재시도...")
                    return "RETRY"
                else:
                    return "ERROR"
        
        if click_try < step6_click_retry:
            print(f"[6단계 클릭 {click_try}/{step6_click_retry}] 클릭 실패, 다시 시도...")
    
    if not step6_success:
        print(f"[오류] 6단계 실패 (클릭 {step6_click_retry}번)")
        return "NOTFOUND"
    
    # ========================================
    # 7단계: 타겟 도메인 찾아서 클릭
    # ========================================
    print(f"\n[7단계] '{target_domain}' 사이트 찾기...")
    
    start_page = 2
    max_page = 10
    domain_found = False
    
    for page_num in range(start_page, max_page + 1):
        print(f"[탐색] {page_num}페이지 검색 중...")
        
        if click_domain_link(cdp, target_domain):
            domain_found = True
            print(f"[성공] {target_domain} 클릭 완료!")
            break
        
        if page_num < max_page:
            next_page = page_num + 1
            print(f"[이동] {next_page}페이지로 이동...")
            
            visible_top = viewport["height"] * 0.2
            visible_bottom = viewport["height"] * 0.8
            
            page_btn_found = False
            scroll_try = 0
            max_scroll_try = 15
            
            while scroll_try < max_scroll_try:
                js_code = f"""
                (function() {{
                    const links = document.querySelectorAll('a');
                    for (let link of links) {{
                        if (link.textContent.trim() === '{next_page}') {{
                            const rect = link.getBoundingClientRect();
                            if (rect.height > 0 && rect.width > 0) {{
                                return {{
                                    found: true,
                                    centerX: rect.left + rect.width / 2,
                                    centerY: rect.top + rect.height / 2
                                }};
                            }}
                        }}
                    }}
                    return {{ found: false }};
                }})()
                """
                result = cdp.send("Runtime.evaluate", {
                    "expression": js_code,
                    "returnByValue": True
                })
                bounds = result.get("result", {}).get("value", {"found": False})
                
                if bounds.get("found"):
                    btn_center_y = bounds["centerY"]
                    
                    if visible_top <= btn_center_y <= visible_bottom:
                        click_x = bounds["centerX"] + random.uniform(-3, 3)
                        click_y = bounds["centerY"] + random.uniform(-2, 2)
                        do_touch_click(cdp, click_x, click_y)
                        page_btn_found = True
                        time.sleep(random.uniform(1.5, 2.0))
                        break
                    else:
                        if btn_center_y > visible_bottom:
                            do_touch_scroll(cdp, CONFIG["scroll"]["distance"])
                        else:
                            do_touch_scroll(cdp, -CONFIG["scroll"]["distance"])
                        scroll_try += 1
                        time.sleep(0.2)
                else:
                    do_touch_scroll(cdp, CONFIG["scroll"]["distance"])
                    scroll_try += 1
                    time.sleep(0.2)
            
            if not page_btn_found:
                break
    
    if domain_found:
        # ========================================
        # 8단계: 타겟 사이트 체류
        # ========================================
        print("\n[8단계] 타겟 사이트 체류 중...")
        
        # 체류 시간 (10~20초)
        stay_time = random.uniform(CONFIG["stay_min"], CONFIG["stay_max"])
        print(f"[체류] {stay_time:.1f}초 대기...")
        time.sleep(stay_time)
        
        # 마지막 키워드가 아니면 뒤로가기
        if not is_last:
            # 뒤로가기로 검색 결과 페이지 복귀
            print("\n[9단계] 뒤로가기로 검색 페이지 복귀...")
            do_history_back(cdp)
            
            # 페이지 로딩 대기
            time.sleep(random.uniform(1.0, 2.0))
            print("[복귀 완료] 검색 결과 페이지로 돌아옴")
        else:
            print("\n[9단계] 마지막 키워드 - 뒤로가기 생략")
        
        return "DONE"
    else:
        return "NOTFOUND"


# ============================================
# 메인
# ============================================
def main():
    if len(sys.argv) < 3:
        print("사용법: python cdp_touch_scroll.py 검색어 도메인 [검색모드] [시작모드] [마지막]")
        print("예시: python cdp_touch_scroll.py 곤지암스키강습 sidecut.co.kr")
        print("예시: python cdp_touch_scroll.py 곤지암스키강습 sidecut.co.kr total  (통합에서만)")
        print("예시: python cdp_touch_scroll.py 곤지암스키강습 sidecut.co.kr more   (더보기에서)")
        print("예시: python cdp_touch_scroll.py 곤지암스키강습 sidecut.co.kr more auto  (자동감지)")
        print("예시: python cdp_touch_scroll.py 곤지암스키강습 sidecut.co.kr more auto 1  (마지막 키워드)")
        print("")
        print("[검색모드] total=통합에서만 찾기, more=더보기에서 찾기, both=통합먼저→더보기 (기본값)")
        print("[시작모드] new=네이버 메인부터, continue=현재페이지에서, auto=자동감지 (기본값)")
        print("[마지막] 0=중간 키워드, 1=마지막 키워드 (뒤로가기 안 함)")
        return
    
    search_keyword = sys.argv[1]
    target_domain = sys.argv[2]
    
    # 검색 모드: total / more / both
    if len(sys.argv) >= 4:
        search_mode_param = sys.argv[3].lower()
        if search_mode_param == "total":
            search_in_total = True
            go_to_more = False
        elif search_mode_param == "more":
            search_in_total = False
            go_to_more = True
        else:  # both (기본값)
            search_in_total = True
            go_to_more = True
    else:
        search_in_total = CONFIG["search_in_total_first"]
        go_to_more = True
    
    # 시작 모드: new / continue / auto
    if len(sys.argv) >= 5:
        start_mode = sys.argv[4].lower()
    else:
        start_mode = "auto"
    
    # 마지막 키워드 여부
    if len(sys.argv) >= 6:
        is_last = sys.argv[5] in ["1", "true", "True", "yes", "Y", "last"]
    else:
        is_last = False
    
    max_full_retry = CONFIG["retry"]["max_full_retry"]
    
    print("========================================")
    print("[CDP 네이버 모바일 검색]")
    print(f"[검색어] {search_keyword}")
    print(f"[타겟 도메인] {target_domain}")
    print(f"[검색 모드] 통합:{search_in_total}, 더보기:{go_to_more}")
    print(f"[시작 모드] {start_mode}")
    print(f"[마지막 키워드] {'YES' if is_last else 'NO'}")
    print(f"[전체 재시도] 최대 {max_full_retry}회")
    print("========================================")
    
    ws_url = get_websocket_url()
    if not ws_url:
        save_result(CONFIG["not_found_value"])
        return
    
    print(f"[연결] {ws_url[:50]}...")
    
    cdp = CDP(ws_url)
    
    # 모바일 에뮬레이션 설정 (핵심!)
    mobile_config = CONFIG.get("mobile_emulation", {})
    
    # UA 파일에서 확률 기반 랜덤 선택
    browser_type, ua = select_random_ua_from_files()
    
    if not ua:
        # UA 파일 로드 실패 시 기본값 사용
        print("[경고] UA 파일 로드 실패, 기본 Chrome UA 사용")
        browser_type = "chrome"
        ua = MOBILE_CONFIG["browser_uas"]["chrome"]
    
    setup_mobile_emulation(
        cdp, 
        ua,
        browser_type=browser_type,
        model=mobile_config.get("model"),
        preset=mobile_config.get("preset"),
        platform_version=mobile_config.get("platform_version")
    )
    
    try:
        # 시작 모드 자동 감지
        if start_mode == "auto":
            current_url = get_current_url(cdp)
            if "search.naver.com" in current_url:
                start_mode = "continue"
                print(f"[자동감지] 네이버 검색 페이지 → continue 모드")
            else:
                start_mode = "new"
                print(f"[자동감지] 네이버 아님 → new 모드")
        
        for full_retry in range(max_full_retry):
            if full_retry > 0:
                print(f"\n{'='*50}")
                print(f"[전체 재시도] {full_retry + 1}/{max_full_retry}회차 - 처음부터 다시 시작")
                print(f"{'='*50}")
                start_mode = "new"  # 재시도 시에는 처음부터
            
            result = run_search_process(cdp, search_keyword, target_domain, search_in_total, go_to_more, start_mode, is_last)
            
            if result == "DONE":
                save_result(CONFIG["done_value"])
                print("\n========================================")
                print("[완료] 모든 작업 완료!")
                print("========================================")
                return
            
            elif result == "ERROR":
                save_result(CONFIG["error_value"])
                print("\n[종료] 페이지 오류")
                return
            
            elif result == "NOTFOUND":
                save_result(CONFIG["not_found_value"])
                print("\n[종료] 도메인을 찾을 수 없음")
                return
            
            elif result == "RETRY":
                if full_retry < max_full_retry - 1:
                    print(f"\n[대기] 3초 후 재시도...")
                    time.sleep(3)
                else:
                    print(f"\n[종료] 전체 재시도 {max_full_retry}회 모두 실패")
                    save_result(CONFIG["not_found_value"])
                    return
    
    except Exception as e:
        print(f"\n[예외 발생] {e}")
        save_result(CONFIG["error_value"])
    
    finally:
        # 브라우저 종료 옵션이 켜져 있으면 브라우저 종료
        if CONFIG.get("close_browser_on_finish", False):
            try:
                print("\n[브라우저 종료] 크롬 브라우저를 종료합니다...")
                cdp.send("Browser.close")
            except:
                pass
        cdp.close()


if __name__ == "__main__":
    main()