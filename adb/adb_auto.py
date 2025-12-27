#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeeLark ADB 네이버 검색 자동화 v3
CDP 스크롤 계산 + ADB 실행 통합 버전

사용법: python adb_auto_cdp.py 검색어 도메인 [검색모드] [폰번호] [마지막]
"""

import subprocess
import time
import random
import sys
import re
import json

# CDP 관련 (선택적)
try:
    import requests
    import websocket
    CDP_AVAILABLE = True
except ImportError:
    CDP_AVAILABLE = False

from config import (
    PHONES, ADB_CONFIG, NAVER_CONFIG, 
    SCROLL_CONFIG, TOUCH_CONFIG, TYPING_CONFIG, WAIT_CONFIG,
    COORDINATES, SELECTORS, READING_PAUSE_CONFIG, KEYBOARD_LAYOUT
)


def log(message, level="INFO"):
    print(f"[{level}] {message}")


def random_delay(min_sec, max_sec):
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


# ============================================
# CDP 스크롤 계산기 (선택적 사용)
# ============================================
class CDPCalculator:
    """PC 크롬에서 스크롤 위치를 미리 계산"""
    
    def __init__(self, port=9222):
        self.port = port
        self.ws = None
        self.msg_id = 0
        self.connected = False
    
    def connect(self):
        """CDP 연결"""
        if not CDP_AVAILABLE:
            log("[CDP] requests/websocket 모듈 없음, CDP 계산 비활성화")
            return False
        
        try:
            response = requests.get(f"http://localhost:{self.port}/json", timeout=3)
            tabs = response.json()
            
            ws_url = None
            for tab in tabs:
                if tab.get("type") == "page":
                    ws_url = tab["webSocketDebuggerUrl"]
                    break
            
            if not ws_url:
                log("[CDP] 탭을 찾을 수 없음")
                return False
            
            self.ws = websocket.create_connection(ws_url, timeout=5)
            self.connected = True
            log("[CDP] 연결 성공!")
            return True
            
        except Exception as e:
            log(f"[CDP] 연결 실패: {e}")
            log("[CDP] 크롬이 --remote-debugging-port=9222 로 실행되었는지 확인")
            return False
    
    def send(self, method, params=None):
        """CDP 명령 전송"""
        if not self.connected:
            return {}
        
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") == self.msg_id:
                return response.get("result", {})
    
    def set_viewport(self, width, height):
        """뷰포트 크기 설정 (모바일과 동일하게)"""
        # Page, Network 도메인 활성화
        self.send("Page.enable", {})
        self.send("Network.enable", {})
        
        # UA 모바일로 설정
        self.send("Emulation.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "acceptLanguage": "ko-KR,ko;q=0.9",
            "platform": "Linux armv81"
        })
        
        # 모바일과 동일한 뷰포트 설정
        self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 2,
            "mobile": True,
            "screenWidth": width,
            "screenHeight": height
        })
        
        self.target_width = width
        self.target_height = height
        
        log(f"[CDP] 뷰포트: {width}x{height} (모바일과 동일)")
    
    def navigate(self, url):
        """페이지 이동"""
        self.send("Page.navigate", {"url": url})
        time.sleep(3)
    
    def evaluate(self, expression):
        """JS 실행"""
        result = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")
    
    def get_viewport_height(self):
        """뷰포트 높이"""
        return self.evaluate("window.innerHeight") or 0
    
    def get_element_y(self, text):
        """텍스트로 요소 Y 좌표 찾기"""
        js = f"""
        (function() {{
            const elements = [...document.querySelectorAll('*')];
            for (const el of elements) {{
                const txt = el.textContent.trim();
                if (txt.includes('{text}') && txt.length < 30) {{
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0 && rect.height < 100) {{
                        return {{
                            found: true,
                            y: rect.top + window.scrollY,
                            screenY: rect.top
                        }};
                    }}
                }}
            }}
            return {{ found: false }};
        }})()
        """
        return self.evaluate(js)
    
    def get_domain_y(self, domain):
        """도메인 링크 Y 좌표 찾기"""
        js = f"""
        (function() {{
            const links = document.querySelectorAll('a[href*="{domain}"]');
            for (const link of links) {{
                const rect = link.getBoundingClientRect();
                if (rect.height > 0) {{
                    return {{
                        found: true,
                        y: rect.top + window.scrollY,
                        screenY: rect.top
                    }};
                }}
            }}
            return {{ found: false }};
        }})()
        """
        return self.evaluate(js)
    
    def scroll_to(self, y):
        """스크롤 이동"""
        self.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(0.5)
    
    def click(self, x, y):
        """터치 클릭"""
        self.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": x, "y": y, "radiusX": 5, "radiusY": 5, "force": 0.5}]
        })
        time.sleep(0.05)
        self.send("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": []
        })
    
    def click_element_by_text(self, text):
        """텍스트로 요소 찾아서 클릭"""
        js = f"""
        (function() {{
            const elements = [...document.querySelectorAll('*')];
            for (const el of elements) {{
                const txt = el.textContent.trim();
                if (txt === '{text}' || (txt.includes('{text}') && txt.length < 30)) {{
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0 && rect.height < 100) {{
                        return {{
                            found: true,
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2
                        }};
                    }}
                }}
            }}
            return {{ found: false }};
        }})()
        """
        result = self.evaluate(js)
        
        if result and result.get("found"):
            self.click(result["x"], result["y"])
            return True
        return False
    
    def calculate_scroll_info(self, keyword, domain, screen_width, screen_height):
        """검색어로 스크롤 정보 미리 계산 (모바일과 동일 뷰포트)"""
        log("[CDP] 스크롤 위치 계산 시작...")
        
        result = {
            "more_scroll_count": 0,
            "domain_scroll_count": -1,
            "calculated": False
        }
        
        if not self.connected:
            return result
        
        try:
            # 모바일과 동일한 뷰포트 설정
            self.set_viewport(screen_width, screen_height)
            
            # 1. 통합 검색 페이지
            search_url = f"https://m.search.naver.com/search.naver?query={keyword}"
            self.navigate(search_url)
            time.sleep(3)
            
            # 실제 뷰포트 확인
            cdp_viewport_h = self.get_viewport_height()
            log(f"[CDP] 실제 뷰포트: {cdp_viewport_h}px")
            
            # ADB 스크롤 1회 거리
            scroll_distance = SCROLL_CONFIG.get("distance", 400)
            
            # "검색결과 더보기" 위치 계산
            more_info = self.get_element_y("검색결과 더보기")
            
            if more_info and more_info.get("found"):
                more_y = more_info["y"]
                # 화면 중앙까지 스크롤 (비율 계산 없이 직접 사용)
                scroll_needed = more_y - (screen_height * 0.5)
                result["more_scroll_count"] = max(1, int(scroll_needed / scroll_distance) + 3)
                
                log(f"[CDP] '검색결과 더보기' Y={more_y:.0f}")
                log(f"[CDP] 스크롤 필요={scroll_needed:.0f}px, 횟수={result['more_scroll_count']}번")
            else:
                log("[CDP] '검색결과 더보기' 못 찾음, 기본값 사용")
                result["more_scroll_count"] = 40
            
            # 2. 더보기 페이지 URL로 직접 이동
            import urllib.parse
            encoded_keyword = urllib.parse.quote(keyword)
            more_page_url = f"https://m.search.naver.com/search.naver?where=m_web&query={encoded_keyword}&sm=mtb_pge&start=1"
            
            log(f"[CDP] 더보기 페이지 이동...")
            self.navigate(more_page_url)
            time.sleep(3)
            
            # 도메인 위치 계산
            domain_info = self.get_domain_y(domain)
            
            if domain_info and domain_info.get("found"):
                domain_y = domain_info["y"]
                scroll_needed = domain_y - (screen_height * 0.5)
                result["domain_scroll_count"] = max(0, int(scroll_needed / scroll_distance) + 3)
                
                log(f"[CDP] '{domain}' Y={domain_y:.0f}")
                log(f"[CDP] 스크롤 필요={scroll_needed:.0f}px, 횟수={result['domain_scroll_count']}번")
            else:
                log(f"[CDP] '{domain}' 1페이지에 없음, 스크롤하며 찾기")
                result["domain_scroll_count"] = -1
            
            result["calculated"] = True
            log("[CDP] 계산 완료!")
            
        except Exception as e:
            log(f"[CDP] 계산 오류: {e}")
        
        return result
    
    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.connected = False


class ADBController:
    def __init__(self, phone_config):
        self.adb_path = ADB_CONFIG["adb_path"]
        self.adb_address = phone_config["adb_address"]
        self.login_code = phone_config.get("login_code", "")
        self.screen_width = phone_config.get("screen_width", 720)
        self.screen_height = phone_config.get("screen_height", 1440)
        self._last_xml = None
        self._last_xml_time = 0
    
    def run_adb(self, command, timeout=None):
        timeout = timeout or ADB_CONFIG["command_timeout"]
        full_command = f'{self.adb_path} -s {self.adb_address} {command}'
        try:
            result = subprocess.run(
                full_command, shell=True, capture_output=True,
                timeout=timeout, encoding='utf-8', errors='ignore'
            )
            return result.stdout.strip() if result.stdout else ""
        except Exception as e:
            log(f"ADB 실행 실패: {e}", "ERROR")
            return None
    
    def shell(self, command):
        return self.run_adb(f'shell {command}')
    
    # ──────────────────────────────────────────
    # 연결
    # ──────────────────────────────────────────
    def connect(self):
        log(f"ADB 연결 시도: {self.adb_address}")
        result = self.run_adb(f"connect {self.adb_address}")
        
        if result and ("connected" in result.lower() or "already" in result.lower()):
            log("ADB 연결 성공!")
            if self.login_code:
                log(f"GeeLark 로그인: {self.login_code}")
                self.shell(f"glogin {self.login_code}")
                time.sleep(1)
            return True
        log(f"ADB 연결 실패: {result}", "ERROR")
        return False
    
    # ──────────────────────────────────────────
    # 터치
    # ──────────────────────────────────────────
    def tap(self, x, y, randomize=True):
        if randomize:
            x += random.randint(-TOUCH_CONFIG["tap_random_x"], TOUCH_CONFIG["tap_random_x"])
            y += random.randint(-TOUCH_CONFIG["tap_random_y"], TOUCH_CONFIG["tap_random_y"])
        x = max(0, min(int(x), self.screen_width))
        y = max(0, min(int(y), self.screen_height))
        log(f"탭: ({x}, {y})")
        self.shell(f"input tap {x} {y}")
        random_delay(TOUCH_CONFIG["after_tap_delay_min"], TOUCH_CONFIG["after_tap_delay_max"])
    
    def tap_element(self, element):
        """요소 내 랜덤 위치 클릭 (CDP 스타일)"""
        if not element or not element.get("found"):
            return False
        
        bounds = element.get("bounds")
        if not bounds:
            return False
        
        x1, y1, x2, y2 = bounds
        
        # bounds 유효성 검사
        if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
            log("[경고] bounds 무효 [0,0][0,0]")
            return False
        
        # 요소 내부 랜덤 좌표 (가장자리 15% 제외)
        margin_x = max(2, int((x2 - x1) * 0.15))
        margin_y = max(2, int((y2 - y1) * 0.15))
        
        x = random.randint(x1 + margin_x, max(x1 + margin_x, x2 - margin_x))
        y = random.randint(y1 + margin_y, max(y1 + margin_y, y2 - margin_y))
        
        log(f"요소 탭: [{x1},{y1}][{x2},{y2}] → ({x}, {y})")
        self.tap(x, y, randomize=False)
        return True
    
    def swipe(self, x1, y1, x2, y2, duration_ms=None):
        if duration_ms is None:
            duration_ms = random.randint(SCROLL_CONFIG["duration_min"], SCROLL_CONFIG["duration_max"])
        log(f"스와이프: ({int(x1)}, {int(y1)}) → ({int(x2)}, {int(y2)}), {duration_ms}ms")
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {duration_ms}")
    
    def scroll_down(self, distance=None):
        """아래로 스크롤 (컨텐츠가 위로 올라감 = 아래 내용 보기)"""
        if distance is None:
            distance = SCROLL_CONFIG["distance"] + random.randint(
                -SCROLL_CONFIG["distance_random"], SCROLL_CONFIG["distance_random"])
        
        x = COORDINATES["scroll_x"] + random.randint(-30, 30)
        start_y = COORDINATES["scroll_start_y"]  # 1100
        end_y = start_y - distance  # 700쯤 (위로 스와이프)
        
        self.swipe(x, start_y, x, end_y)
        
        # 읽기 멈춤 (확률적)
        if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
            pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
            log(f"읽기 멈춤: {pause:.1f}초")
            time.sleep(pause)
    
    def scroll_up(self, distance=None):
        """위로 스크롤 (컨텐츠가 아래로 내려감 = 위 내용 보기)"""
        if distance is None:
            distance = SCROLL_CONFIG["distance"] + random.randint(
                -SCROLL_CONFIG["distance_random"], SCROLL_CONFIG["distance_random"])
        
        x = COORDINATES["scroll_x"] + random.randint(-30, 30)
        start_y = COORDINATES["scroll_end_y"]  # 400
        end_y = start_y + distance  # 800쯤 (아래로 스와이프)
        
        self.swipe(x, start_y, x, end_y)
    
    # ──────────────────────────────────────────
    # 키 입력
    # ──────────────────────────────────────────
    def press_enter(self):
        log("엔터 키")
        self.shell("input keyevent 66")
        random_delay(0.3, 0.6)
    
    def press_back(self):
        log("뒤로가기")
        self.shell("input keyevent 4")
        random_delay(0.5, 1.0)
    
    # ──────────────────────────────────────────
    # 한글 키보드 입력
    # ──────────────────────────────────────────
    def input_text(self, text):
        """텍스트 입력 - 가상 키보드 탭 방식"""
        log(f"텍스트 입력: {text}")
        
        has_korean = any('\uac00' <= c <= '\ud7a3' or '\u3131' <= c <= '\u3163' for c in text)
        
        if has_korean:
            return self.input_korean_keyboard(text)
        else:
            escaped = text.replace(' ', '%s').replace('&', '\\&')
            self.shell(f'input text "{escaped}"')
            random_delay(TYPING_CONFIG["after_typing_delay_min"], TYPING_CONFIG["after_typing_delay_max"])
            return True
    
    def input_korean_keyboard(self, text):
        """한글 키보드 자판 탭으로 입력"""
        log(f"한글 키보드 입력: {text}")
        
        jamos = self._decompose_korean(text)
        log(f"자모 분리: {''.join(jamos)}")
        
        for jamo in jamos:
            if jamo == ' ':
                self._tap_key('space')
            elif jamo in KEYBOARD_LAYOUT:
                self._tap_key(jamo)
            else:
                log(f"[경고] 키보드에 없는 문자: {jamo}")
            
            time.sleep(random.uniform(0.08, 0.18))
        
        random_delay(0.3, 0.5)
        return True
    
    def _decompose_korean(self, text):
        """한글을 자모로 분리"""
        result = []
        
        CHOSUNG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        JUNGSUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
        JONGSUNG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        
        COMPLEX_VOWEL = {
            'ㅘ': ['ㅗ', 'ㅏ'], 'ㅙ': ['ㅗ', 'ㅐ'], 'ㅚ': ['ㅗ', 'ㅣ'],
            'ㅝ': ['ㅜ', 'ㅓ'], 'ㅞ': ['ㅜ', 'ㅔ'], 'ㅟ': ['ㅜ', 'ㅣ'],
            'ㅢ': ['ㅡ', 'ㅣ'], 'ㅒ': ['ㅑ', 'ㅣ'], 'ㅖ': ['ㅕ', 'ㅣ'],
        }
        
        COMPLEX_JONG = {
            'ㄳ': ['ㄱ', 'ㅅ'], 'ㄵ': ['ㄴ', 'ㅈ'], 'ㄶ': ['ㄴ', 'ㅎ'],
            'ㄺ': ['ㄹ', 'ㄱ'], 'ㄻ': ['ㄹ', 'ㅁ'], 'ㄼ': ['ㄹ', 'ㅂ'],
            'ㄽ': ['ㄹ', 'ㅅ'], 'ㄾ': ['ㄹ', 'ㅌ'], 'ㄿ': ['ㄹ', 'ㅍ'],
            'ㅀ': ['ㄹ', 'ㅎ'], 'ㅄ': ['ㅂ', 'ㅅ'],
        }
        
        for char in text:
            if '\uac00' <= char <= '\ud7a3':
                code = ord(char) - 0xAC00
                cho = code // 588
                jung = (code % 588) // 28
                jong = code % 28
                
                result.append(CHOSUNG[cho])
                
                vowel = JUNGSUNG[jung]
                if vowel in COMPLEX_VOWEL:
                    result.extend(COMPLEX_VOWEL[vowel])
                else:
                    result.append(vowel)
                
                if jong > 0:
                    jongchar = JONGSUNG[jong]
                    if jongchar in COMPLEX_JONG:
                        result.extend(COMPLEX_JONG[jongchar])
                    else:
                        result.append(jongchar)
            elif '\u3131' <= char <= '\u3163':
                result.append(char)
            else:
                result.append(char)
        
        return result
    
    def _tap_key(self, key):
        """키보드 키 탭"""
        if key not in KEYBOARD_LAYOUT:
            log(f"[경고] 키 없음: {key}")
            return
        
        coords = KEYBOARD_LAYOUT[key]
        
        if coords.get('shift'):
            shift_coords = KEYBOARD_LAYOUT['shift']
            sx = shift_coords['x'] + random.randint(-5, 5)
            sy = shift_coords['y'] + random.randint(-3, 3)
            self.shell(f"input tap {sx} {sy}")
            time.sleep(random.uniform(0.05, 0.1))
        
        x = coords['x'] + random.randint(-8, 8)
        y = coords['y'] + random.randint(-5, 5)
        self.shell(f"input tap {x} {y}")
    
    # ──────────────────────────────────────────
    # 브라우저 제어
    # ──────────────────────────────────────────
    def open_url(self, url, max_retry=3):
        """URL 열기 + 브라우저 실행 확인"""
        
        for attempt in range(1, max_retry + 1):
            log(f"URL 열기 (시도 {attempt}/{max_retry}): {url}")
            self.shell(f'am start -a android.intent.action.VIEW -d "{url}"')
            
            time.sleep(2)
            
            # 브라우저 로딩 확인 (최대 5초)
            for _ in range(10):
                xml = self.get_screen_xml(force=True)
                if xml and len(xml) > 500:
                    if "naver" in xml.lower() or "MM_SEARCH" in xml or "검색" in xml:
                        log(f"[확인] 브라우저 로딩 완료!")
                        random_delay(1.0, 2.0)
                        return True
                time.sleep(0.5)
            
            if attempt < max_retry:
                log(f"[재시도] 브라우저 로딩 안 됨...")
                self.shell("input keyevent 3")
                time.sleep(1)
        
        log("[실패] 브라우저 실행 실패", "ERROR")
        return False
    
    # ──────────────────────────────────────────
    # UI Automator
    # ──────────────────────────────────────────
    def get_screen_xml(self, force=False):
        """화면 UI XML (캐싱)"""
        now = time.time()
        if not force and self._last_xml and (now - self._last_xml_time) < 0.3:
            return self._last_xml
        
        self.shell("uiautomator dump /sdcard/screen.xml")
        xml = self.shell("cat /sdcard/screen.xml")
        
        self._last_xml = xml
        self._last_xml_time = now
        return xml
    
    def find_element_by_resource_id(self, resource_id, xml=None):
        """리소스 ID로 요소 찾기"""
        if xml is None:
            xml = self.get_screen_xml(force=True)
        if not xml:
            return {"found": False}
        
        # bounds와 resource-id 순서 무관하게 찾기
        pattern1 = rf'resource-id="[^"]*{re.escape(resource_id)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        pattern2 = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*resource-id="[^"]*{re.escape(resource_id)}[^"]*"'
        
        match = re.search(pattern1, xml) or re.search(pattern2, xml)
        
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            return {
                "found": True,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2,
                "width": x2 - x1,
                "height": y2 - y1
            }
        return {"found": False}
    
    def find_element_by_text(self, text, partial=True, xml=None):
        """텍스트로 요소 찾기"""
        if xml is None:
            xml = self.get_screen_xml(force=True)
        if not xml:
            return {"found": False}
        
        # 더 정확한 패턴: node 전체에서 text와 bounds 추출
        if partial:
            # text="...검색결과 더보기..." 포함
            node_pattern = rf'<node[^>]+text="([^"]*{re.escape(text)}[^"]*)"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*/?>'
        else:
            # text="검색결과 더보기" 정확히
            node_pattern = rf'<node[^>]+text="{re.escape(text)}"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*/?>'
        
        match = re.search(node_pattern, xml)
        
        if match:
            matched_text, x1, y1, x2, y2 = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # bounds 유효성
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                return {"found": False}
            
            return {
                "found": True,
                "text": matched_text,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2
            }
        
        # 패턴 2: bounds가 text 앞에 있는 경우
        if partial:
            node_pattern2 = rf'<node[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]+text="([^"]*{re.escape(text)}[^"]*)"[^>]*/?>'
        else:
            node_pattern2 = rf'<node[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]+text="{re.escape(text)}"[^>]*/?>'
        
        match = re.search(node_pattern2, xml)
        
        if match:
            x1, y1, x2, y2, matched_text = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                return {"found": False}
            
            return {
                "found": True,
                "text": matched_text,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2
            }
        
        return {"found": False}
    
    def find_all_elements_with_domain(self, domain, xml=None):
        """도메인이 포함된 모든 요소 찾기"""
        if xml is None:
            xml = self.get_screen_xml(force=True)
        if not xml:
            return []
        
        links = []
        # text 또는 content-desc에서 도메인 찾기
        # 더 정확한 패턴: node 전체를 찾고 그 안에서 bounds 추출
        node_pattern = rf'<node[^>]+(?:text|content-desc)="([^"]*{re.escape(domain)}[^"]*)"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*/>'
        
        for match in re.finditer(node_pattern, xml, re.IGNORECASE):
            text_found, x1, y1, x2, y2 = match.groups()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # 유효한 bounds만
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                continue
            
            links.append({
                "found": True,
                "text": text_found,
                "bounds": (x1, y1, x2, y2),
                "center_x": (x1 + x2) // 2,
                "center_y": (y1 + y2) // 2
            })
        
        return links
    
    def click_search_button(self):
        """검색 버튼 클릭 - 키보드 검색 버튼 우선"""
        
        # 1순위: 키보드의 검색 버튼 (Gboard 우측 하단) - 가장 확실함
        search_key = KEYBOARD_LAYOUT.get('search')
        if search_key:
            log(f"키보드 검색 버튼: ({search_key['x']}, {search_key['y']})")
            self.tap(search_key['x'], search_key['y'], randomize=True)
            return True
        
        # 2순위: UI에서 검색 버튼 찾기 (화면 오른쪽만)
        xml = self.get_screen_xml(force=True)
        half_width = self.screen_width // 2
        
        button_patterns = [
            r'<node[^>]+content-desc="[^"]*검색[^"]*"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'<node[^>]+resource-id="[^"]*search[^"]*btn[^"]*"[^>]+bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        ]
        
        for pattern in button_patterns:
            for match in re.finditer(pattern, xml, re.IGNORECASE):
                x1, y1, x2, y2 = map(int, match.groups())
                cx = (x1 + x2) // 2
                
                # 화면 오른쪽에 있는 버튼만
                if cx > half_width and x2 - x1 > 0 and y2 - y1 > 0:
                    cy = (y1 + y2) // 2
                    log(f"검색 버튼 발견: [{x1},{y1}][{x2},{y2}]")
                    self.tap(cx, cy, randomize=False)
                    return True
        
        log("[경고] 검색 버튼 못 찾음")
        return False


# ============================================
# 네이버 검색 자동화
# ============================================
class NaverSearchAutomation:
    def __init__(self, adb: ADBController, cdp_info=None):
        self.adb = adb
        self.viewport_top = adb.screen_height * 0.15
        self.viewport_bottom = adb.screen_height * 0.85
        self.cdp_info = cdp_info  # CDP 계산 결과
    
    # ========================================
    # 1단계: 네이버 메인 이동
    # ========================================
    def step1_go_to_naver(self):
        log("=" * 50)
        log("[1단계] 네이버 메인으로 이동")
        log("=" * 50)
        
        if not self.adb.open_url(NAVER_CONFIG["start_url"], max_retry=3):
            return False
        return True
    
    # ========================================
    # 2단계: 검색창 클릭 (CDP 로직 동일)
    # ========================================
    def step2_click_search_box(self):
        log("=" * 50)
        log("[2단계] 검색창 클릭")
        log("=" * 50)
        
        max_retry = WAIT_CONFIG.get("max_element_retry", 30)
        clicks_before_reload = 5
        
        for retry in range(1, max_retry + 1):
            # 5번마다 메인 재이동 (CDP 동일)
            if retry > 1 and (retry - 1) % clicks_before_reload == 0:
                log(f"[재이동] {clicks_before_reload}번 실패, 네이버 재이동...")
                self.adb.open_url(NAVER_CONFIG["start_url"], max_retry=1)
            
            xml = self.adb.get_screen_xml(force=True)
            
            # 검색창 찾기 (MM_SEARCH_FAKE)
            element = self.adb.find_element_by_resource_id("MM_SEARCH_FAKE", xml)
            if not element.get("found"):
                element = self.adb.find_element_by_resource_id("query", xml)
            
            if not element.get("found"):
                log(f"[재시도 {retry}/{max_retry}] 검색창 못 찾음")
                time.sleep(0.5)
                continue
            
            # 화면 범위 체크
            cy = element.get("center_y", -1)
            if cy < 0 or cy > self.adb.screen_height:
                log(f"[재시도 {retry}/{max_retry}] 검색창이 화면 밖")
                time.sleep(0.5)
                continue
            
            # 검색창 클릭
            if not self.adb.tap_element(element):
                continue
            
            log(f"[클릭 {retry}/{max_retry}] 검색 모드 확인 중...")
            time.sleep(0.8)
            
            # 검색 모드 전환 확인 (키보드가 떴는지)
            xml = self.adb.get_screen_xml(force=True)
            query = self.adb.find_element_by_resource_id("query", xml)
            
            if query.get("found"):
                qy = query.get("center_y", -1)
                if 0 <= qy <= self.adb.screen_height:
                    log("[성공] 검색 모드 전환됨!")
                    # 입력창 한번 더 클릭 (포커스)
                    self.adb.tap_element(query)
                    time.sleep(0.3)
                    return True
            
            time.sleep(0.5)
        
        log(f"[실패] 검색창 클릭 {max_retry}번 실패", "ERROR")
        return False
    
    # ========================================
    # 3단계: 검색어 입력
    # ========================================
    def step3_input_keyword(self, keyword):
        log("=" * 50)
        log(f"[3단계] 검색어 입력: {keyword}")
        log("=" * 50)
        
        self.adb.input_text(keyword)
        random_delay(0.3, 0.5)
        return True
    
    # ========================================
    # 4단계: 검색 실행 (CDP 로직 동일)
    # ========================================
    def step4_execute_search(self):
        log("=" * 50)
        log("[4단계] 검색 실행")
        log("=" * 50)
        
        # 검색 모드 (1=엔터, 2=돋보기, 3=랜덤)
        search_mode = NAVER_CONFIG.get("search_mode", 3)
        if search_mode == 3:
            search_mode = random.choice([1, 2])
        
        mode_name = "엔터" if search_mode == 1 else "돋보기"
        log(f"검색 방식: {mode_name}")
        
        search_success = False
        
        if search_mode == 1:
            self.adb.press_enter()
            search_success = True
        else:
            # 돋보기 버튼 클릭 시도
            if self.adb.click_search_button():
                search_success = True
            else:
                # 못 찾으면 엔터로 대체 (CDP 동일)
                log("돋보기 못 찾음, 엔터로 대체")
                self.adb.press_enter()
                search_success = True
        
        # 검색 결과 대기 (CDP: 10초)
        log("[대기] 검색 결과 로딩...")
        time.sleep(2)
        
        # 1차 확인
        for _ in range(8):  # 4초
            xml = self.adb.get_screen_xml(force=True)
            if xml and ("search" in xml.lower() or "검색" in xml):
                log("[성공] 검색 결과 로딩 완료!")
                return True
            time.sleep(0.5)
        
        # 1차 실패 → 엔터로 재시도 (CDP 동일)
        log("[재시도] 검색 결과 없음, 엔터로 재검색...")
        self.adb.press_enter()
        time.sleep(2)
        
        # 2차 확인
        for _ in range(8):
            xml = self.adb.get_screen_xml(force=True)
            if xml and ("search" in xml.lower() or "검색" in xml):
                log("[성공] 검색 결과 로딩 완료!")
                return True
            time.sleep(0.5)
        
        log("[경고] 검색 결과 확인 안 됨, 진행...")
        return True
    
    # ========================================
    # 4.5단계: 통합에서 도메인 찾기
    # ========================================
    def step4_5_find_in_total(self, domain):
        log("=" * 50)
        log(f"[4.5단계] 통합에서 '{domain}' 찾기")
        log("=" * 50)
        
        max_scrolls = NAVER_CONFIG.get("max_scrolls_total", 30)
        same_pos_count = 0
        
        for scroll_count in range(max_scrolls):
            xml = self.adb.get_screen_xml(force=True)
            links = self.adb.find_all_elements_with_domain(domain, xml)
            
            if links:
                # 화면 중앙에 있는 링크
                visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
                
                if visible:
                    log(f"[통합] {domain} 발견! {len(visible)}개 링크")
                    
                    # 추가 랜덤 스크롤 (자연스럽게) - CDP 동일
                    extra = random.randint(30, 100) * random.choice([1, -1])
                    self.adb.scroll_down(extra)
                    time.sleep(random.uniform(0.3, 0.5))
                    
                    # 다시 확인
                    xml = self.adb.get_screen_xml(force=True)
                    links = self.adb.find_all_elements_with_domain(domain, xml)
                    visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
                    
                    if visible:
                        selected = random.choice(visible)
                        log(f"[클릭] {selected['text'][:50]}...")
                        self.adb.tap_element(selected)
                        random_delay(2.0, 3.0)
                        return True
            
            self.adb.scroll_down()
            
            if scroll_count % 5 == 0:
                log(f"[4.5단계] 스크롤 {scroll_count}/{max_scrolls}...")
            
            random_delay(0.3, 0.5)
        
        log(f"[4.5단계] 통합에서 {domain} 못 찾음")
        return False
    
    # ========================================
    # 5단계: "검색결과 더보기" 찾기
    # ========================================
    def step5_scroll_to_more(self):
        log("=" * 50)
        log("[5단계] '검색결과 더보기' 찾기")
        log("=" * 50)
        
        target = NAVER_CONFIG.get("target_text", "검색결과 더보기")
        max_scrolls = NAVER_CONFIG.get("max_scrolls", 50)
        short_scroll = int(self.adb.screen_height * 0.3)
        
        # CDP 계산값 사용 (있으면)
        if self.cdp_info and self.cdp_info.get("calculated") and self.cdp_info.get("more_scroll_count", 0) > 0:
            cdp_scroll = self.cdp_info["more_scroll_count"]
            log(f"[CDP] 계산값 사용: {cdp_scroll}번 스크롤")
            
            # 덤프 없이 빠르게 스크롤 (읽기 멈춤 포함)
            for i in range(cdp_scroll):
                self.adb.scroll_down()
                
                # 읽기 멈춤 (확률적)
                if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
                    pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
                    log(f"읽기 멈춤: {pause:.1f}초")
                    time.sleep(pause)
                else:
                    time.sleep(random.uniform(0.1, 0.2))
                
                if (i + 1) % 10 == 0:
                    log(f"[5단계] 스크롤 {i + 1}/{cdp_scroll}...")
            
            # 여유분 3회 스크롤
            log("[5단계] 여유분 3회 스크롤...")
            for _ in range(3):
                self.adb.scroll_down()
                time.sleep(random.uniform(0.2, 0.3))
            
            # 덤프해서 더보기 찾기
            xml = self.adb.get_screen_xml(force=True)
            element = self.adb.find_element_by_text(target, xml=xml)
            
            if element.get("found"):
                cy = element["center_y"]
                if self.viewport_top <= cy <= self.viewport_bottom:
                    log(f"[발견] '{target}' y={cy}")
                    return element
            
            # 못 찾으면 추가 스크롤 (덤프하며)
            log("[5단계] 못 찾음, 추가 스크롤...")
            for extra in range(10):
                self.adb.scroll_down(short_scroll)
                time.sleep(0.3)
                xml = self.adb.get_screen_xml(force=True)
                element = self.adb.find_element_by_text(target, xml=xml)
                if element.get("found"):
                    cy = element["center_y"]
                    if self.viewport_top <= cy <= self.viewport_bottom:
                        log(f"[발견] '{target}' y={cy} (추가 {extra + 1}회)")
                        return element
            
            log(f"[실패] '{target}' 못 찾음", "ERROR")
            return None
        
        # CDP 없으면 기존 방식 (매번 덤프)
        log("[5단계] 기존 방식 (CDP 없음)")
        for scroll_count in range(max_scrolls):
            xml = self.adb.get_screen_xml(force=True)
            element = self.adb.find_element_by_text(target, xml=xml)
            
            if element.get("found"):
                cy = element["center_y"]
                
                if self.viewport_top <= cy <= self.viewport_bottom:
                    log(f"[발견] '{target}' y={cy}")
                    return element
                
                if cy < self.viewport_top:
                    self.adb.scroll_up(short_scroll)
                    continue
            
            self.adb.scroll_down(short_scroll)
            
            if scroll_count % 10 == 0:
                log(f"[5단계] 스크롤 {scroll_count}/{max_scrolls}...")
        
        log(f"[실패] '{target}' 못 찾음", "ERROR")
        return None
    
    # ========================================
    # 6단계: "검색결과 더보기" 클릭 (CDP 로직 동일)
    # ========================================
    def step6_click_more(self, element):
        log("=" * 50)
        log("[6단계] '검색결과 더보기' 클릭")
        log("=" * 50)
        
        max_retry = NAVER_CONFIG.get("step6_click_retry", 5)
        target = NAVER_CONFIG.get("target_text", "검색결과 더보기")
        
        # 클릭 전 안정화 대기 (CDP 동일)
        random_delay(0.5, 1.0)
        
        for click_try in range(1, max_retry + 1):
            time.sleep(random.uniform(0.3, 0.6))
            
            self.adb.tap_element(element)
            log(f"[클릭 {click_try}/{max_retry}] 로딩 대기...")
            
            # 10초 단위로 체크하면서 재클릭 (CDP 동일: 10초 * 5회 = 50초)
            max_reclick = 5
            
            for reclick_try in range(max_reclick):
                # 10초 대기 (0.5초 * 20)
                for _ in range(20):
                    xml = self.adb.get_screen_xml(force=True)
                    nx = self.adb.find_element_by_resource_id("nx_query", xml)
                    
                    if nx.get("found"):
                        log("[성공] 더보기 페이지 로딩 완료!")
                        random_delay(1.0, 2.0)
                        return True
                    time.sleep(0.5)
                
                # URL 안 바뀌면 재클릭 (CDP 동일)
                if reclick_try < max_reclick - 1:
                    log(f"[재클릭] 페이지 변경 없음, 재클릭 {reclick_try + 2}/{max_reclick}...")
                    # 요소 다시 찾아서 클릭
                    xml = self.adb.get_screen_xml(force=True)
                    element = self.adb.find_element_by_text(target, xml=xml)
                    if element.get("found"):
                        self.adb.tap_element(element)
            
            # 타임아웃
            log(f"[타임아웃] 페이지 로딩 50초 초과")
            return False
        
        log(f"[실패] 더보기 클릭 {max_retry}번 실패", "ERROR")
        return False
    
    # ========================================
    # 7단계: 더보기 페이지에서 도메인 찾기
    # ========================================
    def step7_find_domain(self, domain):
        log("=" * 50)
        log(f"[7단계] '{domain}' 찾기")
        log("=" * 50)
        
        # CDP 계산값 사용 (있으면)
        if self.cdp_info and self.cdp_info.get("calculated") and self.cdp_info.get("domain_scroll_count", -1) >= 0:
            cdp_scroll = self.cdp_info["domain_scroll_count"]
            log(f"[CDP] 계산값 사용: {cdp_scroll}번 스크롤")
            
            # 덤프 없이 빠르게 스크롤 (읽기 멈춤 포함)
            for i in range(cdp_scroll):
                self.adb.scroll_down()
                
                if READING_PAUSE_CONFIG["enabled"] and random.random() < READING_PAUSE_CONFIG["probability"]:
                    pause = random.uniform(READING_PAUSE_CONFIG["min_time"], READING_PAUSE_CONFIG["max_time"])
                    log(f"읽기 멈춤: {pause:.1f}초")
                    time.sleep(pause)
                else:
                    time.sleep(random.uniform(0.1, 0.2))
                
                if (i + 1) % 10 == 0:
                    log(f"[7단계] 스크롤 {i + 1}/{cdp_scroll}...")
            
            # 여유분 3회 스크롤
            log("[7단계] 여유분 3회 스크롤...")
            for _ in range(3):
                self.adb.scroll_down()
                time.sleep(random.uniform(0.2, 0.3))
            
            # 덤프해서 도메인 찾기
            return self._find_and_click_domain_final(domain)
        
        # CDP 없거나 도메인 못 찾은 경우 → 기존 방식 (페이지별 탐색)
        log("[7단계] 기존 방식 (CDP 없음)")
        
        max_page = NAVER_CONFIG.get("max_page", 10)
        start_page = 2
        
        for page_num in range(start_page, max_page + 1):
            log(f"[탐색] {page_num}페이지...")
            
            if self._find_and_click_domain_in_page(domain):
                return True
            
            if page_num < max_page:
                next_page = page_num + 1
                log(f"[이동] {next_page}페이지로...")
                
                if not self._click_page_number(next_page):
                    log(f"[실패] {next_page}페이지 버튼 못 찾음")
                    break
                
                random_delay(1.5, 2.5)
        
        log(f"[실패] {domain} 못 찾음 ({max_page}페이지까지)", "ERROR")
        return False
    
    def _find_and_click_domain_final(self, domain):
        """CDP 스크롤 후 도메인 찾아서 클릭"""
        short_scroll = int(self.adb.screen_height * 0.3)
        
        # 먼저 현재 위치에서 찾기
        xml = self.adb.get_screen_xml(force=True)
        links = self.adb.find_all_elements_with_domain(domain, xml)
        visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
        
        if visible:
            return self._click_domain_link(visible, domain)
        
        # 못 찾으면 추가 스크롤
        log("[7단계] CDP 위치에서 못 찾음, 추가 스크롤...")
        for _ in range(15):
            self.adb.scroll_down(short_scroll)
            time.sleep(0.3)
            
            xml = self.adb.get_screen_xml(force=True)
            links = self.adb.find_all_elements_with_domain(domain, xml)
            visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
            
            if visible:
                return self._click_domain_link(visible, domain)
        
        return False
    
    def _click_domain_link(self, visible_links, domain):
        """도메인 링크 클릭"""
        log(f"[발견] {domain} 링크 {len(visible_links)}개!")
        
        # 추가 랜덤 스크롤
        extra = random.randint(30, 80) * random.choice([1, -1])
        self.adb.scroll_down(extra)
        time.sleep(0.3)
        
        # 다시 확인
        xml = self.adb.get_screen_xml(force=True)
        links = self.adb.find_all_elements_with_domain(domain, xml)
        visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
        
        if visible:
            for click_try in range(3):
                selected = random.choice(visible)
                log(f"[클릭 {click_try + 1}/3] {selected['text'][:50]}...")
                self.adb.tap_element(selected)
                time.sleep(2)
                
                xml = self.adb.get_screen_xml(force=True)
                nx = self.adb.find_element_by_resource_id("nx_query", xml)
                
                if not nx.get("found"):
                    log("[성공] 페이지 이동!")
                    return True
                
                log("[재시도] 페이지 변경 안 됨")
        
        return False
    
    def _find_and_click_domain_in_page(self, domain):
        """현재 페이지에서 도메인 찾아서 클릭"""
        max_scrolls = 30
        short_scroll = int(self.adb.screen_height * 0.3)
        
        for scroll_count in range(max_scrolls):
            xml = self.adb.get_screen_xml(force=True)
            links = self.adb.find_all_elements_with_domain(domain, xml)
            
            if links:
                visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
                
                if visible:
                    log(f"[발견] {domain} 링크 {len(visible)}개!")
                    
                    # 추가 랜덤 스크롤 (CDP 동일)
                    extra = random.randint(30, 80) * random.choice([1, -1])
                    self.adb.scroll_down(extra)
                    time.sleep(0.3)
                    
                    # 다시 확인
                    xml = self.adb.get_screen_xml(force=True)
                    links = self.adb.find_all_elements_with_domain(domain, xml)
                    visible = [l for l in links if self.viewport_top <= l["center_y"] <= self.viewport_bottom]
                    
                    if visible:
                        for click_try in range(3):
                            selected = random.choice(visible)
                            log(f"[클릭 {click_try + 1}/3] {selected['text'][:50]}...")
                            self.adb.tap_element(selected)
                            time.sleep(2)
                            
                            xml = self.adb.get_screen_xml(force=True)
                            nx = self.adb.find_element_by_resource_id("nx_query", xml)
                            
                            if not nx.get("found"):
                                log("[성공] 페이지 이동!")
                                return True
                            
                            log("[재시도] 페이지 변경 안 됨")
                        
                        return False
            
            self.adb.scroll_down(short_scroll)
            
            if scroll_count % 10 == 0:
                log(f"[7단계] 스크롤 {scroll_count}/{max_scrolls}...")
        
        return False
        
        return False
    
    def _click_page_number(self, page_num):
        """페이지 번호 버튼 클릭 (CDP 동일)"""
        max_scroll = 15
        
        for _ in range(max_scroll):
            xml = self.adb.get_screen_xml(force=True)
            element = self.adb.find_element_by_text(str(page_num), partial=False, xml=xml)
            
            if element.get("found"):
                bounds = element.get("bounds", (0, 0, 0, 0))
                if bounds[0] == 0 and bounds[1] == 0 and bounds[2] == 0 and bounds[3] == 0:
                    self.adb.scroll_down()
                    time.sleep(0.2)
                    continue
                
                cy = element["center_y"]
                
                if self.viewport_top <= cy <= self.viewport_bottom:
                    self.adb.tap_element(element)
                    return True
                
                if cy > self.viewport_bottom:
                    self.adb.scroll_down()
                else:
                    self.adb.scroll_up()
            else:
                self.adb.scroll_down()
            
            time.sleep(0.2)
        
        return False
    
    # ========================================
    # 8단계: 체류
    # ========================================
    def step8_stay(self):
        log("=" * 50)
        log("[8단계] 타겟 사이트 체류")
        log("=" * 50)
        
        stay = random.uniform(NAVER_CONFIG.get("stay_min", 10), NAVER_CONFIG.get("stay_max", 20))
        log(f"[체류] {stay:.1f}초...")
        time.sleep(stay)
        return True
    
    # ========================================
    # 9단계: 뒤로가기
    # ========================================
    def step9_go_back(self, is_last=False):
        log("=" * 50)
        log("[9단계] 뒤로가기")
        log("=" * 50)
        
        if is_last:
            log("마지막 키워드 - 뒤로가기 생략")
            return True
        
        self.adb.press_back()
        random_delay(1.0, 2.0)
        log("[완료] 검색 페이지로 복귀")
        return True
    
    # ========================================
    # 전체 실행
    # ========================================
    def run(self, keyword, domain, search_in_total=True, go_to_more=True, is_last=False):
        log("=" * 60)
        log(f"검색 시작: '{keyword}' → {domain}")
        log(f"옵션: 통합={search_in_total}, 더보기={go_to_more}, 마지막={is_last}")
        log("=" * 60)
        
        # 1단계
        if not self.step1_go_to_naver():
            return "ERROR"
        
        # 2단계
        if not self.step2_click_search_box():
            return "RETRY"
        
        # 3단계
        if not self.step3_input_keyword(keyword):
            return "ERROR"
        
        # 4단계
        if not self.step4_execute_search():
            return "ERROR"
        
        # 4.5단계
        if search_in_total:
            if self.step4_5_find_in_total(domain):
                log(f"[성공] 통합에서 {domain} 클릭!")
                self.step8_stay()
                self.step9_go_back(is_last)
                return "DONE"
            
            if not go_to_more:
                return "NOTFOUND"
            
            log("통합에 없음, 더보기로...")
        
        if not go_to_more:
            return "NOTFOUND"
        
        # 5단계
        more_el = self.step5_scroll_to_more()
        if not more_el:
            return "RETRY"
        
        # 6단계
        if not self.step6_click_more(more_el):
            return "RETRY"
        
        # 7단계
        if not self.step7_find_domain(domain):
            return "NOTFOUND"
        
        log(f"[성공] {domain} 클릭!")
        
        # 8단계
        self.step8_stay()
        
        # 9단계
        self.step9_go_back(is_last)
        
        return "DONE"


# ============================================
# 메인
# ============================================
def main():
    if len(sys.argv) < 3:
        print("사용법: python adb_auto_cdp.py 검색어 도메인 [검색모드] [폰번호] [마지막]")
        print("예시: python adb_auto_cdp.py 곤지암스키강습 sidecut.co.kr")
        print("예시: python adb_auto_cdp.py 곤지암스키강습 sidecut.co.kr total")
        print("예시: python adb_auto_cdp.py 곤지암스키강습 sidecut.co.kr more 1 1")
        print("")
        print("[검색모드] total=통합에서만, more=더보기에서, both=통합→더보기 (기본값)")
        print("[폰번호] config.py PHONES 키 (기본값: 1)")
        print("[마지막] 0=중간, 1=마지막 키워드")
        return
    
    keyword = sys.argv[1]
    domain = sys.argv[2]
    
    # 검색 모드
    search_in_total = True
    go_to_more = True
    
    if len(sys.argv) >= 4:
        mode = sys.argv[3].lower()
        if mode == "total":
            search_in_total = True
            go_to_more = False
        elif mode == "more":
            search_in_total = False
            go_to_more = True
        else:
            search_in_total = True
            go_to_more = True
    
    phone_key = sys.argv[4] if len(sys.argv) >= 5 else "1"
    is_last = sys.argv[5] in ["1", "true", "last"] if len(sys.argv) >= 6 else False
    
    if phone_key not in PHONES:
        print(f"[오류] 폰 '{phone_key}' 없음")
        return
    
    phone_config = PHONES[phone_key]
    
    print("=" * 60)
    print("[ADB + CDP 통합 네이버 검색 v3]")
    print(f"[검색어] {keyword}")
    print(f"[도메인] {domain}")
    print(f"[모드] 통합:{search_in_total}, 더보기:{go_to_more}")
    print(f"[폰] {phone_config.get('name', phone_key)}")
    print(f"[마지막] {'YES' if is_last else 'NO'}")
    print("=" * 60)
    
    # ADB 연결
    adb = ADBController(phone_config)
    if not adb.connect():
        return
    
    # CDP 계산 (선택적 - 크롬 디버깅 모드 필요)
    cdp_info = None
    cdp = None
    
    if go_to_more and CDP_AVAILABLE:
        print("\n[CDP 스크롤 계산]")
        cdp = CDPCalculator(port=9222)
        
        if cdp.connect():
            cdp_info = cdp.calculate_scroll_info(
                keyword, domain,
                adb.screen_width, adb.screen_height
            )
            cdp.close()
        else:
            print("[CDP] 연결 실패, 기존 방식으로 진행")
    
    print("")
    
    # 자동화 실행
    automation = NaverSearchAutomation(adb, cdp_info)
    max_retry = NAVER_CONFIG.get("max_full_retry", 2)
    
    for retry in range(max_retry + 1):
        if retry > 0:
            log(f"\n[전체 재시도 {retry}/{max_retry}]")
        
        result = automation.run(keyword, domain, search_in_total, go_to_more, is_last)
        
        if result == "DONE":
            print("\n" + "=" * 60)
            print("[완료] 성공!")
            print("=" * 60)
            return
        elif result == "NOTFOUND":
            print("\n" + "=" * 60)
            print(f"[결과] {domain} 못 찾음")
            print("=" * 60)
            return
        elif result == "RETRY" and retry < max_retry:
            continue
        else:
            break
    
    print("\n" + "=" * 60)
    print("[실패]")
    print("=" * 60)


if __name__ == "__main__":
    main()