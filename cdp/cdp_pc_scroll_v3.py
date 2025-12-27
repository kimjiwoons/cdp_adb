# ============================================
# CDP를 이용한 네이버 PC 검색 자동화 v2
# 크롬 디버깅 모드 필요: --remote-debugging-port=9222 --remote-allow-origins=*
# 
# 사용법: python cdp_pc_scroll_v2.py 검색어 도메인 [검색모드] [시작모드] [마지막]
# 
# v2: fingerprint 스푸핑 + UA 파일 로드 지원 (Chrome/Edge/Opera/Firefox)
# ============================================

import json
import time
import random
import sys
import os
import re
import glob
import requests
import websocket
import pyperclip

# ============================================
# ★★★ 랜덤 옵션 설정 (여기서 조절) ★★★
# ============================================
RANDOM_OPTIONS = {
    # ──────────────────────────────────────────
    # 브라우저 선택 가중치
    # ──────────────────────────────────────────
    # 순서: [Chrome, Edge, Opera, Firefox]
    # 예시:
    #   [50, 25, 15, 10] = 일반적인 분포
    #   [100, 0, 0, 0]   = Chrome만
    #   [0, 0, 0, 100]   = Firefox만
    "browser_weights": [60, 15, 15, 10],
    
    # ──────────────────────────────────────────
    # 체류 시간 설정 (초)
    # ──────────────────────────────────────────
    # 타겟 사이트 도착 후 체류 시간
    # stay_min ~ stay_max 사이에서 랜덤 선택
    "stay_min": 10,   # 최소 체류 시간 (초)
    "stay_max": 20,   # 최대 체류 시간 (초)
    
    # ──────────────────────────────────────────
    # 작업 완료 후 브라우저 종료
    # ──────────────────────────────────────────
    # True: 작업 완료 후 크롬 브라우저 종료
    # False: 브라우저 유지
    "close_browser_on_finish": True,
    
    # ──────────────────────────────────────────
    # 해상도 선택 가중치
    # ──────────────────────────────────────────
    # PC_PRESETS 순서:
    #   0: 1920x1080 DPR 1.0   (FHD 100%)      ★ DPR 1.0
    #   1: 1920x1080 DPR 1.25  (FHD 125%)
    #   2: 1536x864  DPR 1.25  (노트북)
    #   3: 1366x768  DPR 1.0   (저가 노트북)   ★ DPR 1.0
    #   4: 1440x900  DPR 1.0   (16:10)         ★ DPR 1.0
    #   5: 1600x900  DPR 1.0   (16:9)          ★ DPR 1.0
    #   6: 2560x1440 DPR 1.0   (QHD 100%)      ★ DPR 1.0
    #   7: 2560x1440 DPR 1.25  (QHD 125%)
    #   8: 3840x2160 DPR 1.0   (4K 100%)       ★ DPR 1.0
    #   9: 1920x1200 DPR 1.0   (16:10)         ★ DPR 1.0
    #  10: 1680x1050 DPR 1.0   (16:10)         ★ DPR 1.0
    #  11: 2560x1080 DPR 1.0   (울트라와이드)   ★ DPR 1.0
    #  12: 3440x1440 DPR 1.0   (울트라와이드)   ★ DPR 1.0
    #  13: 1280x1024 DPR 1.0   (5:4)           ★ DPR 1.0
    #  14: 1280x720  DPR 1.0   (HD)            ★ DPR 1.0
    #  15: 1360x768  DPR 1.0   (저가형)        ★ DPR 1.0
    #
    # ※ DPR 1.5 이상 제거됨 (화면 깨짐 방지)
    # ※ 고해상도(1920x1080 초과)는 창 크기 1920x1080 이하로 자동 제한
    #
    # DPR 1.0 많이 나오게 하려면: ★ 표시된 인덱스 가중치 높이기
    #                      0   1  2  3  4  5   6  7  8  9 10 11 12 13 14 15
    "resolution_weights": [30, 8, 5, 5, 3, 3, 12, 4, 6, 3, 2, 3, 3, 2, 2, 2],
    
    # ──────────────────────────────────────────
    # 창 타입 가중치
    # ──────────────────────────────────────────
    # 브라우저 창 크기 결정
    # 순서: [fullscreen, large, half, custom]
    #   fullscreen: 전체화면 (F11 또는 최대화)
    #   large:      80~95% 크기 (거의 전체화면)
    #   half:       화면 절반 (좌우 분할 작업)
    #   custom:     60~80% 랜덤 크기
    "window_type_weights": [45, 25, 18, 12],
    
    # ──────────────────────────────────────────
    # 메모리 옵션 (GB)
    # ──────────────────────────────────────────
    # deviceMemory API 값 (랜덤 선택)
    # 일반 PC: 8~16GB, 고사양: 32~64GB
    # 중복 입력하면 해당 값 선택 확률 높아짐
    "memory_options": [4, 8, 8, 16, 16, 32, 64],
}

# ============================================
# 버전 매핑 (UA fullVersionList용)
# ============================================
CHROME_VERSION_MAP = {
    "132": {"build": "6834", "patches": ["83", "110", "159", "194"]},
    "133": {"build": "6943", "patches": ["53", "98", "126", "141", "142"]},
    "134": {"build": "6998", "patches": ["35", "88", "117", "166"]},
    "135": {"build": "7049", "patches": ["42", "84", "95", "115"]},
    "136": {"build": "7103", "patches": ["49", "92", "113", "114", "127"]},
    "137": {"build": "7151", "patches": ["41", "55", "68", "104"]},
    "138": {"build": "7204", "patches": ["49", "93", "157", "179", "183", "184"]},
    "139": {"build": "7258", "patches": ["66", "67", "128", "138", "139", "143"]},
    "140": {"build": "7339", "patches": ["80", "81", "124", "154", "207", "208"]},
    "141": {"build": "7390", "patches": ["43", "55", "65", "70", "112", "123", "125"]},
    "142": {"build": "7444", "patches": ["59", "91", "135", "138", "158", "171", "176"]},
    "143": {"build": "7499", "patches": ["40", "41", "52", "92", "110", "147"]},
}

OPERA_VERSION_MAP = {
    "115": {"build": "5322", "patches": ["68", "94", "109", "119"]},
    "116": {"build": "5366", "patches": ["127"]},
    "117": {"build": "5408", "patches": ["197"]},
    "118": {"build": "5461", "patches": ["104"]},
    "119": {"build": "5497", "patches": ["141"]},
    "120": {"build": "5543", "patches": ["38", "61", "93", "128", "161", "201"]},
    "121": {"build": "5600", "patches": ["20", "38", "50"]},
    "122": {"build": "5643", "patches": ["17", "24", "51", "71", "92", "142"]},
    "123": {"build": "5669", "patches": ["23", "47"]},
    "124": {"build": "5705", "patches": ["15", "42", "65"]},
    "125": {"build": "5729", "patches": ["12", "15", "21", "49"]},
}

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
}

def get_chrome_full_version(major_version):
    """Chrome 메이저 버전 → 상세 버전 변환"""
    major = str(major_version).split(".")[0]
    if major in CHROME_VERSION_MAP:
        info = CHROME_VERSION_MAP[major]
        patch = random.choice(info["patches"])
        return f"{major}.0.{info['build']}.{patch}"
    return f"{major}.0.0.0"

def get_opera_full_version(major_version):
    """Opera 메이저 버전 → 상세 버전 변환"""
    major = str(major_version).split(".")[0]
    if major in OPERA_VERSION_MAP:
        info = OPERA_VERSION_MAP[major]
        patch = random.choice(info["patches"])
        return f"{major}.0.{info['build']}.{patch}"
    return f"{major}.0.0.0"

def get_edge_full_version(major_version):
    """Edge 메이저 버전 → 상세 버전 변환"""
    major = str(major_version).split(".")[0]
    if major in EDGE_VERSION_MAP:
        info = EDGE_VERSION_MAP[major]
        patch = random.choice(info["patches"])
        return f"{major}.0.{info['build']}.{patch}"
    return f"{major}.0.0.0"

# ============================================
# PC 해상도 프리셋
# ============================================
PC_PRESETS = [
    # FHD (1920x1080) - 가장 흔함
    {"screen": "1920x1080", "dpr": 1.0},   # 0: FHD 100%
    {"screen": "1920x1080", "dpr": 1.25},  # 1: FHD 125%
    # 노트북
    {"screen": "1536x864", "dpr": 1.25},   # 2: 노트북 흔함
    {"screen": "1366x768", "dpr": 1.0},    # 3: 저가 노트북
    # 16:10, 16:9
    {"screen": "1440x900", "dpr": 1.0},    # 4: 16:10
    {"screen": "1600x900", "dpr": 1.0},    # 5: 16:9
    # QHD (2560x1440)
    {"screen": "2560x1440", "dpr": 1.0},   # 6: QHD 100%
    {"screen": "2560x1440", "dpr": 1.25},  # 7: QHD 125%
    # 4K (3840x2160) - DPR 1.0만
    {"screen": "3840x2160", "dpr": 1.0},   # 8: 4K 100%
    # 기타 16:10
    {"screen": "1920x1200", "dpr": 1.0},   # 9: 16:10
    {"screen": "1680x1050", "dpr": 1.0},   # 10: 16:10
    # 울트라와이드 21:9
    {"screen": "2560x1080", "dpr": 1.0},   # 11: 울트라와이드
    {"screen": "3440x1440", "dpr": 1.0},   # 12: 울트라와이드 QHD
    # 구형/저가
    {"screen": "1280x1024", "dpr": 1.0},   # 13: 5:4 비율
    {"screen": "1280x720", "dpr": 1.0},    # 14: HD
    {"screen": "1360x768", "dpr": 1.0},    # 15: 저가형
]

def select_random_preset():
    """가중치 기반 랜덤 해상도 선택"""
    weights = RANDOM_OPTIONS["resolution_weights"]
    return random.choices(PC_PRESETS, weights=weights)[0]

def calc_inner_size(screen_w, screen_h):
    """브라우저 inner 크기 계산"""
    
    # 고해상도(1920x1080 초과)는 전체화면 제외
    if screen_w > 1920 or screen_h > 1080:
        window_type = random.choices(
            ["large", "half", "custom"],
            weights=[35, 40, 25]  # 절반 사용이 가장 흔함
        )[0]
    else:
        window_type = random.choices(
            ["fullscreen", "large", "half", "custom"],
            weights=RANDOM_OPTIONS["window_type_weights"]
        )[0]
    
    taskbar = random.randint(40, 50)
    browser_top = random.randint(80, 140)
    
    if window_type == "fullscreen":
        # 전체화면 (1920x1080 이하만)
        inner_w = screen_w
        inner_h = screen_h - taskbar - browser_top
    elif window_type == "large":
        # 거의 전체화면 (80~95%)
        ratio = random.uniform(0.80, 0.95)
        inner_w = int(screen_w * ratio)
        inner_h = int((screen_h - taskbar) * ratio) - browser_top
        # 고해상도면 1920x1080 이하로 제한
        if screen_w > 1920:
            inner_w = min(inner_w, random.randint(1600, 1920))
        if screen_h > 1080:
            inner_h = min(inner_h, random.randint(900, 1000))
    elif window_type == "half":
        # 화면 절반
        inner_w = screen_w // 2
        inner_h = screen_h - taskbar - browser_top
        # 고해상도 절반도 너무 크면 제한
        if inner_w > 1920:
            inner_w = random.randint(1400, 1920)
        if inner_h > 1080:
            inner_h = random.randint(900, 1000)
    else:
        # 커스텀 (60~80%)
        ratio_w = random.uniform(0.6, 0.8)
        ratio_h = random.uniform(0.6, 0.8)
        inner_w = int(screen_w * ratio_w)
        inner_h = int((screen_h - taskbar) * ratio_h) - browser_top
        # 고해상도면 제한
        if inner_w > 1920:
            inner_w = random.randint(1200, 1800)
        if inner_h > 1080:
            inner_h = random.randint(700, 950)
    
    return inner_w, inner_h, window_type

