"""实时信息工具：日期/时间、天气（Open-Meteo 免 key）。

- 日期/时间：本地系统时间，零依赖。
- 天气：Open-Meteo 免 key API（无需注册、无需 token）。
  - geocoding: https://geocoding-api.open-meteo.com/v1/search?name=<城市>
  - forecast:   https://api.open-meteo.com/v1/forecast?latitude=&longitude=&current=temperature_2m,weather_code

用法：
  from generator.realtime import get_datetime, get_weather
  get_datetime()                       -> "2026年8月9日 周日 14:32 (本地时间)"
  get_weather("东京")                  -> "东京 当前 24.5°C，多云。"
  get_weather()                       -> 默认城市（DEFAULT_CITY）
"""
import datetime
import json
import re

import requests

DEFAULT_CITY = "东京"

# Open-Meteo weather_code -> 中文简述
WEATHER_DESC = {
    0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷阵雨伴冰雹",
}

_TZ_NAME = "（本地时间）"


def get_datetime() -> str:
    """返回人类可读的本地日期时间。"""
    now = datetime.datetime.now()
    week = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    return f"{now.year}年{now.month}月{now.day}日 {week} {now.hour:02d}:{now.minute:02d} {_TZ_NAME}"


def _geocode(city: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 1, "language": "zh"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data.get("results"):
        return None
    res = data["results"][0]
    return res.get("latitude"), res.get("longitude"), res.get("name")


def get_weather(city: str | None = None) -> str:
    """查询天气。city 为 None 时用 DEFAULT_CITY。失败返回错误信息字符串。"""
    city = city or DEFAULT_CITY
    try:
        geo = _geocode(city)
        if not geo:
            return f"没能找到「{city}」这个地方的天气，换个地名试试？"
        lat, lon, name = geo
        url = "https://api.open-meteo.com/v1/forecast"
        r = requests.get(
            url,
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=10,
        )
        r.raise_for_status()
        cur = r.json().get("current", {})
        temp = cur.get("temperature_2m")
        code = cur.get("weather_code")
        desc = WEATHER_DESC.get(code, "未知天气")
        if temp is None:
            return f"{name} 的天气暂时查不到。"
        return f"{name} 当前气温 {temp}°C，{desc}。"
    except Exception as e:
        return f"查天气时出了点小状况（{e}），稍后再试？"


# ---- 意图识别：决定要不要调用实时工具 ----
def detect_realtime(user_msg: str):
    """返回 (kind, city) 或 None。kind ∈ {'datetime','weather'}。
    city 为 None 表示未指定城市（调用方用默认城市）。"""
    m = user_msg.strip()
    # 天气：含天气相关词
    weather_kw = ["天气", "气温", "几度", "温度", "降雨", "下雨", "下雪", "晴", "阴", "多云", "冷不冷", "热不冷"]
    if any(k in m for k in weather_kw):
        city = _extract_city(m)
        return ("weather", city)
    # 日期/时间
    dt_kw = ["几号", "星期几", "周几", "今天日期", "今天是", "现在几点", "日期", "时间", "年月日", "星期"]
    if any(k in m for k in dt_kw):
        return ("datetime", None)
    return None


# 非地名的干扰词（出现在候选城市串里时剔除/判定为无效）
_CITY_STOP = {"查询", "今日", "现在", "此刻", "这会儿", "目前", "天气", "我想", "我要",
              "请问", "帮忙", "查一下", "看一下", "知道", "今天", "明天", "昨天"}


def _extract_city(m: str):
    """从消息中抽取城市名（2-4 个汉字）。抽不到或抽到非地名则返回 None。"""
    time_alt = "(?:今天|现在|此刻|这会儿|目前|明天|昨天)?"
    # 句式1：<城市>天气 / <城市>的天气 / <城市>今日天气
    mm = re.search(r"([一-龥]{2,4}?)(?:的)?%s天气" % time_alt, m)
    if mm:
        cand = mm.group(1)
        if cand not in _CITY_STOP and not any(w in cand for w in _CITY_STOP):
            return cand
    # 句式2：天气 <城市> / 天气在<城市> / 天气<城市>
    mm2 = re.search(r"天气(?:在|到|于|是)?([一-龥]{2,4})", m)
    if mm2:
        cand = mm2.group(1)
        if cand not in _CITY_STOP and not any(w in cand for w in _CITY_STOP):
            return cand
    return None


def _looks_like_place(text: str) -> str | None:
    """判断一段文本是否像一个地名（用于多轮补城市）。
    返回地名（2-4 汉字）或 None。要求：整段就是 2-4 个汉字、且不含非地名词。"""
    t = text.strip()
    if not (2 <= len(t) <= 4):
        return None
    if not re.fullmatch(r"[一-龥]+", t):
        return None
    if t in _CITY_STOP or any(w in t for w in _CITY_STOP):
        return None
    chitchat = ["你好", "谢谢", "在吗", "早安", "晚安", "哈哈", "嗯嗯", "好吧", "是的", "不是"]
    if t in chitchat:
        return None
    return t


if __name__ == "__main__":
    print(get_datetime())
    print(get_weather("东京"))
    print(get_weather("北京"))
    print(detect_realtime("东京今天天气怎么样"))
    print(detect_realtime("今天是几号"))