# ============================================
# 설정
# ============================================
CONFIG = {
    # 크롬 디버깅 포트
    "chrome_port": 9222,
    
    # 네이버 PC 검색 URL
    "naver_url": "https://www.naver.com",
    
    # 찾을 텍스트
    "target_text": "검색결과 더보기",
    
    # 검색 실행 모드: 1=엔터, 2=돋보기 클릭, 3=랜덤
    "search_mode": 3,
    
    # 통합 페이지에서 먼저 찾기: True=통합에서 먼저 찾고 없으면 더보기, False=바로 더보기
    "search_in_total_first": True,
    
    # 브라우저 창 크기 (PC)
    "viewport": {
        "width": 1024,
        "height": 768
    },
    
    # 마우스 스크롤 설정
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
    
    # 마우스 좌표 랜덤 범위
    "mouse_random": {
        "x_range": 50,
        "y_range": 30
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
        # 검색창 (메인/통합)
        "search_input": ["input#query", "#query", "input.search_input"],
        # 더보기 페이지 검색창 (continue 모드용)
        "search_more": ["input#nx_query", "#nx_query"],
        # 검색 버튼 (돋보기) - 메인/통합 페이지용
        "search_button": ["button.btn_search", "button[type='submit'].btn_search", "#search-btn", "svg#search-btn", "button[type='submit']"],
        # 검색 버튼 (돋보기) - 더보기 페이지용 (continue 모드)
        "search_button_more": ["button.bt_search", ".bt_search", "button.btn_search", "#nx_search_form button[type='submit']", "button[type='submit']"],
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
    
    # UA 파일 경로
    "ua_folder": "C:\\exload\\python\\ua_lists\\pc",
}


# ============================================
# UA 파일 로드
# ============================================
def load_ua_from_file(browser_type="random"):
    """
    UA 파일에서 랜덤 UA 로드
    
    Args:
        browser_type: "chrome", "edge", "opera", "firefox", "random"
    
    Returns:
        (browser_name, ua_string) or (None, None)
    """
    ua_folder = CONFIG.get("ua_folder", ".")
    
    ua_files = {
        "chrome": ["Chrome_pc.txt", "chrome_pc.txt", "pc_chrome_ua.txt"],
        "edge": ["Edge_pc.txt", "edge_pc.txt", "pc_edge_ua.txt"],
        "opera": ["Opera_pc.txt", "opera_pc.txt", "pc_opera_ua.txt"],
        "firefox": ["Firefox_pc.txt", "firefox_pc.txt", "pc_firefox_ua.txt"],
    }
    
    def find_and_load(patterns):
        for pattern in patterns:
            path = os.path.join(ua_folder, pattern)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                    if lines:
                        return random.choice(lines)
            for p in glob.glob(os.path.join(ua_folder, f"*{pattern}*")):
                if os.path.isfile(p):
                    with open(p, 'r', encoding='utf-8') as f:
                        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
                        if lines:
                            return random.choice(lines)
        return None
    
    if browser_type == "random":
        browsers = ["chrome", "edge", "opera", "firefox"]
        weights = RANDOM_OPTIONS["browser_weights"]
        browser_type = random.choices(browsers, weights=weights)[0]
    
    if browser_type in ua_files:
        ua = find_and_load(ua_files[browser_type])
        if ua:
            print(f"[UA 로드] {browser_type.upper()} UA 파일에서 로드")
            return browser_type.capitalize(), ua
    
    return None, None


def get_default_ua(browser_type="chrome"):
    """기본 UA 반환 (파일 없을 때)"""
    defaults = {
        "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        "opera": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 OPR/125.0.0.0",
        "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
    }
    return defaults.get(browser_type, defaults["chrome"])


# ============================================
# UA 파싱
# ============================================
def parse_ua(ua):
    """UA 문자열 파싱"""
    result = {
        "platform": "Windows",
        "is_mobile": False,
        "browser": "Unknown",
        "browser_version": "",
        "chromium_version": None,
        "needs_hints": True,
        "is_firefox": False,
        "is_edge": False,
        "is_opera": False,
    }
    
    patterns = [
        (r'Edg/(\d+[\d.]*)', "Microsoft Edge"),
        (r'OPR/(\d+[\d.]*)', "Opera"),
        (r'Firefox/(\d+[\d.]*)', "Firefox"),
        (r'Chrome/(\d+[\d.]*)', "Google Chrome"),
    ]
    
    for pattern, browser in patterns:
        m = re.search(pattern, ua)
        if m:
            result["browser"] = browser
            result["browser_version"] = m.group(1)
            break
    
    m = re.search(r'Chrome/(\d+[\d.]*)', ua)
    if m:
        result["chromium_version"] = m.group(1)
    
    if result["browser"] == "Firefox":
        result["is_firefox"] = True
        result["needs_hints"] = False
    elif result["browser"] == "Microsoft Edge":
        result["is_edge"] = True
    elif result["browser"] == "Opera":
        result["is_opera"] = True
    
    return result


# ============================================
# Client Hints 생성
# ============================================
def generate_pc_hints(ua_info, browser_version):
    """PC용 Client Hints 생성"""
    
    if not ua_info["needs_hints"]:
        return None
    
    browser = ua_info["browser"]
    chromium_version = ua_info.get("chromium_version", browser_version)
    major = browser_version.split(".")[0]
    chromium_major = chromium_version.split(".")[0] if chromium_version else major
    
    chromium_full = get_chrome_full_version(chromium_major)
    
    if browser == "Opera":
        browser_full = get_opera_full_version(major)
    elif browser == "Microsoft Edge":
        browser_full = get_edge_full_version(major)
    else:
        browser_full = chromium_full
    
    # Chrome 버전별 GREASE 값 (Chrome 110부터 "Not A(Brand" 사용)
    chromium_major_int = int(chromium_major) if chromium_major.isdigit() else 100
    
    if chromium_major_int >= 110:
        # Chrome 110+ : "Not A(Brand", version 24
        grease = "Not A(Brand"
        grease_version = "24"
    else:
        # Chrome 109 이하: "Not?A_Brand", version 8
        grease = "Not?A_Brand"
        grease_version = "8"
    
    # 순서도 버전에 따라 다름 (Chrome 110+는 Browser → Chromium → GREASE)
    if browser == "Google Chrome":
        if chromium_major_int >= 110:
            order = ["Google Chrome", "Chromium", "GREASE"]
        else:
            order = ["Google Chrome", "GREASE", "Chromium"]
    elif browser == "Microsoft Edge":
        order = ["Microsoft Edge", "Chromium", "GREASE"]
    elif browser == "Opera":
        if chromium_major_int >= 110:
            order = ["Opera", "Chromium", "GREASE"]
        else:
            order = ["Opera", "GREASE", "Chromium"]
    else:
        if chromium_major_int >= 110:
            order = ["Google Chrome", "Chromium", "GREASE"]
        else:
            order = ["Google Chrome", "GREASE", "Chromium"]
    
    brands = []
    full_version_list = []
    
    brand_info = {
        "Chromium": {"major": chromium_major, "full": chromium_full},
        "Google Chrome": {"major": chromium_major, "full": chromium_full},
        "Microsoft Edge": {"major": major, "full": browser_full},
        "Opera": {"major": major, "full": browser_full},
    }
    
    for brand_name in order:
        if brand_name == "GREASE":
            brands.append({"brand": grease, "version": grease_version})
            full_version_list.append({"brand": grease, "version": f"{grease_version}.0.0.0"})
        elif brand_name in brand_info:
            brands.append({"brand": brand_name, "version": brand_info[brand_name]["major"]})
            full_version_list.append({"brand": brand_name, "version": brand_info[brand_name]["full"]})
    
    return {
        "brands": brands,
        "fullVersionList": full_version_list,
        "mobile": False,
        "platform": "Windows",
        "platformVersion": "10.0.0",
        "architecture": "x86",
        "bitness": "64",
        "model": "",
        "wow64": False,
        "formFactors": ["Desktop"],
    }


# ============================================
# JS 스푸핑 코드 생성
# ============================================
def generate_pc_js_spoof(ua_info, ua, hints, preset_info):
    """PC용 JS 스푸핑 코드 생성"""
    
    browser = ua_info.get("browser", "")
    is_firefox = ua_info.get("is_firefox", False)
    is_edge = ua_info.get("is_edge", False)
    is_opera = ua_info.get("is_opera", False)
    
    screen_w = preset_info["screen_w"]
    screen_h = preset_info["screen_h"]
    inner_w = preset_info["inner_w"]
    inner_h = preset_info["inner_h"]
    dpr = preset_info["dpr"]
    
    if is_firefox:
        nav_vendor = ""
        device_memory = "undefined"
    else:
        nav_vendor = "Google Inc."
        device_memory = preset_info["memory"]
    
    if is_firefox:
        do_not_track = '"unspecified"'
    else:
        do_not_track = "null"
    
    if is_edge:
        languages_array = '["ko","en","en-US"]'
        language_single = "ko"
    else:
        languages_array = '["ko-KR","ko","en-US","en"]'
        language_single = "ko-KR"
    
    hints_json = json.dumps(hints) if hints else "null"
    has_user_agent_data = not is_firefox
    
    # PC용 WebGL 값 설정
    if is_firefox:
        webgl_vendor = "Mozilla"
        webgl_renderer = "Mozilla"
        webgl_unmasked_vendor = "Google Inc. (Intel)"
        webgl_unmasked_renderer = "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    elif is_opera or is_edge:
        webgl_vendor = "Google Inc. (Google)"
        webgl_renderer = "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)"
        webgl_unmasked_vendor = "Google Inc. (Google)"
        webgl_unmasked_renderer = "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)"
    else:
        # Chrome PC 기본값
        webgl_vendor = "WebKit"
        webgl_renderer = "WebKit WebGL"
        webgl_unmasked_vendor = "Google Inc. (Intel)"
        webgl_unmasked_renderer = "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    
    js_code = f"""
(function() {{
    'use strict';
    
    const CONFIG = {{
        ua: {json.dumps(ua)},
        platform: "Win32",
        isFirefox: {str(is_firefox).lower()},
        isEdge: {str(is_edge).lower()},
        isOpera: {str(is_opera).lower()},
        maxTouchPoints: 0,
        hardwareConcurrency: 8,
        deviceMemory: {device_memory},
        vendor: {json.dumps(nav_vendor)},
        dpr: {dpr},
        screenWidth: {screen_w},
        screenHeight: {screen_h},
        innerWidth: {inner_w},
        innerHeight: {inner_h},
        hints: {hints_json},
        languagesArray: {languages_array},
        languageSingle: {json.dumps(language_single)},
        hasUserAgentData: {str(has_user_agent_data).lower()},
        doNotTrack: {do_not_track},
        pdfViewerEnabled: true,
        audioSampleRate: 44100,
        productSub: {'"20100101"' if is_firefox else '"20030107"'},
        appCodeName: "Mozilla",
        appName: "Netscape",
        product: "Gecko",
        webglVendor: {json.dumps(webgl_vendor)},
        webglRenderer: {json.dumps(webgl_renderer)},
        webglUnmaskedVendor: {json.dumps(webgl_unmasked_vendor)},
        webglUnmaskedRenderer: {json.dumps(webgl_unmasked_renderer)}
    }};
    
    const safe = (fn) => {{ try {{ fn(); }} catch(e) {{}} }};
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
    
    // navigator 스푸핑
    safe(() => {{
        spoofProperty(NavProto, 'platform', CONFIG.platform);
        spoofProperty(navigator, 'platform', CONFIG.platform);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'userAgent', CONFIG.ua);
        spoofProperty(navigator, 'userAgent', CONFIG.ua);
    }});
    
    // appVersion 스푸핑
    safe(() => {{
        let appVer;
        if (CONFIG.isFirefox) {{
            appVer = '5.0 (Windows)';
        }} else {{
            appVer = CONFIG.ua.replace(/^Mozilla\\//, '');
        }}
        spoofProperty(NavProto, 'appVersion', appVer);
        spoofProperty(navigator, 'appVersion', appVer);
    }});
    
    // productSub 스푸핑
    safe(() => {{
        spoofProperty(NavProto, 'productSub', CONFIG.productSub);
        spoofProperty(navigator, 'productSub', CONFIG.productSub);
    }});
    
    // appCodeName, appName, product 스푸핑
    safe(() => {{
        spoofProperty(NavProto, 'appCodeName', CONFIG.appCodeName);
        spoofProperty(navigator, 'appCodeName', CONFIG.appCodeName);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'appName', CONFIG.appName);
        spoofProperty(navigator, 'appName', CONFIG.appName);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'product', CONFIG.product);
        spoofProperty(navigator, 'product', CONFIG.product);
    }});
    
    safe(() => {{
        spoofProperty(NavProto, 'maxTouchPoints', CONFIG.maxTouchPoints);
        spoofProperty(navigator, 'maxTouchPoints', CONFIG.maxTouchPoints);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'hardwareConcurrency', CONFIG.hardwareConcurrency);
        spoofProperty(navigator, 'hardwareConcurrency', CONFIG.hardwareConcurrency);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'deviceMemory', CONFIG.deviceMemory);
        spoofProperty(navigator, 'deviceMemory', CONFIG.deviceMemory);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'vendor', CONFIG.vendor);
        spoofProperty(navigator, 'vendor', CONFIG.vendor);
    }});
    safe(() => {{
        // languages 배열은 frozen이어야 함
        // 주의: navigator 객체에 직접 설정하면 안 됨! (hasOwnProperty 체크 때문)
        const frozenLanguages = Object.freeze([...CONFIG.languagesArray]);
        spoofProperty(NavProto, 'languages', frozenLanguages);
        // navigator에는 설정하지 않음 - prototype에서 상속받아야 함
    }});
    safe(() => {{
        spoofProperty(NavProto, 'language', CONFIG.languageSingle);
        // navigator에는 설정하지 않음
    }});
    safe(() => {{
        spoofProperty(NavProto, 'doNotTrack', CONFIG.doNotTrack);
        spoofProperty(navigator, 'doNotTrack', CONFIG.doNotTrack);
    }});
    safe(() => {{
        spoofProperty(NavProto, 'pdfViewerEnabled', CONFIG.pdfViewerEnabled);
        spoofProperty(navigator, 'pdfViewerEnabled', CONFIG.pdfViewerEnabled);
    }});
    
    // webdriver 스푸핑 (prototype에만 설정, navigator 직접 설정 X)
    // 실제 브라우저는 webdriver가 prototype에만 있어서 _.has(navigator, 'webdriver')가 false
    safe(() => {{
        spoofProperty(NavProto, 'webdriver', false);
        // navigator 객체에서 own property 제거 (있다면)
        try {{ delete navigator.webdriver; }} catch(e) {{}}
    }});
    
    // screen 스푸핑
    safe(() => {{
        Object.defineProperty(window.screen, 'width', {{ get: () => CONFIG.screenWidth, configurable: true }});
        Object.defineProperty(window.screen, 'height', {{ get: () => CONFIG.screenHeight, configurable: true }});
        Object.defineProperty(window.screen, 'availWidth', {{ get: () => CONFIG.screenWidth, configurable: true }});
        Object.defineProperty(window.screen, 'availHeight', {{ get: () => CONFIG.screenHeight - 50, configurable: true }});
    }});
    
    // window 크기 스푸핑
    safe(() => {{
        Object.defineProperty(window, 'innerWidth', {{ get: () => CONFIG.innerWidth, configurable: true }});
        Object.defineProperty(window, 'innerHeight', {{ get: () => CONFIG.innerHeight, configurable: true }});
        Object.defineProperty(window, 'outerWidth', {{ get: () => CONFIG.screenWidth, configurable: true }});
        Object.defineProperty(window, 'outerHeight', {{ get: () => CONFIG.screenHeight - 50, configurable: true }});
        Object.defineProperty(window, 'devicePixelRatio', {{ get: () => CONFIG.dpr, configurable: true }});
    }});
    
    // userAgentData 스푸핑
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
                        wow64: CONFIG.hints.wow64,
                        formFactors: CONFIG.hints.formFactors,
                        fullVersionList: CONFIG.hints.fullVersionList,
                    }};
                }},
                toJSON: function() {{
                    return {{ brands: CONFIG.hints.brands, mobile: CONFIG.hints.mobile, platform: CONFIG.hints.platform }};
                }}
            }};
            spoofProperty(NavProto, 'userAgentData', mockUserAgentData);
            spoofProperty(navigator, 'userAgentData', mockUserAgentData);
        }} else if (CONFIG.isFirefox) {{
            spoofProperty(NavProto, 'userAgentData', undefined);
            spoofProperty(navigator, 'userAgentData', undefined);
        }}
    }});
    
    // AudioContext 스푸핑
    safe(() => {{
        const OriginalAudioContext = window.AudioContext || window.webkitAudioContext;
        if (OriginalAudioContext) {{
            const WrappedAudioContext = function(...args) {{
                const ctx = new OriginalAudioContext(...args);
                Object.defineProperty(ctx, 'sampleRate', {{ get: () => CONFIG.audioSampleRate, configurable: true }});
                if (CONFIG.isFirefox) {{
                    Object.defineProperty(ctx, 'state', {{ get: () => 'suspended', configurable: true }});
                    Object.defineProperty(ctx, 'baseLatency', {{ get: () => 0, configurable: true }});
                    try {{ Object.defineProperty(ctx.destination, 'maxChannelCount', {{ get: () => 0, configurable: true }}); }} catch(e) {{}}
                }}
                return ctx;
            }};
            WrappedAudioContext.prototype = OriginalAudioContext.prototype;
            Object.defineProperty(WrappedAudioContext, 'name', {{ value: 'AudioContext' }});
            window.AudioContext = WrappedAudioContext;
            if (window.webkitAudioContext) window.webkitAudioContext = WrappedAudioContext;
        }}
    }});
    
    // 터치 이벤트 제거
    safe(() => {{ delete window.ontouchstart; delete document.ontouchstart; }});
    
    // Firefox 전용
    if (CONFIG.isFirefox) {{
        safe(() => {{
            try {{ delete window.TouchEvent; }} catch(e) {{ Object.defineProperty(window, 'TouchEvent', {{ get: () => undefined, configurable: true }}); }}
        }});
        safe(() => {{
            try {{ delete navigator.deviceMemory; delete Navigator.prototype.deviceMemory; }} catch(e) {{}}
            try {{ delete navigator.connection; delete Navigator.prototype.connection; }} catch(e) {{}}
            try {{ delete navigator.bluetooth; delete Navigator.prototype.bluetooth; }} catch(e) {{}}
            try {{ delete navigator.usb; delete Navigator.prototype.usb; }} catch(e) {{}}
            try {{ delete navigator.serial; delete Navigator.prototype.serial; }} catch(e) {{}}
            try {{ delete navigator.hid; delete Navigator.prototype.hid; }} catch(e) {{}}
            try {{ delete navigator.vibrate; delete Navigator.prototype.vibrate; }} catch(e) {{}}
            try {{ delete navigator.share; delete Navigator.prototype.share; }} catch(e) {{}}
            try {{ delete navigator.presentation; delete Navigator.prototype.presentation; }} catch(e) {{}}
            try {{ delete navigator.getBattery; delete Navigator.prototype.getBattery; }} catch(e) {{}}
            try {{ Object.defineProperty(performance, 'memory', {{ get: () => undefined, configurable: true }}); }} catch(e) {{}}
        }});
        safe(() => {{
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {{
                if (type === 'webgl2' || type === 'experimental-webgl2') return null;
                return originalGetContext.call(this, type, ...args);
            }};
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {{
                if (param === 7938) return 'WebGL 1.0';
                if (param === 35724) return 'WebGL GLSL ES 1.0';
                if (param === 7936) return 'Mozilla';
                if (param === 7937) {{
                    const debugExt = this.getExtension('WEBGL_debug_renderer_info');
                    if (debugExt) {{
                        let unmasked = originalGetParameter.call(this, 37446);
                        if (unmasked) {{
                            // Firefox 형식으로 정리: (0x숫자) 제거, ", D3D11)" 제거
                            unmasked = unmasked.replace(/\\s*\\(0x[0-9A-Fa-f]+\\)/g, '');
                            unmasked = unmasked.replace(/,\\s*D3D11\\)/g, ')');
                            if (!unmasked.includes(', or similar')) unmasked = unmasked + ', or similar';
                        }}
                        return unmasked;
                    }}
                    return 'ANGLE (Microsoft, Microsoft Basic Render Driver Direct3D11 vs_5_0 ps_5_0), or similar';
                }}
                if (param === 37446) {{
                    let unmasked = originalGetParameter.call(this, param);
                    if (unmasked) {{
                        // Firefox 형식으로 정리: (0x숫자) 제거, ", D3D11)" 제거
                        unmasked = unmasked.replace(/\\s*\\(0x[0-9A-Fa-f]+\\)/g, '');
                        unmasked = unmasked.replace(/,\\s*D3D11\\)/g, ')');
                        if (!unmasked.includes(', or similar')) unmasked = unmasked + ', or similar';
                    }}
                    return unmasked;
                }}
                return originalGetParameter.call(this, param);
            }};
            const originalGetSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
            WebGLRenderingContext.prototype.getSupportedExtensions = function() {{
                const ext = originalGetSupportedExtensions.call(this);
                if (ext) {{
                    // WEBGL_debug_renderer_info가 없으면 추가
                    if (ext.indexOf('WEBGL_debug_renderer_info') === -1) {{
                        ext.push('WEBGL_debug_renderer_info');
                    }}
                    if (ext.length > 27) {{
                        const sliced = ext.slice(0, 27);
                        if (sliced.indexOf('WEBGL_debug_renderer_info') === -1) {{
                            sliced.push('WEBGL_debug_renderer_info');
                        }}
                        return sliced;
                    }}
                }}
                return ext;
            }};
        }});
    }}
    
    // Chrome 기본 (Firefox, Opera, Edge 아닌 경우) - getSupportedExtensions에 WEBGL_debug_renderer_info 추가
    if (!CONFIG.isFirefox && !CONFIG.isOpera && !CONFIG.isEdge) {{
        safe(() => {{
            const originalGetSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
            WebGLRenderingContext.prototype.getSupportedExtensions = function() {{
                const ext = originalGetSupportedExtensions.call(this);
                if (ext) {{
                    // WEBGL_debug_renderer_info가 없으면 추가
                    if (ext.indexOf('WEBGL_debug_renderer_info') === -1) {{
                        ext.push('WEBGL_debug_renderer_info');
                    }}
                }}
                return ext;
            }};
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                const originalGetSupportedExtensions2 = WebGL2RenderingContext.prototype.getSupportedExtensions;
                WebGL2RenderingContext.prototype.getSupportedExtensions = function() {{
                    const ext = originalGetSupportedExtensions2.call(this);
                    if (ext) {{
                        if (ext.indexOf('WEBGL_debug_renderer_info') === -1) {{
                            ext.push('WEBGL_debug_renderer_info');
                        }}
                    }}
                    return ext;
                }};
            }}
        }});
    }}
    
    // Opera/Edge WebGL 스푸핑
    if (CONFIG.isOpera || CONFIG.isEdge) {{
        safe(() => {{
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {{
                if (param === 37445) return 'Google Inc. (Google)';
                if (param === 37446) return 'ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)';
                if (param === 3379) return 8192;
                if (param === 34076) return 16384;
                if (param === 34024) return 8192;
                if (param === 3386) return new Int32Array([8192, 8192]);
                if (param === 36349) return 4096;
                if (param === 36348) return 31;
                if (param === 33901) return new Float32Array([1, 1023]);
                return originalGetParameter.call(this, param);
            }};
            const originalGetSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
            WebGLRenderingContext.prototype.getSupportedExtensions = function() {{
                const ext = originalGetSupportedExtensions.call(this);
                if (ext) {{
                    // WEBGL_debug_renderer_info가 없으면 추가
                    if (ext.indexOf('WEBGL_debug_renderer_info') === -1) {{
                        ext.push('WEBGL_debug_renderer_info');
                    }}
                    if (ext.length > 35) {{
                        const sliced = ext.slice(0, 35);
                        if (sliced.indexOf('WEBGL_debug_renderer_info') === -1) {{
                            sliced.push('WEBGL_debug_renderer_info');
                        }}
                        return sliced;
                    }}
                }}
                return ext;
            }};
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(param) {{
                    if (param === 37445) return 'Google Inc. (Google)';
                    if (param === 37446) return 'ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)';
                    if (param === 3379) return 8192;
                    if (param === 34076) return 16384;
                    if (param === 34024) return 8192;
                    if (param === 3386) return new Int32Array([8192, 8192]);
                    if (param === 36349) return 4096;
                    if (param === 36348) return 31;
                    if (param === 33901) return new Float32Array([1, 1023]);
                    if (param === 36183) return 4;
                    return originalGetParameter2.call(this, param);
                }};
            }}
        }});
    }}
    
    // Firefox/Edge locale 스푸핑
    if (CONFIG.isFirefox || CONFIG.isEdge) {{
        safe(() => {{
            const OriginalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(locales, options) {{
                const instance = new OriginalDateTimeFormat(locales, options);
                const originalResolvedOptions = instance.resolvedOptions.bind(instance);
                instance.resolvedOptions = function() {{
                    const result = originalResolvedOptions();
                    result.locale = 'ko-KR';
                    return result;
                }};
                return instance;
            }};
            Intl.DateTimeFormat.prototype = OriginalDateTimeFormat.prototype;
            Intl.DateTimeFormat.supportedLocalesOf = OriginalDateTimeFormat.supportedLocalesOf;
        }});
    }}
    
    // Firefox 폰트 스푸핑 (Arial Black 등 숨기기)
    if (CONFIG.isFirefox) {{
        safe(() => {{
            const firefoxAllowedFonts = new Set(['arial', 'verdana', 'times new roman', 'georgia', 'courier new', 'malgun gothic', 'comic sans ms', 'impact', 'trebuchet ms', 'lucida console', 'tahoma', 'helvetica', 'segoe ui']);
            const systemFonts = new Set(['sans-serif', 'serif', 'monospace', 'cursive', 'fantasy', 'system-ui']);
            const extractFirstFont = (fontStr) => {{
                const match = fontStr.match(/(?:\\d+(?:px|pt|em|rem|%)\\s+)?([^,]+)/i);
                if (match) return match[1].trim().toLowerCase().replace(/['"]/g, '');
                return '';
            }};
            const originalMeasureText = CanvasRenderingContext2D.prototype.measureText;
            CanvasRenderingContext2D.prototype.measureText = function(text) {{
                const result = originalMeasureText.call(this, text);
                const fontName = extractFirstFont(this.font);
                if (systemFonts.has(fontName)) return result;
                // Firefox에서 허용되지 않은 폰트는 기본 폰트처럼 보이게
                if (!firefoxAllowedFonts.has(fontName)) {{
                    // 기본 폰트(monospace) 너비 반환하여 폰트 감지 실패하게
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    ctx.font = this.font.replace(fontName, 'monospace');
                    return originalMeasureText.call(ctx, text);
                }}
                return result;
            }};
        }});
    }}
    
    // Chrome/Edge/Opera 폰트 스푸핑
    if (!CONFIG.isFirefox) {{
        safe(() => {{
            const basePcFonts = new Set(['arial', 'verdana', 'times new roman', 'georgia', 'courier new', 'malgun gothic', 'comic sans ms', 'impact', 'trebuchet ms', 'lucida console', 'tahoma', 'helvetica', 'segoe ui']);
            const edgeFonts = new Set(['arial', 'verdana', 'times new roman', 'georgia', 'courier new', 'roboto', 'malgun gothic', 'comic sans ms', 'impact', 'trebuchet ms', 'lucida console', 'tahoma', 'helvetica', 'segoe ui']);
            const allowedFonts = CONFIG.isEdge ? edgeFonts : basePcFonts;
            const systemFonts = new Set(['sans-serif', 'serif', 'monospace', 'cursive', 'fantasy', 'system-ui']);
            const fontOffsets = {{'arial': 0.1, 'verdana': 0.15, 'times new roman': 0.08, 'georgia': 0.12, 'courier new': 0.05, 'roboto': 0.07, 'malgun gothic': 0.09, 'comic sans ms': 0.11, 'impact': 0.14, 'trebuchet ms': 0.06, 'lucida console': 0.04, 'tahoma': 0.09, 'helvetica': 0.13, 'segoe ui': 0.10}};
            const extractFirstFont = (fontStr) => {{
                const match = fontStr.match(/(?:\\d+(?:px|pt|em|rem|%)\\s+)?([^,]+)/i);
                if (match) return match[1].trim().toLowerCase().replace(/['"]/g, '');
                return '';
            }};
            const originalMeasureText = CanvasRenderingContext2D.prototype.measureText;
            CanvasRenderingContext2D.prototype.measureText = function(text) {{
                const result = originalMeasureText.call(this, text);
                const fontName = extractFirstFont(this.font);
                if (systemFonts.has(fontName)) return result;
                if (allowedFonts.has(fontName)) {{
                    const offset = fontOffsets[fontName] || 0.001;
                    return {{ width: result.width + offset, actualBoundingBoxLeft: result.actualBoundingBoxLeft, actualBoundingBoxRight: result.actualBoundingBoxRight, actualBoundingBoxAscent: result.actualBoundingBoxAscent, actualBoundingBoxDescent: result.actualBoundingBoxDescent, fontBoundingBoxAscent: result.fontBoundingBoxAscent, fontBoundingBoxDescent: result.fontBoundingBoxDescent }};
                }}
                return result;
            }};
        }});
    }}
    
    // ========== 새 탭 방지 (target="_blank" 제거) ==========
    // 링크 클릭 시 새 탭 대신 현재 탭에서 열리게 함
    // 네이버 서버는 새 탭/현재 탭 구분 불가 (클라이언트 동작이므로)
    safe(() => {{
        document.addEventListener('click', function(e) {{
            const link = e.target.closest('a');
            if (link && link.target === '_blank') {{
                link.removeAttribute('target');
                // rel="noopener" 등도 제거 (선택사항)
                link.removeAttribute('rel');
            }}
        }}, true);  // capture phase에서 실행 (다른 핸들러보다 먼저)
    }});
    
    // ========== Web Worker 스푸핑 ==========
    // Worker 내부에서도 동일한 값이 반환되도록 Worker 생성자를 가로챔
    safe(() => {{
        const OriginalWorker = window.Worker;
        
        // Worker 내부에 주입할 스푸핑 코드 (CONFIG 값 사용)
        // 주의: WorkerNavigator에 원래 없는 속성(productSub, maxTouchPoints, cookieEnabled 등)은
        // 실제 브라우저에서도 undefined이므로 스푸핑하지 않음
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
                    webglUnmaskedRenderer: ` + JSON.stringify(CONFIG.webglUnmaskedRenderer) + `,
                    isFirefox: ` + CONFIG.isFirefox + `
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
                        // Firefox일 때는 Main과 동일한 변환 로직 적용
                        if (spoofedValues.isFirefox) {{
                            if (param === 7936) return 'Mozilla';
                            if (param === 7937) {{
                                let unmasked = originalGetParameter.call(this, 37446);
                                if (unmasked) {{
                                    unmasked = unmasked.replace(/\\s*\\(0x[0-9A-Fa-f]+\\)/g, '');
                                    unmasked = unmasked.replace(/,\\s*D3D11\\)/g, ')');
                                    if (!unmasked.includes(', or similar')) unmasked = unmasked + ', or similar';
                                }}
                                return unmasked || 'ANGLE (Microsoft, Microsoft Basic Render Driver Direct3D11 vs_5_0 ps_5_0), or similar';
                            }}
                            if (param === 37446) {{
                                let unmasked = originalGetParameter.call(this, param);
                                if (unmasked) {{
                                    unmasked = unmasked.replace(/\\s*\\(0x[0-9A-Fa-f]+\\)/g, '');
                                    unmasked = unmasked.replace(/,\\s*D3D11\\)/g, ')');
                                    if (!unmasked.includes(', or similar')) unmasked = unmasked + ', or similar';
                                }}
                                return unmasked;
                            }}
                            if (param === 37445) {{
                                let vendor = originalGetParameter.call(this, param);
                                return vendor;
                            }}
                        }} else {{
                            // 37445 = UNMASKED_VENDOR_WEBGL, 37446 = UNMASKED_RENDERER_WEBGL
                            if (param === 37445) return spoofedValues.webglUnmaskedVendor;
                            if (param === 37446) return spoofedValues.webglUnmaskedRenderer;
                            // 7936 = VENDOR, 7937 = RENDERER
                            if (param === 7936) return spoofedValues.webglVendor;
                            if (param === 7937) return spoofedValues.webglRenderer;
                        }}
                        return originalGetParameter.call(this, param);
                    }};
                    
                    // getSupportedExtensions에 WEBGL_debug_renderer_info 추가
                    const originalGetSupportedExtensions = WebGLRenderingContext.prototype.getSupportedExtensions;
                    WebGLRenderingContext.prototype.getSupportedExtensions = function() {{
                        const ext = originalGetSupportedExtensions.call(this);
                        if (ext && ext.indexOf('WEBGL_debug_renderer_info') === -1) {{
                            ext.push('WEBGL_debug_renderer_info');
                        }}
                        return ext;
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
    
    // Firefox: window.chrome 삭제 (실제 Firefox에는 없음)
    if (CONFIG.isFirefox) {{
        safe(() => {{
            // configurable: false라서 delete나 defineProperty 안 됨
            // 하지만 writable: true니까 직접 할당으로 덮어쓰기
            window.chrome = undefined;
        }});
        
        // Firefox: userAgentData 속성 완전 삭제
        safe(() => {{
            try {{
                delete Navigator.prototype.userAgentData;
                delete navigator.userAgentData;
            }} catch(e) {{}}
            
            if ('userAgentData' in Navigator.prototype) {{
                Object.defineProperty(Navigator.prototype, 'userAgentData', {{
                    value: undefined,
                    writable: true,
                    configurable: true
                }});
                delete Navigator.prototype.userAgentData;
            }}
        }});
    }}
    
    // ========== 추가 스푸핑 1: Error.prepareStackTrace ==========
    safe(() => {{
        const originalPrepareStackTrace = Error.prepareStackTrace;
        Error.prepareStackTrace = function(error, structuredStackTrace) {{
            if (originalPrepareStackTrace) {{
                return originalPrepareStackTrace(error, structuredStackTrace);
            }}
            return error.stack;
        }};
        
        if (Error.captureStackTrace) {{
            const originalCaptureStackTrace = Error.captureStackTrace;
            Error.captureStackTrace = function(targetObject, constructorOpt) {{
                originalCaptureStackTrace(targetObject, constructorOpt);
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
    safe(() => {{
        if (!navigator.scheduling) {{
            const scheduling = {{
                isInputPending: function(options) {{
                    return false;
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
    safe(() => {{
        Date.prototype.getTimezoneOffset = function() {{
            return -540; // 한국 시간대 (UTC+9)
        }};
    }});
    
    // ========== 추가 스푸핑 5: iframe.contentWindow ==========
    safe(() => {{
        const originalCreateElement = document.createElement;
        document.createElement = function(tagName) {{
            const element = originalCreateElement.call(document, tagName);
            
            if (tagName.toLowerCase() === 'iframe') {{
                element.addEventListener('load', function() {{
                    try {{
                        const iframeWindow = element.contentWindow;
                        const iframeNavigator = iframeWindow.navigator;
                        const iframeNavProto = Object.getPrototypeOf(iframeNavigator);
                        
                        Object.defineProperty(iframeNavProto, 'webdriver', {{
                            get: () => false,
                            configurable: true
                        }});
                        
                        Object.defineProperty(iframeNavProto, 'userAgent', {{
                            get: () => CONFIG.userAgent,
                            configurable: true
                        }});
                        
                        Object.defineProperty(iframeNavProto, 'platform', {{
                            get: () => CONFIG.platform,
                            configurable: true
                        }});
                    }} catch(e) {{}}
                }});
            }}
            
            return element;
        }};
    }});
    
    // ========== 추가 스푸핑 6: navigator.product ==========
    safe(() => {{
        spoofProperty(NavProto, 'product', 'Gecko');
    }});
    
    console.log('[CDP PC Spoof v2] 완료');
}})();
"""
    return js_code


# ============================================
# PC 에뮬레이션 설정
# ============================================
def setup_pc_emulation(cdp, ua, preset_info):
    """PC 에뮬레이션 설정"""
    
    cdp.send("Network.enable", {})
    cdp.send("Page.enable", {})
    
    ua_info = parse_ua(ua)
    
    print(f"\n[UA 분석]")
    print(f"  브라우저: {ua_info['browser']} {ua_info['browser_version']}")
    print(f"  Chromium: {ua_info['chromium_version']}")
    
    hints = generate_pc_hints(ua_info, ua_info['browser_version'])
    
    # Accept-Language 헤더 설정 (navigator.languages와 일치해야 함)
    accept_language = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    
    ua_override_params = {
        "userAgent": ua,
        "acceptLanguage": accept_language,
    }
    
    if hints:
        ua_override_params["userAgentMetadata"] = {
            "brands": hints["brands"],
            "fullVersionList": hints["fullVersionList"],
            "platform": hints["platform"],
            "platformVersion": hints["platformVersion"],
            "architecture": hints["architecture"],
            "bitness": hints["bitness"],
            "model": hints["model"],
            "mobile": hints["mobile"],
            "wow64": hints["wow64"],
        }
    
    cdp.send("Emulation.setUserAgentOverride", ua_override_params)
    
    cdp.send("Emulation.setDeviceMetricsOverride", {
        "width": preset_info["inner_w"],
        "height": preset_info["inner_h"],
        "deviceScaleFactor": preset_info["dpr"],
        "mobile": False,
        "screenWidth": preset_info["screen_w"],
        "screenHeight": preset_info["screen_h"],
    })
    
    cdp.send("Emulation.setTouchEmulationEnabled", {
        "enabled": False,
        "maxTouchPoints": 0,
    })
    
    # viewport 업데이트
    CONFIG["viewport"]["width"] = preset_info["inner_w"]
    CONFIG["viewport"]["height"] = preset_info["inner_h"]
    
    js_spoof = generate_pc_js_spoof(ua_info, ua, hints, preset_info)
    
    cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": js_spoof})
    cdp.send("Runtime.evaluate", {
        "expression": js_spoof,
        "allowUnsafeEvalBlockedByCSP": True,
    })
    
    print(f"[CDP] PC 에뮬레이션 설정 완료")
    print(f"  화면: {preset_info['screen_w']}x{preset_info['screen_h']} (DPR: {preset_info['dpr']})")
    print(f"  창: {preset_info['inner_w']}x{preset_info['inner_h']}")
    print(f"  메모리: {preset_info['memory']}GB")
    
    return {"ua_info": ua_info, "hints": hints, "preset": preset_info}


def save_result(value):
    """결과를 파일로 저장"""
    try:
        with open(CONFIG["result_file"], "w", encoding="utf-8") as f:
            f.write(value)
        print(f"[결과 저장] {CONFIG['result_file']} → {value}")
    except Exception as e:
        print(f"[결과 저장 실패] {e}")
        # 파일 저장 실패 시 클립보드로 대체
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
            if "search.naver.com" in url or "www.naver.com" in url or "naver.com" in url:
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
# 탭 관리 함수
# ============================================
def get_all_tabs():
    """모든 탭 목록 가져오기"""
    try:
        url = f"http://localhost:{CONFIG['chrome_port']}/json"
        response = requests.get(url, timeout=5)
        tabs = response.json()
        # page 타입만 필터링
        return [tab for tab in tabs if tab.get("type") == "page"]
    except Exception as e:
        print(f"[오류] 탭 목록 가져오기 실패: {e}")
        return []


def close_tab(tab_id):
    """특정 탭 닫기"""
    try:
        url = f"http://localhost:{CONFIG['chrome_port']}/json/close/{tab_id}"
        requests.get(url, timeout=5)
        print(f"[탭 닫기] {tab_id}")
        return True
    except Exception as e:
        print(f"[오류] 탭 닫기 실패: {e}")
        return False


def switch_to_tab(ws_url):
    """특정 탭으로 전환 (새 CDP 연결)"""
    try:
        return CDP(ws_url)
    except Exception as e:
        print(f"[오류] 탭 전환 실패: {e}")
        return None


def close_new_tab_and_return(original_tab_id):
    """
    새 탭 닫고 원래 탭으로 복귀
    
    Returns:
        CDP 객체 (원래 탭) 또는 None
    """
    tabs = get_all_tabs()
    
    if len(tabs) <= 1:
        print("[탭] 탭이 1개뿐이라 닫지 않음")
        return None
    
    # 원래 탭 찾기
    original_tab = None
    new_tabs = []
    
    for tab in tabs:
        if tab.get("id") == original_tab_id:
            original_tab = tab
        else:
            new_tabs.append(tab)
    
    if not original_tab:
        print("[오류] 원래 탭을 찾을 수 없음")
        return None
    
    # 새 탭들 닫기
    for tab in new_tabs:
        print(f"[탭 닫기] {tab.get('title', 'Unknown')[:30]}...")
        close_tab(tab.get("id"))
        time.sleep(0.3)
    
    # 원래 탭으로 연결
    print(f"[탭 복귀] {original_tab.get('title', 'Unknown')[:30]}...")
    time.sleep(0.5)
    
    return switch_to_tab(original_tab.get("webSocketDebuggerUrl"))


# ============================================
# 마우스 이동 (사람처럼 곡선 이동)
# ============================================
# 현재 마우스 위치 저장 (전역)
current_mouse_pos = {"x": 512, "y": 384}  # 화면 중앙에서 시작


def move_mouse_to(cdp, target_x, target_y, steps=None):
    """
    마우스를 현재 위치에서 목표 위치까지 사람처럼 이동
    - 베지어 곡선으로 자연스러운 경로
    - 속도 변화 (시작 느림 → 중간 빠름 → 끝 느림)
    """
    global current_mouse_pos
    
    start_x = current_mouse_pos["x"]
    start_y = current_mouse_pos["y"]
    
    # 이동 거리 계산
    distance = ((target_x - start_x) ** 2 + (target_y - start_y) ** 2) ** 0.5
    
    # 거리에 따라 스텝 수 결정 (짧으면 적게, 길면 많이)
    if steps is None:
        steps = max(5, min(25, int(distance / 30)))
    
    print(f"[마우스 이동] ({start_x:.0f}, {start_y:.0f}) → ({target_x:.0f}, {target_y:.0f}), 거리: {distance:.0f}px, 스텝: {steps}")
    
    # 컨트롤 포인트 (베지어 곡선용) - 약간의 곡선 추가
    ctrl_x = (start_x + target_x) / 2 + random.uniform(-50, 50)
    ctrl_y = (start_y + target_y) / 2 + random.uniform(-30, 30)
    
    for i in range(steps + 1):
        # t: 0 → 1 (이징 적용: ease-in-out)
        t = i / steps
        # ease-in-out 함수
        if t < 0.5:
            eased_t = 2 * t * t
        else:
            eased_t = 1 - ((-2 * t + 2) ** 2) / 2
        
        # 베지어 곡선 좌표 계산
        inv_t = 1 - eased_t
        x = inv_t * inv_t * start_x + 2 * inv_t * eased_t * ctrl_x + eased_t * eased_t * target_x
        y = inv_t * inv_t * start_y + 2 * inv_t * eased_t * ctrl_y + eased_t * eased_t * target_y
        
        # 약간의 흔들림 추가 (마지막 스텝 제외)
        if i < steps:
            x += random.uniform(-2, 2)
            y += random.uniform(-2, 2)
        
        # 마우스 이동 이벤트
        cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": x,
            "y": y
        })
        
        # 속도 변화가 있는 딜레이
        base_delay = 0.01
        if t < 0.2 or t > 0.8:  # 시작과 끝에서 느리게
            delay = base_delay * random.uniform(1.5, 2.5)
        else:  # 중간에서 빠르게
            delay = base_delay * random.uniform(0.5, 1.0)
        
        time.sleep(delay)
    
    # 현재 위치 업데이트
    current_mouse_pos["x"] = target_x
    current_mouse_pos["y"] = target_y


def do_mouse_click(cdp, x, y, show_effect=True, move_first=True):
    """마우스 클릭 실행 + 시각적 피드백"""
    
    # 마우스 이동 먼저 (사람처럼)
    if move_first:
        move_mouse_to(cdp, x, y)
        time.sleep(random.uniform(0.05, 0.15))  # 이동 후 짧은 대기
    
    print(f"[마우스 클릭] x: {x:.1f}, y: {y:.1f}")
    
    # 시각적 피드백 - 클릭 위치에 빨간 점 표시
    if show_effect:
        cdp.send("Runtime.evaluate", {
            "expression": f"""
            (function() {{
                const dot = document.createElement('div');
                dot.style.cssText = `
                    position:fixed; left:{x-10}px; top:{y-10}px;
                    width:20px; height:20px; background:rgba(255,0,0,0.7);
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
    
    # 마우스 클릭 (mousePressed)
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": x,
        "y": y,
        "button": "left",
        "clickCount": 1
    })
    
    # 짧은 유지
    hold_time = random.uniform(0.05, 0.12)
    print(f"[마우스 홀드] {hold_time:.3f}초")
    time.sleep(hold_time)
    
    # 마우스 릴리즈 (mouseReleased)
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": x,
        "y": y,
        "button": "left",
        "clickCount": 1
    })
    
    print(f"[마우스 클릭 완료]")


def do_triple_click(cdp, x, y, move_first=True):
    """트리플 클릭 (전체선택)"""
    
    # 마우스 이동 먼저
    if move_first:
        move_mouse_to(cdp, x, y)
        time.sleep(random.uniform(0.05, 0.1))
    
    print(f"[트리플 클릭] x: {x:.1f}, y: {y:.1f}")
    
    for i in range(3):
        cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": i + 1
        })
        cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": i + 1
        })
        time.sleep(random.uniform(0.03, 0.06))
    
    print(f"[트리플 클릭 완료]")


def check_text_selected(cdp):
    """텍스트 선택 여부 확인"""
    result = cdp.send("Runtime.evaluate", {
        "expression": "window.getSelection().toString().length > 0",
        "returnByValue": True
    })
    return result.get("result", {}).get("value", False)


def do_mouse_back(cdp):
    """마우스 뒤로가기 버튼 클릭 (마우스 4번 버튼)"""
    viewport = CONFIG["viewport"]
    
    # 화면 중앙 근처에서 뒤로가기 버튼 클릭
    x = viewport["width"] // 2 + random.randint(-50, 50)
    y = viewport["height"] // 2 + random.randint(-50, 50)
    
    print(f"[마우스 뒤로가기] 버튼 클릭 at ({x}, {y})")
    
    # 마우스 이동
    move_mouse_to(cdp, x, y)
    time.sleep(random.uniform(0.05, 0.1))
    
    # 마우스 뒤로가기 버튼 (back)
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": x,
        "y": y,
        "button": "back",
        "clickCount": 1
    })
    
    time.sleep(random.uniform(0.03, 0.08))
    
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": x,
        "y": y,
        "button": "back",
        "clickCount": 1
    })
    
    print(f"[마우스 뒤로가기 완료]")


def do_history_back(cdp):
    """브라우저 뒤로가기 (history.back) - 백업용"""
    print(f"[뒤로가기] history.back() 실행")
    
    cdp.send("Runtime.evaluate", {
        "expression": "history.back()"
    })
    
    # 페이지 이동 대기
    time.sleep(random.uniform(1.0, 2.0))
    print(f"[뒤로가기 완료]")


# ============================================
# 마우스 휠 스크롤
# ============================================
def do_mouse_scroll(cdp, distance, show_effect=True):
    """마우스 휠 스크롤 실행 (랜덤화 적용) - 지도 영역 회피"""
    viewport = CONFIG["viewport"]
    scroll_config = CONFIG["scroll"]
    mouse_random = CONFIG["mouse_random"]
    
    # 랜덤화된 거리
    distance_variation = random.randint(-scroll_config["distance_random"], scroll_config["distance_random"])
    actual_distance = distance + distance_variation if distance > 0 else distance - distance_variation
    
    # 플레이스/지도 영역 감지
    map_bounds = cdp.send("Runtime.evaluate", {
        "expression": """
        (function() {
            // 네이버 플레이스 지도 영역 찾기 (우선순위대로)
            const mapSelectors = [
                '.YXb5L',  // 지도 컨테이너 (height:250px)
                '#loc-main-section-root',  // 플레이스 전체 영역
                'section.sc_new[data-laim-exp-id="loc_plc"]',  // 플레이스 섹션
                '.s_FZx',  // 지도 wrapper
                '[tabindex="0"][style*="height: 250px"]'  // 지도 div
            ];
            
            for (let selector of mapSelectors) {
                const el = document.querySelector(selector);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 100) {
                        return {
                            found: true,
                            left: rect.left,
                            right: rect.right,
                            top: rect.top,
                            bottom: rect.bottom
                        };
                    }
                }
            }
            return { found: false };
        })()
        """,
        "returnByValue": True
    }).get("result", {}).get("value", {"found": False})
    
    # 랜덤화된 Y 위치 (화면 중앙 근처)
    center_y = viewport["height"] // 2
    y = center_y + random.randint(-mouse_random["y_range"], mouse_random["y_range"])
    
    # X 좌표 결정 (지도 영역 회피 - 오른쪽 사용)
    if map_bounds.get("found"):
        map_top = map_bounds.get("top", 0)
        map_bottom = map_bounds.get("bottom", viewport["height"])
        
        # Y가 지도 영역에 걸치면 X를 오른쪽으로
        if map_top <= y <= map_bottom:
            x = random.randint(int(viewport["width"] * 0.85), int(viewport["width"] - 20))
        else:
            # 지도와 Y가 안 겹치면 오른쪽 영역 사용
            x = random.randint(int(viewport["width"] * 0.8), int(viewport["width"] - 20))
    else:
        # 지도 없으면 오른쪽 영역 사용
        x = random.randint(int(viewport["width"] * 0.8), int(viewport["width"] - 20))
    
    # 시각적 피드백
    if show_effect:
        direction = "↓" if actual_distance > 0 else "↑"
        cdp.send("Runtime.evaluate", {
            "expression": f"""
            (function() {{
                const indicator = document.createElement('div');
                indicator.style.cssText = `
                    position:fixed; left:{x-25}px; top:{y-25}px;
                    width:50px; height:50px; 
                    background:rgba(0,100,255,0.3);
                    border:2px solid rgba(0,100,255,0.8);
                    border-radius:50%; z-index:999999;
                    pointer-events:none;
                    display:flex; align-items:center; justify-content:center;
                    font-size:20px; color:rgba(0,100,255,0.8);
                `;
                indicator.textContent = '{direction}';
                document.body.appendChild(indicator);
                setTimeout(() => indicator.remove(), 300);
            }})()
            """
        })
    
    # 마우스 이동 (스크롤 위치로)
    print(f"[마우스 스크롤] 위치: ({x}, {y}), 거리: {actual_distance}px, 방향: {'↓' if actual_distance > 0 else '↑'}")
    
    cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved",
        "x": x,
        "y": y
    })
    time.sleep(0.02)
    
    # 마우스 휠 스크롤 (여러 번 나눠서 자연스럽게)
    steps = scroll_config["steps"]
    delta_per_step = actual_distance / steps
    
    for i in range(steps):
        cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": x,
            "y": y,
            "deltaX": 0,
            "deltaY": delta_per_step
        })
        time.sleep(scroll_config["step_delay"] + random.uniform(-0.005, 0.005))
    
    print(f"[스크롤 완료] {steps}스텝")
    
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


# ============================================
# 페이지 오류 체크
# ============================================
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


# ============================================
# 요소 위치/정보 가져오기
# ============================================
def get_element_bounds(cdp, selector=None, text=None):
    """
    요소의 위치와 크기 가져오기
    
    Args:
        selector: CSS selector
        text: 텍스트로 찾기
    
    Returns:
        {found: bool, x, y, width, height, centerX, centerY}
    """
    if selector:
        js_code = f"""
        (function() {{
            const el = document.querySelector('{selector}');
            if (!el) return {{ found: false }};
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
        }})()
        """
    elif text:
        js_code = f"""
        (function() {{
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null, false
            );
            while (walker.nextNode()) {{
                if (walker.currentNode.textContent.includes('{text}')) {{
                    const range = document.createRange();
                    range.selectNodeContents(walker.currentNode);
                    const rect = range.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {{
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
            }}
            return {{ found: false }};
        }})()
        """
    else:
        return {"found": False}
    
    result = cdp.send("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True
    })
    
    return result.get("result", {}).get("value", {"found": False})


def get_target_position(cdp, target_text):
    """타겟 텍스트의 위치 가져오기"""
    js_code = f"""
    (function() {{
        const elements = document.querySelectorAll('a, button, span, div');
        for (let el of elements) {{
            if (el.textContent.trim() === '{target_text}') {{
                const rect = el.getBoundingClientRect();
                return {{
                    found: true,
                    top: rect.top,
                    bottom: rect.bottom,
                    left: rect.left,
                    right: rect.right,
                    centerX: rect.left + rect.width / 2,
                    centerY: rect.top + rect.height / 2
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


def is_target_visible(position):
    """타겟이 화면 중앙 영역에 보이는지 확인"""
    if not position.get("found"):
        return False
    
    viewport = CONFIG["viewport"]
    visible_top = viewport["height"] * 0.2
    visible_bottom = viewport["height"] * 0.8
    
    center_y = position.get("centerY", 0)
    return visible_top <= center_y <= visible_bottom


# ============================================
# 요소 대기
# ============================================
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
            if bounds.get("found"):
                if after_delay:
                    delay = wait_config["after_found_delay"]
                    delay_random = wait_config["after_found_delay_random"]
                    time.sleep(delay + random.uniform(0, delay_random))
                return {"found": True, "selector": selector, "bounds": bounds}
        
        time.sleep(interval)
    
    return {"found": False, "selector": None, "bounds": None}


def wait_for_element_with_retry(cdp, selectors, timeout=None, interval=None, after_delay=True):
    """
    요소가 나타날 때까지 대기 (30번 x 2회, 메인 재이동 포함)
    페이지 오류 감지시 ERROR 반환
    30번 x 2회 모두 실패 시 ERROR 반환 (종료)
    """
    max_retry = CONFIG["retry"]["max_element_retry"]  # 30
    max_full_retry = CONFIG["retry"]["max_full_retry"]  # 2
    
    for full_round in range(max_full_retry):
        if full_round > 0:
            print(f"\n[요소 대기 재시도 {full_round + 1}/{max_full_retry}] 메인으로 이동 후 다시 시도...")
            cdp.navigate(CONFIG["naver_url"])
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


# ============================================
# 스크롤 위치
# ============================================
def get_scroll_position(cdp):
    """현재 스크롤 Y 위치 가져오기"""
    result = cdp.send("Runtime.evaluate", {
        "expression": "window.scrollY || document.documentElement.scrollTop",
        "returnByValue": True
    })
    return result.get("result", {}).get("value", 0)


# ============================================
# 통합 페이지 웹사이트 영역에서 도메인 찾기
# ============================================
def get_web_domain_links(cdp, domain):
    """
    통합 검색 결과에서 도메인 링크 찾기 (PC 버전)
    - 도메인, 제목, 설명 링크 모두 포함
    - 공통 부모 컨테이너 기준으로 찾기
    - 경로가 포함된 경우 정확한 경로 매칭 (예: skincora.com/coratherapy.php)
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
        const mainLinks = [];
        const debugInfo = {
            totalFound: allLinks.length,
            allHrefs: [],
            excluded: {
                noHref: 0,
                notMatch: 0,
                isSublink: 0,
                notWebArea: 0,
                noSize: 0
            }
        };
        
        allLinks.forEach((link, index) => {
            const href = link.getAttribute('href');
            
            if (!href) {
                debugInfo.excluded.noHref++;
                return;
            }
            
            debugInfo.allHrefs.push(href);
            
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
            
            if (!isMatch) {
                debugInfo.excluded.notMatch++;
                return;
            }
            
            // 서브링크(.sublink) 제외 - 메인 결과의 서브링크는 위치 겹침 문제 있음
            const heatmapTarget = link.getAttribute('data-heatmap-target');
            if (heatmapTarget === '.sublink') {
                debugInfo.excluded.isSublink++;
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
            
            if (!isWebArea) {
                debugInfo.excluded.notWebArea++;
                return;
            }
            
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
                    centerY: rect.top + rect.height / 2,
                    heatmapTarget: heatmapTarget || ''
                });
            } else {
                debugInfo.excluded.noSize++;
            }
        });
        
        return {
            found: mainLinks.length > 0,
            links: mainLinks,
            count: mainLinks.length,
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
    for i, href in enumerate(all_hrefs[:10]):
        print(f"  [{i+1}] {href}")
    if len(all_hrefs) > 10:
        print(f"  ... 외 {len(all_hrefs) - 10}개")
    
    # 제외 통계
    excluded = debug.get('excluded', {})
    print(f"\n[도메인 검색] 제외 통계:")
    print(f"  - noHref: {excluded.get('noHref', 0)}")
    print(f"  - notMatch: {excluded.get('notMatch', 0)}")
    print(f"  - isSublink: {excluded.get('isSublink', 0)}")
    print(f"  - notWebArea: {excluded.get('notWebArea', 0)}")
    print(f"  - noSize: {excluded.get('noSize', 0)}")
    
    # 최종 매칭된 링크
    print(f"\n[도메인 검색] ✅ 최종 매칭 링크: {data.get('count', 0)}개")
    for i, link in enumerate(data.get('links', [])):
        print(f"  [{i+1}] href={link.get('href', '')}")
        print(f"      x={link.get('x', 0):.0f}, y={link.get('y', 0):.0f}, w={link.get('width', 0):.0f}, h={link.get('height', 0):.0f}")
    
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


def get_tab_count(cdp):
    """현재 열린 탭 개수 가져오기"""
    try:
        result = cdp.send("Target.getTargets", {})
        targets = result.get("targetInfos", [])
        # type이 "page"인 것만 카운트 (탭)
        page_count = sum(1 for t in targets if t.get("type") == "page")
        return page_count
    except:
        return -1


def click_web_domain_link(cdp, domain):
    """
    통합 페이지 웹사이트 영역에서 도메인 링크를 찾아 랜덤 클릭
    클릭 후 URL 변경 확인, 안 됐으면 다른 링크로 재시도 (최대 3회)
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
                do_mouse_scroll(cdp, extra_scroll)
                time.sleep(random.uniform(0.3, 0.5))
                
                # 스크롤 후 다시 위치 확인
                web_links = get_web_domain_links(cdp, domain)
                visible_links = []
                for link in web_links["links"]:
                    if visible_top <= link["centerY"] <= visible_bottom:
                        visible_links.append(link)
                
                if visible_links:
                    print(f"[통합] 웹사이트 영역에서 {domain} 발견! {len(visible_links)}개 링크 (스크롤 {scroll_count}회)")
                    
                    # 클릭 전 URL 저장 (현재 탭에서 이동 확인용)
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
                        
                        print(f"[클릭 시도 {click_attempt + 1}/3] 좌표 x: {x:.1f}, y: {y:.1f}")
                        do_mouse_click(cdp, x, y)
                        
                        # 3초 대기 후 URL 변경 확인 (현재 탭에서 이동)
                        time.sleep(3)
                        after_url = get_current_url(cdp)
                        
                        if after_url != before_url:
                            print(f"[성공] 페이지 이동 완료!")
                            return True
                        else:
                            print(f"[재시도] 페이지 이동 안 됨, 다른 링크 시도...")
                    
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
            do_mouse_scroll(cdp, scroll_distance)
            time.sleep(0.3)
            after_scroll = get_scroll_position(cdp)
            scroll_count += 1
        else:
            # 링크 없음 → 아래로 스크롤
            before_scroll = get_scroll_position(cdp)
            do_mouse_scroll(cdp, scroll_config["distance"])
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


# ============================================
# 더보기 페이지에서 도메인 찾기
# ============================================
def get_all_domain_links(cdp, domain):
    """
    더보기 페이지에서 도메인 링크 가져오기
    - 도메인, 제목, 설명 링크 모두 포함
    - 공통 부모 컨테이너 기준으로 찾기
    - 경로가 포함된 경우 정확한 경로 매칭 (예: skincora.com/coratherapy.php)
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


def click_domain_link(cdp, domain):
    """
    도메인 메인 링크를 스크롤로 찾아가서 랜덤 클릭
    """
    viewport = CONFIG["viewport"]
    scroll_config = CONFIG["scroll"]
    max_scrolls = CONFIG["max_scrolls"]
    
    visible_top = viewport["height"] * 0.2
    visible_bottom = viewport["height"] * 0.8
    
    scroll_count = 0
    same_position_count = 0
    
    while scroll_count < max_scrolls:
        # 도메인 링크 찾기
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
                do_mouse_scroll(cdp, extra_scroll)
                time.sleep(random.uniform(0.3, 0.5))
                
                # 스크롤 후 다시 위치 확인
                all_links = get_all_domain_links(cdp, domain)
                visible_links = []
                for link in all_links["links"]:
                    if visible_top <= link["centerY"] <= visible_bottom:
                        visible_links.append(link)
                
                if visible_links:
                    print(f"[발견] {domain} 링크! 화면에 보이는 {len(visible_links)}개 링크")
                    
                    # 클릭 전 URL 저장 (현재 탭에서 이동 확인용)
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
                        
                        print(f"[클릭 시도 {click_attempt + 1}/3] 좌표 x: {x:.1f}, y: {y:.1f}")
                        do_mouse_click(cdp, x, y)
                        
                        # 3초 대기 후 URL 변경 확인 (현재 탭에서 이동)
                        time.sleep(3)
                        after_url = get_current_url(cdp)
                        
                        if after_url != before_url:
                            print(f"[성공] 페이지 이동 완료!")
                            return True
                        else:
                            print(f"[재시도] 페이지 이동 안 됨, 다른 링크 시도...")
                    
                    # 3회 모두 실패
                    print(f"[실패] 3회 클릭 시도 모두 실패")
                    return False
            
            # 링크는 있지만 화면 밖 → 스크롤
            first_link = all_links["links"][0]
            link_center_y = first_link["centerY"]
            
            if link_center_y > visible_bottom:
                scroll_distance = scroll_config["distance"] + random.uniform(-scroll_config["distance_random"], scroll_config["distance_random"])
            else:
                scroll_distance = -(scroll_config["distance"] + random.uniform(-scroll_config["distance_random"], scroll_config["distance_random"]))
            
            before_scroll = get_scroll_position(cdp)
            do_mouse_scroll(cdp, scroll_distance)
            time.sleep(0.1)
            after_scroll = get_scroll_position(cdp)
            
            scroll_count += 1
        else:
            # 링크 없음 → 아래로 스크롤
            before_scroll = get_scroll_position(cdp)
            do_mouse_scroll(cdp, scroll_config["distance"])
            time.sleep(0.1)
            after_scroll = get_scroll_position(cdp)
            
            scroll_count += 1
        
        # 페이지 끝 감지
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


def mouse_click_element(cdp, selector=None, text=None, random_offset=True):
    """요소를 찾아서 마우스 클릭"""
    bounds = get_element_bounds(cdp, selector=selector, text=text)
    
    if not bounds.get("found"):
        return False
    
    if random_offset:
        x = bounds["x"] + random.uniform(bounds["width"] * 0.2, bounds["width"] * 0.8)
        y = bounds["y"] + random.uniform(bounds["height"] * 0.2, bounds["height"] * 0.8)
    else:
        x = bounds["centerX"]
        y = bounds["centerY"]
    
    do_mouse_click(cdp, x, y)
    return True


# ============================================
# 검색 프로세스 (1~7단계)
# ============================================
def run_search_process(cdp, search_keyword, target_domain, search_in_total, go_to_more=True, start_mode="new", is_last=False):
    """
    검색 프로세스 1~7단계 실행
    
    Args:
        start_mode: "new"=네이버 메인부터, "continue"=현재 페이지에서 검색
    
    Returns:
        "DONE": 성공 (+ 새 CDP 객체 반환 필요시 튜플)
        "RETRY": 재시도 필요
        "ERROR": 페이지 오류 → 종료
        "NOTFOUND": 도메인 못 찾음 → 종료
    """
    global current_cdp  # 탭 전환 후 CDP 객체 업데이트용
    
    viewport = CONFIG["viewport"]
    
    # 현재 탭 ID 저장 (나중에 복귀용)
    tabs = get_all_tabs()
    original_tab_id = None
    if tabs:
        # 현재 연결된 탭 찾기 (가장 최근 활성 탭)
        for tab in tabs:
            if "search.naver.com" in tab.get("url", "") or "naver.com" in tab.get("url", ""):
                original_tab_id = tab.get("id")
                break
        if not original_tab_id and tabs:
            original_tab_id = tabs[0].get("id")
    
    print(f"[탭 저장] 원래 탭 ID: {original_tab_id}")
    
    # ========================================
    # 1단계: 네이버 이동 (start_mode에 따라)
    # ========================================
    if start_mode == "new":
        print("\n[1단계] 네이버 PC 메인 이동...")
        cdp.navigate(CONFIG["naver_url"])
        
        # 페이지 로딩 완료 대기 (무조건 10초)
        print("[대기] 페이지 로딩 대기 10초...")
        time.sleep(10)
        print("[로딩 완료]")
    else:
        print("\n[1단계] continue 모드 - 현재 페이지에서 시작")
        # 검색창 초기화를 위해 잠시 대기
        time.sleep(random.uniform(0.3, 0.5))
    
    # ========================================
    # 2단계: 검색창 클릭 + 검색어 입력
    # ========================================
    print("\n[2단계] 검색창 클릭 및 검색어 입력...")
    
    # continue 모드일 때는 검색창 selector가 다름 (더보기 페이지 = nx_query)
    if start_mode == "continue":
        search_selectors = CONFIG["selectors"]["search_more"] + CONFIG["selectors"]["search_input"]
    else:
        search_selectors = CONFIG["selectors"]["search_input"]
    
    max_click_retry = CONFIG["retry"]["max_element_retry"]
    clicks_before_reload = 5
    
    search_input_success = False
    click_retry = 0
    
    while click_retry < max_click_retry:
        click_retry += 1
        
        # 5번마다 메인 재이동 (continue 모드에서도)
        if click_retry > 1 and (click_retry - 1) % clicks_before_reload == 0:
            print(f"[재이동] {clicks_before_reload}번 시도 실패, 네이버 메인으로 다시 이동...")
            cdp.navigate(CONFIG["naver_url"])
            time.sleep(CONFIG["retry"]["after_refresh_delay"])
            search_selectors = CONFIG["selectors"]["search_input"]  # 메인으로 갔으니 원래 selector로
        
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
        
        # 검색창 클릭
        click_x = bounds["centerX"] + random.uniform(-bounds["width"]*0.3, bounds["width"]*0.3)
        click_y = bounds["centerY"] + random.uniform(-bounds["height"]*0.2, bounds["height"]*0.2)
        do_mouse_click(cdp, click_x, click_y)
        
        print(f"[클릭 {click_retry}/{max_click_retry}] 검색창 클릭 완료")
        time.sleep(0.3)
        
        # continue 모드일 때 기존 텍스트 삭제 (트리플 클릭으로 전체선택)
        if start_mode == "continue":
            print("[검색창 초기화] 트리플 클릭으로 전체 선택...")
            
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
                    # 트리플 클릭
                    do_triple_click(cdp, select_x, select_y)
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
        
        # 검색어 입력
        cdp.type_text(search_keyword)
        search_input_success = True
        break
    
    if not search_input_success:
        print(f"[실패] 검색창 클릭 {max_click_retry}번 실패")
        return "RETRY"
    
    time.sleep(random.uniform(0.3, 0.5))
    
    # ========================================
    # 3단계: 검색 실행 (엔터 또는 돋보기 랜덤)
    # ========================================
    search_mode = CONFIG["search_mode"]
    if search_mode == 3:
        search_mode = random.choice([1, 2])
    
    mode_name = "엔터" if search_mode == 1 else "돋보기"
    print(f"\n[3단계] 검색 실행... (모드: {mode_name})")
    
    if search_mode == 1:
        cdp.press_enter()
    else:
        # continue 모드일 때는 더보기 페이지용 돋보기 셀렉터 사용
        if start_mode == "continue":
            btn_selectors = CONFIG["selectors"]["search_button_more"]
        else:
            btn_selectors = CONFIG["selectors"]["search_button"]
        
        btn_clicked = False
        for selector in btn_selectors:
            bounds = get_element_bounds(cdp, selector=selector)
            print(f"[돋보기] {selector} 찾기: {bounds.get('found')}")
            if bounds.get("found"):
                click_x = bounds["centerX"] + random.uniform(-5, 5)
                click_y = bounds["centerY"] + random.uniform(-3, 3)
                print(f"[돋보기] 클릭 좌표: x={click_x:.1f}, y={click_y:.1f}")
                do_mouse_click(cdp, click_x, click_y)
                btn_clicked = True
                break
        
        if not btn_clicked:
            print("[돋보기] 버튼 못 찾음, 엔터로 대체")
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
    found_in_total = False  # 통합에서 찾았는지
    
    if search_in_total:
        print(f"\n[4.5단계] 통합 페이지에서 '{target_domain}' 웹사이트 영역 찾기...")
        
        if click_web_domain_link(cdp, target_domain):
            print(f"[성공] 통합 페이지에서 {target_domain} 클릭 완료!")
            found_in_total = True
            
            # === 8단계: 타겟 사이트 체류 ===
            print("\n[8단계] 타겟 사이트 체류 중...")
            
            # 페이지 로딩 대기 (현재 탭에서 이동하므로)
            time.sleep(random.uniform(2.0, 3.0))
            
            # 체류 시간 (10~20초)
            stay_time = random.uniform(RANDOM_OPTIONS["stay_min"], RANDOM_OPTIONS["stay_max"])
            print(f"[체류] {stay_time:.1f}초 대기...")
            time.sleep(stay_time)
            
            # 마지막 키워드가 아니면 뒤로가기로 복귀
            if not is_last:
                print("\n[9단계] 뒤로가기로 검색 결과 복귀...")
                cdp.send("Runtime.evaluate", {"expression": "history.back()"})
                time.sleep(random.uniform(1.5, 2.5))
                print("[복귀 완료] 검색 결과 페이지로 돌아옴")
            else:
                print("\n[9단계] 마지막 키워드 - 복귀 생략")
            
            return "DONE"
        else:
            if go_to_more:
                print(f"[결과] 통합 페이지에 {target_domain} 없음, 더보기로 이동...")
            else:
                print(f"[결과] 통합 페이지에 {target_domain} 없음 (더보기 이동 OFF)")
                return "NOTFOUND"
    
    # 더보기로 이동 안 하는 경우
    if not go_to_more and not found_in_total:
        print(f"[종료] go_to_more=False, 더보기 이동 안 함")
        return "NOTFOUND"
    
    # 통합에서 이미 찾았으면 5,6,7단계 스킵하고 바로 8,9단계로
    domain_found = found_in_total  # 통합에서 찾았으면 이미 True
    
    if not found_in_total:
        # ========================================
        # 5단계: 검색결과 더보기까지 스크롤
        # ========================================
        print(f"\n[5단계] '{CONFIG['target_text']}' 까지 스크롤...")
        
        step5_full_retry = CONFIG["retry"]["step5_full_retry"]
        step5_success = False
        
        for step5_round in range(step5_full_retry + 1):
            if step5_round > 0:
                print(f"\n[5단계 재시도 {step5_round}/{step5_full_retry}] 처음부터 다시 시도 필요...")
                return "RETRY"
            
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
                    do_mouse_scroll(cdp, -CONFIG["scroll"]["distance"])
                else:
                    do_mouse_scroll(cdp, CONFIG["scroll"]["distance"])
                
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
            
            if mouse_click_element(cdp, text=CONFIG["target_text"], random_offset=True):
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
                        mouse_click_element(cdp, text=CONFIG["target_text"], random_offset=True)
                
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
                            do_mouse_click(cdp, click_x, click_y)
                            page_btn_found = True
                            time.sleep(random.uniform(1.5, 2.0))
                            break
                        else:
                            if btn_center_y > visible_bottom:
                                do_mouse_scroll(cdp, CONFIG["scroll"]["distance"])
                            else:
                                do_mouse_scroll(cdp, -CONFIG["scroll"]["distance"])
                            scroll_try += 1
                            time.sleep(0.2)
                    else:
                        do_mouse_scroll(cdp, CONFIG["scroll"]["distance"])
                        scroll_try += 1
                        time.sleep(0.2)
                
                if not page_btn_found:
                    break
    
    # 통합 또는 더보기에서 찾았는지 확인
    if found_in_total or domain_found:
        # ========================================
        # 8단계: 타겟 사이트 체류
        # ========================================
        print("\n[8단계] 타겟 사이트 체류 중...")
        
        # 페이지 로딩 대기 (현재 탭에서 이동하므로)
        time.sleep(random.uniform(2.0, 3.0))
        
        # 체류 시간 (10~20초)
        stay_time = random.uniform(RANDOM_OPTIONS["stay_min"], RANDOM_OPTIONS["stay_max"])
        print(f"[체류] {stay_time:.1f}초 대기...")
        time.sleep(stay_time)
        
        # 마지막 키워드가 아니면 뒤로가기로 검색 결과 복귀
        if not is_last:
            print("\n[9단계] 뒤로가기로 검색 결과 복귀...")
            cdp.send("Runtime.evaluate", {"expression": "history.back()"})
            time.sleep(random.uniform(1.5, 2.5))
            print("[복귀 완료] 검색 결과 페이지로 돌아옴")
        else:
            print("\n[9단계] 마지막 키워드 - 복귀 생략")
        
        return "DONE"
    else:
        return "NOTFOUND"


# 전역 CDP 객체 (탭 전환 시 업데이트)
current_cdp = None


# ============================================
# 메인
# ============================================
def main():
    if len(sys.argv) < 3:
        print("사용법: python cdp_pc_scroll.py 검색어 도메인 [검색모드] [시작모드] [마지막]")
        print("예시: python cdp_pc_scroll.py 곤지암스키강습 sidecut.co.kr")
        print("예시: python cdp_pc_scroll.py 곤지암스키강습 sidecut.co.kr total  (통합에서만)")
        print("예시: python cdp_pc_scroll.py 곤지암스키강습 sidecut.co.kr more   (더보기에서)")
        print("예시: python cdp_pc_scroll.py 곤지암스키강습 sidecut.co.kr more auto  (자동감지)")
        print("예시: python cdp_pc_scroll.py 곤지암스키강습 sidecut.co.kr more auto 1  (마지막 키워드)")
        print("")
        print("[검색모드] total=통합에서만 찾기, more=더보기에서 찾기, both=통합먼저→더보기 (기본값)")
        print("[시작모드] new=네이버 메인부터, continue=현재페이지에서, auto=자동감지 (기본값)")
        print("[마지막] 0=중간 키워드, 1=마지막 키워드 (탭 닫기 안 함)")
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
    print("[CDP 네이버 PC 검색]")
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
    
    global current_cdp
    cdp = CDP(ws_url)
    current_cdp = cdp
    
    try:
        # ========================================
        # UA 로드 및 에뮬레이션 설정
        # ========================================
        browser_name, ua = load_ua_from_file("random")
        
        if not ua:
            browser_type = random.choices(
                ["chrome", "edge", "opera", "firefox"],
                weights=RANDOM_OPTIONS["browser_weights"]
            )[0]
            browser_name = browser_type.capitalize()
            ua = get_default_ua(browser_type)
            print(f"[UA] 기본 UA 사용: {browser_name}")
        
        # 해상도 랜덤 선택
        preset = select_random_preset()
        screen_w, screen_h = map(int, preset["screen"].split("x"))
        inner_w, inner_h, window_type = calc_inner_size(screen_w, screen_h)
        dpr = preset["dpr"]
        memory = random.choice(RANDOM_OPTIONS["memory_options"])
        
        preset_info = {
            "screen_w": screen_w,
            "screen_h": screen_h,
            "inner_w": inner_w,
            "inner_h": inner_h,
            "dpr": dpr,
            "memory": memory,
            "window_type": window_type,
        }
        
        # PC 에뮬레이션 설정 (fingerprint 스푸핑 포함)
        setup_pc_emulation(cdp, ua, preset_info)
        
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
            
            # current_cdp 사용 (탭 전환 시 업데이트됨)
            result = run_search_process(current_cdp, search_keyword, target_domain, search_in_total, go_to_more, start_mode, is_last)
            
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
        if RANDOM_OPTIONS.get("close_browser_on_finish", False):
            try:
                print("\n[브라우저 종료] 크롬 브라우저를 종료합니다...")
                cdp.send("Browser.close")
            except:
                pass
        cdp.close()


if __name__ == "__main__":
    main()