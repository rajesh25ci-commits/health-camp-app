"""
=============================================================================
Smart Community Health Camp Management System - V3 Architecture
File: upgraded_features_v3.py
=============================================================================
1. Universal Multilingual AI Chatbot (Strict Priority-Ordered Engine + Gemini API)
   - Priority 1: Emergency & 108 Alert
   - Priority 2: Specific Symptoms (Fever, Cough, Acidity, Sugar, BP, Anemia) FIRST
   - Priority 3: Diet / Food Advice
   - Priority 4: Generic Tablet Timings (Only when no symptom is mentioned)
   - Supports English, Hindi, Kannada, Hinglish
2. Symptom-First Tablet Schedule Generator
3. Gamified Health Camp Impact Score, XP Progress & Tier Levels
   (Bronze Seva Starter -> Silver Responder -> Gold Rural Healthcare Hero -> Platinum Health Champion)
4. Patient Health Wellness Score (0-100) & 4-Step Patient Journey Tracker
=============================================================================
"""

import os
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import case

features_v3_bp = Blueprint('features_v3_bp', __name__)

# =============================================================================
# 1. LANGUAGE DETECTION
# =============================================================================

def detect_language(text: str) -> str:
    """
    Detect whether text is Kannada, Hindi (Devanagari), Hinglish, or English.
    """
    if re.search(r'[\u0C80-\u0CFF]', text):
        return 'kannada'
    if re.search(r'[\u0900-\u097F]', text):
        return 'hindi'
    
    lower = text.lower()
    kannada_words = [
        'jwara', 'jvara', 'talenovu', 'kemmu', 'hottenovu', 'maddu', 'aushadhi',
        'neeru', 'oota', 'turtu', 'othada', 'sakkare', 'hege', 'yavaga', 'elli',
        'enu', 'beku', 'thale', 'bisi', 'mathe'
    ]
    if any(k in lower for k in kannada_words):
        return 'kannada_translit'

    hinglish_words = [
        'kya', 'hai', 'batao', 'dawa', 'dawaii', 'samay', 'khana', 'peena',
        'bukhar', 'sir', 'dard', 'pet', 'khasi', 'zukam', 'chahiye', 'kaise',
        'kab', 'lena', 'subah', 'dophar', 'raat', 'namaste', 'bimar', 'mere'
    ]
    if any(k in lower for k in hinglish_words):
        return 'hinglish'

    return 'english'


# =============================================================================
# 2. PRIORITY-ORDERED MULTILINGUAL CLINICAL KNOWLEDGE ENGINE
# =============================================================================

def priority_multilingual_clinical_response(query: str, lang: str) -> str:
    """
    STRICT PRIORITY-ORDERED CLINICAL MATCHING:
    Priority 1 — Emergency Detection (Chest pain, severe breathlessness, fainting, 108)
    Priority 2 — Specific Symptoms FIRST (Fever, Cough, Acidity, Sugar, BP, Weakness)
                 *Fixes the bug where asking 'i have a fever recommend tablet' matched 'tablet' first*
    Priority 3 — Diet/Food Queries
    Priority 4 — Generic 1-0-1 Tablet Timing Explanation ONLY when no symptom was specified
    """
    q = query.lower()

    # -------------------------------------------------------------------------
    # PRIORITY 1: EMERGENCY DETECTION (Immediate 108 / Counter 1 Alert)
    # -------------------------------------------------------------------------
    emergency_triggers = [
        '108', 'ambulance', 'chest pain', 'heart attack', 'breathless', 'breathing',
        'choking', 'unconscious', 'fainted', 'fainting', 'heavy bleeding', 'paralysis',
        'stroke', 'critical', 'emergency', 'सीने में दर्द', 'सांस फूलना', 'बेहोश',
        'ಎದೆ ನೋವು', 'ಉಸಿರಾಟ', 'ತುರ್ತು', 'turtu', 'behosh'
    ]
    if any(t in q for t in emergency_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🚨 **ತುರ್ತು ಎಚ್ಚರಿಕೆ / EMERGENCY 108 ALERT:**\n"
                "• ಈ ಲಕ್ಷಣಗಳು ಗಂಭೀರ ವೈದ್ಯಕೀಯ ತುರ್ತು ಪರಿಸ್ಥಿತಿಯನ್ನು ಸೂಚಿಸುತ್ತವೆ.\n"
                "• ತಕ್ಷಣ ಉಚಿತ ಸಂಖ್ಯೆ **108 ಕ್ಕೆ ಕರೆ ಮಾಡಿ** ಅಥವಾ ಕ್ಯಾಂಪಿನ **ಕೌಂಟರ್ 1 (Emergency Triage)** ಗೆ ರೋಗಿಯನ್ನು ಕರೆತನ್ನಿ!\n"
                "• ರೋಗಿಯನ್ನು ಗಾಳಿಯಾಡುವ ಜಾಗದಲ್ಲಿ ತಲೆ ಎತ್ತರಿಸಿ ಮಲಗಿಸಿ. ನೀರು ಅಥವಾ ಆಹಾರ ಬಲವಂತವಾಗಿ ನೀಡಬೇಡಿ.\n"
                "👉 ಕ್ಯಾಂಪ್ ವೈದ್ಯರು ತಕ್ಷಣ ತಪಾಸಣೆ ಮಾಡುವುದು ಅತ್ಯಗತ್ಯ!"
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🚨 **आपातकालीन 108 अलर्ट / CRITICAL EMERGENCY WARNING:**\n"
                "• यह गंभीर चिकित्सकीय आपातकाल हो सकता है!\n"
                "• तुरंत टोल-फ्री **108 डायल करें** या मरीज को तुरंत कैंप के **काउंटर 1 (Emergency Triage)** पर लाएं!\n"
                "• मरीज को हवादार जगह पर सिर ऊंचा रखकर लिटाएं। जबरदस्ती कुछ खिलाएं-पिलाएं नहीं।\n"
                "👉 कैंप में मौजूद डॉक्टर को तुरंत दिखाएं, बिल्कुल भी देर न करें!"
            )
        else:
            return (
                "🚨 **CRITICAL EMERGENCY WARNING (CALL 108 IMMEDIATELY):**\n"
                "• These symptoms indicate a potentially life-threatening medical emergency!\n"
                "• **Dial 108 immediately** (National Toll-Free Ambulance) or bring the patient straight to **Camp Counter 1 (Emergency Triage)**.\n"
                "• Keep the patient calm in a well-ventilated space with head slightly elevated. Do not force oral fluids.\n"
                "👉 Have the attending camp medical officer examine the patient RIGHT NOW."
            )

    # -------------------------------------------------------------------------
    # PRIORITY 2: SPECIFIC SYMPTOMS FIRST (Evaluated before any generic 'tablet' check)
    # -------------------------------------------------------------------------

    # 2A. FEVER / BUKHAR / JWARA / TEMPERATURE (Addresses user's specific scenario)
    fever_triggers = ['fever', 'bukhar', 'jwara', 'jvara', 'temperature', 'taap', 'chills', 'thand', 'बुखार', 'ಜ್ವರ']
    if any(t in q for t in fever_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🌡️ **ಜ್ವರ ನಿರ್ವಹಣೆ ಮತ್ತು ಮಾತ್ರೆಗಳ ಸಲಹೆ (Fever Care):**\n"
                "• **ಪ್ಯಾರಸಿಟಮಾಲ್ (Paracetamol 650mg):** 1 ಮಾತ್ರೆ ಬೆಳಿಗ್ಗೆ 8:00 AM ಮತ್ತು 1 ಮಾತ್ರೆ ರಾತ್ರಿ 8:30 PM (ಆಹಾರ ಸೇವಿಸಿದ ನಂತರ). ಜ್ವರ 100°F ಗಿಂತ ಹೆಚ್ಚಿದ್ದರೆ ದಿನಕ್ಕೆ ಗರಿಷ್ಠ 3 ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಬಹುದು.\n"
                "• **ಆಹಾರ ಮತ್ತು ಜಲಸಂಚಯನ:** ಸಾಕಷ್ಟು ORS ದ್ರಾವಣ, ಎಳನೀರು, ಶುದ್ಧ ಕುದಿಸಿ ಆರಿಸಿದ ನೀರು ಮತ್ತು ಮೃದುವಾದ ಗಂಜಿ/ಇಡ್ಲಿ ಸೇವಿಸಿ.\n"
                "• ಜ್ವರ 2 ದಿನಗಳಿಗಿಂತ ಹೆಚ್ಚು ಮುಂದುವರಿದರೆ ಅಥವಾ ನಡುಕವಿದ್ದರೆ ರಕ್ತ ಪರೀಕ್ಷೆಗಾಗಿ ಕ್ಯಾಂಪ್ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🌡️ **बुखार के लिए दवा व देखभाल परामर्श (Fever Guidance):**\n"
                "• **Paracetamol 650mg:** 1 गोली सुबह 8:00 AM और 1 गोली रात 8:30 PM (खाना खाने के बाद लें)। यदि बुखार 100°F से अधिक हो तो दिन में अधिकतम 3 बार ले सकते हैं।\n"
                "• **खान-पान व तरल पदार्थ:** खूब सारा ओआरएस (ORS), नारियल पानी, गुनगुना पानी और हल्का सुपाच्य भोजन (मूंग दाल खिचड़ी या दलिया) लें।\n"
                "• माथे पर सामान्य पानी की ठंडी पट्टी रखें। यदि बुखार 2 दिन से अधिक रहे तो कैंप डॉक्टर से रक्त जांच कराएं।"
            )
        else:
            return (
                "🌡️ **Fever Primary Care & Tablet Guidance:**\n"
                "• **Medication:** Paracetamol 650mg — 1 tablet Morning (08:00 AM) & 1 tablet Night (08:30 PM) after meals. (Maximum 3 tablets in 24 hours if body temperature exceeds 100°F).\n"
                "• **Hydration & Diet:** Drink plenty of ORS electrolyte solution, fresh coconut water, and clean boiled water. Eat light meals such as khichdi, idli, or warm vegetable soup.\n"
                "• **Cold Sponging:** Apply a clean, damp room-temperature cloth to forehead if temp is elevated.\n"
                "👉 If fever persists beyond 2 days or is accompanied by chills or vomiting, see the camp doctor immediately."
            )

    # 2B. COUGH, COLD, SORE THROAT, SNEEZING
    cold_triggers = ['cough', 'cold', 'khasi', 'zukam', 'kemmu', 'throat', 'sore throat', 'sneeze', 'flu', 'खांसी', 'जुकाम', 'ಕೆಮ್ಮು', 'ನೆಗಡಿ']
    if any(t in q for t in cold_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "☕ **ಕೆಮ್ಮು ಮತ್ತು ಶೀತ ಪರಿಹಾರ (Cough & Cold Care):**\n"
                "• **ಮಾತ್ರೆ:** ಅಲರ್ಜಿ ಮತ್ತು ಸೀನು ಇದ್ದರೆ ರಾತ್ರಿ ಊಟದ ನಂತರ **Cetirizine 10mg** (1 ಮಾತ್ರೆ ರಾತ್ರಿ 8:30 PM).\n"
                "• ದಿನಕ್ಕೆ 2 ಬಾರಿ ಬಿಸಿ ನೀರಿನ ಉಗಿ (Steam inhalation) ತೆಗೆದುಕೊಳ್ಳಿ ಮತ್ತು ಉಪ್ಪು ನೀರಿನಿಂದ ಗಂಟಲು ಮುಕ್ಕಳಿಸಿ.\n"
                "• ತುಳಸಿ-ಶುಂಠಿ ಕಷಾಯ ಕುಡಿಯಿರಿ; ತಣ್ಣನೆಯ ಪದಾರ್ಥಗಳನ್ನು ತ್ಯಜಿಸಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "☕ **खांसी, जुकाम व गले में खराश के लिए परामर्श:**\n"
                "• **दवा:** रात को भोजन के बाद **Cetirizine 10mg** (1 गोली रात 8:30 PM) और कफ सिरप (10ml दोपहर व रात)।\n"
                "• **घरेलू उपाय:** दिन में 2 बार गर्म पानी की भाप (Steam) लें और गुनगुने पानी में थोड़ा नमक डालकर गरारे करें।\n"
                "• तुलसी-अदरक का गर्म काढ़ा पिएं। ठंडे पेय और आइसक्रीम से पूरी तरह परहेज रखें।"
            )
        else:
            return (
                "☕ **Cough, Cold & Sore Throat Primary Care:**\n"
                "• **Medication:** Cetirizine 10mg — 1 tablet at Night (08:30 PM) after food for allergic sneezing/runny nose. Use warm saline gargles for throat irritation.\n"
                "• **Steam Inhalation:** Inhale steam twice daily for 5-7 minutes to loosen congestion.\n"
                "• **Diet:** Sip warm ginger-tulsi water, herbal tea, or warm soup. Avoid chilled water and fried snacks."
            )

    # 2C. ACIDITY, GAS, STOMACH PAIN, HEARTBURN
    stomach_triggers = ['acidity', 'gas', 'acid', 'heartburn', 'pet dard', 'hottenovu', 'stomach', 'indigestion', 'gastric', 'pet me dard', 'पेट दर्द', 'ಅಸಿಡಿಟಿ', 'ಹೊಟ್ಟೆ ನೋವು']
    if any(t in q for t in stomach_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🌿 **ಅಸಿಡಿಟಿ ಮತ್ತು ಹೊಟ್ಟೆ ನೋವು ಪರಿಹಾರ (Acidity Care):**\n"
                "• **Pantoprazole 40mg:** ಬೆಳಿಗ್ಗೆ ಖಾಲಿ ಹೊಟ್ಟೆಯಲ್ಲಿ 1 ಮಾತ್ರೆ (ಉಪಾಹಾರಕ್ಕೆ 30 ನಿಮಿಷ ಮೊದಲು).\n"
                "• ಖಾರ, ಮಸಾಲೆ, ಹುರಿದ ತಿಂಡಿಗಳು ಮತ್ತು ಖಾಲಿ ಹೊಟ್ಟೆಯಲ್ಲಿ ಚಹಾ/ಕಾಫಿ ಕುಡಿಯುವುದನ್ನು ತಪ್ಪಿಸಿ.\n"
                "• ತಾಜಾ ಮಜ್ಜಿಗೆ, ಎಳನೀರು ಅಥವಾ ತಣ್ಣನೆಯ ಹಾಲು ಕುಡಿಯಿರಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🌿 **एसिडिटी, पेट दर्द व गैस के लिए परामर्श:**\n"
                "• **दवा:** **Pantoprazole 40mg** — सुबह खाली पेट 1 गोली (नाश्ते से 30 मिनट पहले एक गिलास पानी के साथ)।\n"
                "• **परहेज:** ज्यादा तीखा, तला-भुना, मिर्च-मसाला और खाली पेट तेज चाय/कॉफी बंद करें।\n"
                "• ठंडा दूध, छाछ (मट्ठा) और नारियल पानी पिएं। भोजन के तुरंत बाद न लेटें।"
            )
        else:
            return (
                "🌿 **Acidity, Heartburn & Gastric Pain Guidance:**\n"
                "• **Medication:** Pantoprazole 40mg — 1 tablet in the Morning (08:00 AM) on an empty stomach, 30 minutes before breakfast.\n"
                "• **Diet:** Avoid deep-fried roadside snacks, heavy spices, and raw chillies. Do not drink tea/coffee on an empty stomach.\n"
                "• Drink fresh buttermilk, tender coconut water, or cold milk to soothe stomach lining."
            )

    # 2D. HIGH BLOOD PRESSURE / HYPERTENSION
    bp_triggers = ['bp', 'blood pressure', 'hypertension', 'pressure', 'othada', 'raktadottada', 'बीपी', 'रक्तचाप', 'ರಕ್ತದೊತ್ತಡ']
    if any(t in q for t in bp_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "❤️ **ಅಧಿಕ ರಕ್ತದೊತ್ತಡ ನಿಯಂತ್ರಣ (High BP Advice):**\n"
                "• ಅಡುಗೆಯಲ್ಲಿ ಉಪ್ಪಿನ (Salt) ಪ್ರಮಾಣವನ್ನು ಗಣನೀಯವಾಗಿ ಕಡಿಮೆ ಮಾಡಿ. ಉಪ್ಪಿನಕಾಯಿ ಮತ್ತು ಹಪ್ಪಳ ಬೇಡ.\n"
                "• ವೈದ್ಯರು ಸೂಚಿಸಿದ ಬಿಪಿ ಮಾತ್ರೆಗಳನ್ನು (Amlodipine/Telmisartan) ಬೆಳಿಗ್ಗೆ ಉಪಾಹಾರದ ನಂತರ ತಪ್ಪದೇ ಸೇವಿಸಿ.\n"
                "• ತಲೆಸುತ್ತು ಅಥವಾ ಎದೆ ಬಡಿತ ಹೆಚ್ಚಿದ್ದರೆ ಕ್ಯಾಂಪಿನ ಕೌಂಟರ್ 2 ರಲ್ಲಿ ತಕ್ಷಣ ಬಿಪಿ ತಪಾಸಣೆ ಮಾಡಿಸಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "❤️ **हाई बीपी (रक्तचाप) नियंत्रण सलाह:**\n"
                "• भोजन में ऊपर से कच्चा नमक, अचार, पापड़ और नमकीन पूरी तरह बंद करें।\n"
                "• डॉक्टर द्वारा निर्धारित बीपी की दवा (Amlodipine/Telmisartan) रोजाना सुबह 8:00 AM नाश्ते के बाद नियम से लें।\n"
                "• लौकी का सूप, खीरा, पपीता और नारियल पानी लें। सिर चकराने पर काउंटर 2 पर तुरंत बीपी चेक करवाएं।"
            )
        else:
            return (
                "❤️ **High Blood Pressure (Hypertension) Care:**\n"
                "• **Dietary Sodium:** Strictly eliminate extra table salt, pickles (aachar), and salted papad.\n"
                "• **Medication:** Take your prescribed anti-hypertensive (e.g. Amlodipine 5mg) in the Morning (08:00 AM) after breakfast without skipping.\n"
                "• If systolic BP exceeds 160 or you experience dizziness/headache, visit Camp Counter 2 for an urgent reading."
            )

    # 2E. DIABETES / HIGH BLOOD SUGAR
    sugar_triggers = ['sugar', 'diabetes', 'madhumeh', 'sakkare', 'glucose', 'shugar', 'शुगर', 'मधुमेह', 'ಸಕ್ಕರೆ']
    if any(t in q for t in sugar_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🩺 **ಮಧುಮೇಹ ಮತ್ತು ಸಕ್ಕರೆ ನಿಯಂತ್ರಣ (Diabetes Guidance):**\n"
                "• ಸಿಹಿ ತಿನಿಸುಗಳು, ಬೆಲ್ಲ, ಮೈದಾ, ಬೇಕರಿ ಪದಾರ್ಥಗಳು ಮತ್ತು ಅತಿಯಾದ ಬಿಳಿ ಅನ್ನವನ್ನು ಮಿತಿಗೊಳಿಸಿ.\n"
                "• ಮೆಂತ್ಯ ಕಾಳು, ಹಾಗಲಕಾಯಿ, ಹಸಿರು ತರಕಾರಿ ಮತ್ತು ಜೋಳದ ರೊಟ್ಟಿ ಉತ್ತಮ.\n"
                "• ಮೆಟ್‌ಫಾರ್ಮಿನ್ (Metformin) ಮಾತ್ರೆಗಳನ್ನು ಊಟದ ಜೊತೆಗೆ ವೈದ್ಯರ ಸಲಹೆಯಂತೆ ಸೇವಿಸಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🩺 **डायबिटीज व ब्लड शुगर नियंत्रण सलाह:**\n"
                "• सफेद चीनी, गुड़, मिठाइयां, मैदा, सफेद चावल और कोल्ड ड्रिंक्स से पूरी तरह परहेज करें।\n"
                "• मेथी दाना पानी, करेला, हरी पत्तेदार सब्जियां और चने/जौ की मल्टीग्रेन रोटी खाएं।\n"
                "• शुगर की दवा (Metformin) सुबह व रात भोजन के साथ नियमित लें और रोजाना 30 मिनट टहलें।"
            )
        else:
            return (
                "🩺 **Diabetes & Blood Sugar Guidance:**\n"
                "• **Diet:** Completely avoid refined sugar, sweets, jaggery, maida, and sweet fruit juices.\n"
                "• **Beneficial Foods:** Include methi seeds (fenugreek), bitter gourd (karela), green vegetables, and multigrain rotis.\n"
                "• Take prescribed antidiabetic tablets (e.g., Metformin 500mg) with meals as directed."
            )

    # 2F. WEAKNESS, ANEMIA, FATIGUE, DIZZINESS
    weakness_triggers = ['weakness', 'fatigue', 'kamzori', 'tired', 'dizzy', 'anemia', 'blood less', 'कमजोरी', 'ಸುಸ್ತು', 'susthu']
    if any(t in q for t in weakness_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "💪 **ದೈಹಿಕ ದೌರ್ಬಲ್ಯ ಮತ್ತು ಆಯಾಸ ಪರಿಹಾರ (Weakness Care):**\n"
                "• ಬೆಳಿಗ್ಗೆ ಉಪಾಹಾರದ ನಂತರ 1 ಮಲ್ಟಿವಿಟಮಿನ್ ಮಾತ್ರೆ (Multivitamin with Zinc) ತೆಗೆದುಕೊಳ್ಳಿ.\n"
                "• ದಾಳಿಂಬೆ, ಪಾಲಕ್ ಸೊಪ್ಪು, ಖರ್ಜೂರ ಮತ್ತು ಬೆಲ್ಲ-ಕಡಲೆಬೀಜ ಸೇವಿಸಿ (ರಕ್ತ ಹೆಚ್ಚಿಸಲು).\n"
                "• ಸಾಕಷ್ಟು ನೀರು ಕುಡಿಯಿರಿ ಮತ್ತು ಕ್ಯಾಂಪಿನಲ್ಲಿ ಹಿಮೋಗ್ಲೋಬಿನ್ ತಪಾಸಣೆ ಮಾಡಿಸಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "💪 **शारीरिक कमजोरी व थकान के लिए परामर्श:**\n"
                "• सुबह नाश्ते के बाद एक मल्टीविटामिन व जिंक की गोली (Multivitamin + Zinc) लें।\n"
                "• खून की कमी दूर करने के लिए पालक, अनार, चुकंदर, खजूर और गुड़-चना खाएं।\n"
                "• दिनभर में 8-10 गिलास पानी पिएं और कैंप में हीमोग्लोबिन की जांच करवाएं।"
            )
        else:
            return (
                "💪 **General Weakness & Fatigue Support:**\n"
                "• Take a daily Multivitamin with Zinc tablet in the Morning (08:00 AM) after breakfast.\n"
                "• Boost iron levels naturally with spinach, pomegranates, beetroot, dates, and jaggery-roasted chana.\n"
                "• Ensure adequate sleep and check hemoglobin levels at Camp Counter 2."
            )

    # -------------------------------------------------------------------------
    # PRIORITY 3: DIET & NUTRITION QUERIES (Only if no specific symptom above)
    # -------------------------------------------------------------------------
    diet_triggers = ['diet', 'food', 'khana', 'kya khaye', 'parhez', 'aahar', 'oota', 'tindi', 'आहार', 'खान-पान', 'ಆಹಾರ']
    if any(t in q for t in diet_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🥗 **ಆರೋಗ್ಯಕರ ಭಾರತೀಯ ಆಹಾರ ಸಲಹೆ (Healthy Diet):**\n"
                "• **ಸೇವಿಸಿ:** ಹಸಿರು ತರಕಾರಿಗಳು (ನುಗ್ಗೆಕಾಯಿ, ಪಾಲಕ್), ಜೋಳ/ಗೋಧಿ ರೊಟ್ಟಿ, ಹೆಸರುಕಾಳು ಮತ್ತು ಮಜ್ಜಿಗೆ.\n"
                "• **ತ್ಯಜಿಸಿ:** ಅತಿಯಾದ ಉಪ್ಪು, ಉಪ್ಪಿನಕಾಯಿ, ಎಣ್ಣೆಯಲ್ಲಿ ಕರಿದ ತಿಂಡಿಗಳು ಮತ್ತು ಬಿಳಿ ಸಕ್ಕರೆ.\n"
                "• ದಿನಕ್ಕೆ ಕನಿಷ್ಠ 8-10 ಲೋಟ ಶುದ್ಧ ನೀರು ಕುಡಿಯಿರಿ."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🥗 **स्वस्थ भारतीय आहार व पोषण नियम:**\n"
                "• **खाएं:** मौसमी हरी सब्जियां (लौकी, पालक, तोरई), अंकुरित मूंग, चने की रोटी और ताजा छाछ।\n"
                "• **परहेज:** ज्यादा नमक, बाजार के तले-भुने समोसे-पकौड़े, अचार और सफेद चीनी।\n"
                "• दिनभर में 8-10 गिलास साफ उबला/फिल्टर किया हुआ पानी जरूर पिएं।"
            )
        else:
            return (
                "🥗 **Healthy Community Diet & Nutrition Principles:**\n"
                "• **Foods to Eat:** Fresh green vegetables (gourd, spinach, fenugreek), whole lentils, sprouts, and fresh buttermilk.\n"
                "• **Foods to Avoid:** Excessive table salt, roadside fried snacks, commercial sweets, and stored oily foods.\n"
                "• Stay well-hydrated with 8-10 glasses of clean drinking water daily."
            )

    # -------------------------------------------------------------------------
    # PRIORITY 4: GENERIC TABLET DOSAGE TIMINGS (ONLY if no symptom was given!)
    # -------------------------------------------------------------------------
    timing_triggers = ['timing', 'time', 'samay', 'schedule', 'tablets', 'dose', 'when to take', 'समय', 'ಮಾತ್ರೆ ಸಮಯ']
    if any(t in q for t in timing_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🕒 **ಕ್ಯಾಂಪ್ ಮಾತ್ರೆಗಳ ಸಾಮಾನ್ಯ ವೇಳಾಪಟ್ಟಿ (1-0-1 Schedule):**\n"
                "• **ಬೆಳಿಗ್ಗೆ (08:00 AM):** ಬಿಪಿ, ಥೈರಾಯ್ಡ್ ಮತ್ತು ಮಲ್ಟಿವಿಟಮಿನ್ ಮಾತ್ರೆಗಳು (ಉಪಾಹಾರದ ನಂತರ).\n"
                "• **ಮಧ್ಯಾಹ್ನ (01:30 PM):** ಆಂಟಿಬಯೋಟಿಕ್ ಅಥವಾ ಜೀರ್ಣಕ್ರಿಯೆ ಮಾತ್ರೆಗಳು (ಊಟದ ನಂತರ).\n"
                "• **ರಾತ್ರಿ (08:30 PM):** ಕೊಲೆಸ್ಟ್ರಾಲ್, ಅಲರ್ಜಿ (Cetirizine) ಮತ್ತು ನಿದ್ರೆ ಮಾತ್ರೆಗಳು (ರಾತ್ರಿ ಊಟದ ನಂತರ).\n"
                "👉 ನಿಮ್ಮ ನಿಖರವಾದ ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್ ತಿಳಿಯಲು ರೋಗಲಕ್ಷಣಗಳನ್ನು ನಮೂದಿಸಿ!"
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🕒 **कैंप दवाइयों का दैनिक समय-सारणी (Daily Tablet Timings):**\n"
                "• **सुबह (08:00 AM):** बीपी, थायराइड व मल्टीविटामिन दवाइयां — नाश्ते के बाद लें।\n"
                "• **दोपहर (01:30 PM):** एंटीबायोटिक या पाचन की दवा — दोपहर भोजन के बाद।\n"
                "• **रात (08:30 PM):** कोलेस्ट्रॉल, एलर्जी व रात की शुगर की दवा — रात के खाने के बाद।\n"
                "👉 मरीज की विशेष दवा जानने के लिए पहले अपने लक्षण बताएं।"
            )
        else:
            return (
                "🕒 **Standard Health Camp Tablet Schedule (1-0-1 Routine):**\n"
                "• **Morning (08:00 AM):** Blood pressure, thyroid, and daily multivitamins *(after breakfast)*.\n"
                "• **Afternoon (01:30 PM):** Antibiotics or digestive enzymes *(after lunch)*.\n"
                "• **Night (08:30 PM):** Cholesterol, allergy relief, and bedtime tablets *(after dinner)*.\n"
                "👉 To view patient-specific medications, please record presenting symptoms."
            )

    # -------------------------------------------------------------------------
    # PRIORITY 5: CAMP NAVIGATION & COUNTER ASSISTANCE
    # -------------------------------------------------------------------------
    counter_triggers = ['counter', 'kaha', 'kahan', 'where', 'token', 'line', 'room', 'pharmacy', 'ಕೌಂಟರ್', 'काउंटर']
    if any(t in q for t in counter_triggers):
        if lang in ['kannada', 'kannada_translit']:
            return (
                "🏢 **ಕ್ಯಾಂಪ್ ಕೌಂಟರ್ ಮಾರ್ಗದರ್ಶಿ (Camp Navigation):**\n"
                "• **ಕೌಂಟರ್ 1:** ರೋಗಿ ನೋಂದಣಿ ಮತ್ತು QR ಪಾಸ್ ಪಡೆಯುವುದು.\n"
                "• **ಕೌಂಟರ್ 2:** ಬಿಪಿ, ಶುಗರ್ ಹಾಗೂ ತೂಕ ತಪಾಸಣೆ.\n"
                "• **ಕೌಂಟರ್ 3 & 4:** ಪರಿಣಿತ ವೈದ್ಯರ ಸಮಾಲೋಚನೆ ಕೊಠಡಿ.\n"
                "• **ಕೌಂಟರ್ 5:** ಉಚಿತ ಔಷಧಿ ವಿತರಣಾ ಕೇಂದ್ರ (Pharmacy)."
            )
        elif lang in ['hindi', 'hinglish']:
            return (
                "🏢 **हेल्थ कैंप काउंटर जानकारी (Camp Navigation):**\n"
                "• **काउंटर 1:** नया रजिस्ट्रेशन व डिजिटल QR पास प्राप्त करें।\n"
                "• **काउंटर 2:** बीपी, शुगर व वजन की त्वरित जांच।\n"
                "• **काउंटर 3 व 4:** विशेषज्ञ डॉक्टर परामर्श कक्ष।\n"
                "• **काउंटर 5:** मुफ्त दवा वितरण (Pharmacy Counter)।"
            )
        else:
            return (
                "🏢 **Camp Counter Navigation:**\n"
                "• **Counter 1:** Patient Registration & Digital QR Pass issuance.\n"
                "• **Counter 2:** Vital Signs Screening (BP, SpO2, Random Blood Sugar).\n"
                "• **Counter 3 & 4:** Specialist Doctor Consultation Chambers.\n"
                "• **Counter 5:** Free Pharmacy & Medicine Dispensation Counter."
            )

    # -------------------------------------------------------------------------
    # DEFAULT COMPASSIONATE GREETING
    # -------------------------------------------------------------------------
    if lang in ['kannada', 'kannada_translit']:
        return (
            "ನಮಸ್ಕಾರ! 🙏 ನಾನು ನಿಮ್ಮ ಸ್ಮಾರ್ಟ್ ಹೆಲ್ತ್ ಕ್ಯಾಂಪ್ AI ಸಹಾಯಕ.\n"
            "ನೀವು ಜ್ವರ, ಕೆಮ್ಮು, ಬಿಪಿ, ಸಕ್ಕರೆ ಕಾಯಿಲೆ, ಮಾತ್ರೆಗಳ ಸಮಯ, ಆಹಾರ ಪದ್ಧತಿ ಅಥವಾ 108 ಆಂಬ್ಯುಲೆನ್ಸ್ ಬಗ್ಗೆ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಕೇಳಬಹುದು. "
            "ಕ್ಯಾಂಪ್ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಲು ಹಿಂಜರಿಯಬೇಡಿ!"
        )
    elif lang in ['hindi', 'hinglish']:
        return (
            "नमस्ते! 🙏 मैं आपका स्मार्ट हेल्थ कैंप AI सहायक हूं।\n"
            "आप मुझसे बुखार, खांसी, बीपी, शुगर, दवा लेने का समय, उचित खान-पान या 108 एम्बुलेंस के बारे में कोई भी प्रश्न पूछ सकते हैं। "
            "कैंप में मौजूद विशेषज्ञ डॉक्टर से परामर्श अवश्य लें।"
        )
    else:
        return (
            "Hello! 🙏 I am your Smart Community Health Camp AI Assistant.\n"
            "You can ask me about fever, cough, high BP, diabetes, tablet dosage schedules, healthy diet, camp counters, or 108 ambulance help. "
            "Feel free to consult our empaneled camp doctors on duty!"
        )


def call_gemini_api(prompt: str, user_lang: str) -> str:
    """
    Call Google Gemini API if GEMINI_API_KEY is available.
    """
    api_key = os.environ.get('GEMINI_API_KEY') or (current_app.config.get('GEMINI_API_KEY') if current_app else None)
    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    lang_instruction = {
        'kannada': 'Respond purely in authentic KANNADA (ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ) with compassionate medical phrasing.',
        'kannada_translit': 'Respond in conversational KANNADA using Roman English transliteration (e.g. "Namaskara, jwara idre Paracetamol tagolli...").',
        'hindi': 'Respond purely in standard HINDI (हिन्दी देवनागरी में) with polite clinical guidance.',
        'hinglish': 'Respond in friendly HINGLISH (e.g. "Namaste! Bukhar ke liye Paracetamol le sakte hain...").',
        'english': 'Respond in clear, simple ENGLISH with empathetic clinical tone.'
    }.get(user_lang, 'Respond clearly in the user\'s language.')

    system_instruction = (
        "You are an empathetic, clinical AI Doctor & Health Camp Guide for community outreach camps in India. "
        f"{lang_instruction} "
        "Keep answers concise (under 90 words), bulleted, and practical. "
        "CRITICAL CLINICAL RULES: "
        "1. If user has fever, prioritize Paracetamol 650mg morning & night after food, hydration, and doctor visit. "
        "2. If chest pain or emergency signs, tell them to call 108 immediately. "
        "3. Always advise visiting the camp doctor on duty."
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{system_instruction}\n\nUser Question: {prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 250
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                res_body = json.loads(response.read().decode('utf-8'))
                candidates = res_body.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        return parts[0].get('text', '').strip()
    except Exception:
        pass
    
    return None


def universal_health_chatbot(query: str, patient_context: dict = None) -> dict:
    """
    Main entry point for universal health chatbot.
    """
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return {
            'status': 'success',
            'reply': "Hello! I am your Multilingual Camp Assistant. Ask me anything in English, Hindi (हिन्दी), Kannada (ಕನ್ನಡ), or Hinglish! 🙏",
            'language': 'english',
            'source': 'system'
        }

    lang = detect_language(cleaned_query)

    # 1. Try Gemini API if configured
    gemini_reply = call_gemini_api(cleaned_query, lang)
    if gemini_reply:
        return {
            'status': 'success',
            'reply': gemini_reply,
            'language': lang,
            'source': 'gemini_ai'
        }

    # 2. Priority-ordered clinical fallback engine
    fallback_reply = priority_multilingual_clinical_response(cleaned_query, lang)
    return {
        'status': 'success',
        'reply': fallback_reply,
        'language': lang,
        'source': 'clinical_ai_engine'
    }


# =============================================================================
# 3. SYMPTOM-FIRST TABLET SCHEDULE GENERATOR
# =============================================================================

def get_symptom_based_prescription(symptoms: str = "", age: int = None, urgency_level: str = "NORMAL") -> dict:
    """
    Symptom-First Clinical Prescription & Dosage Schedule Engine.
    Only generates prescription & timing if symptoms/condition are recorded.
    """
    symptoms_clean = (symptoms or "").strip()
    
    if not symptoms_clean:
        return {
            'has_prescription': False,
            'message': 'Prescription and dosage schedule will be unlocked after recording the patient symptoms / clinical evaluation.',
            'suggested_prescription': None,
            'morning': [],
            'afternoon': [],
            'night': [],
            'diet_tip': 'Maintain balanced nutrition and adequate hydration.',
            'urgency_flag': urgency_level or 'NORMAL'
        }

    s = symptoms_clean.lower()
    meds = []
    morning_slots = []
    afternoon_slots = []
    night_slots = []
    diet_tips = []

    # 1. Fever / Bukhar / Temperature
    if any(k in s for k in ['fever', 'bukhar', 'jwara', 'taap', 'temperature', 'body ache', 'dard', 'pain', 'chills']):
        meds.append("Paracetamol 650mg - 1 tab BD after food x 3 days")
        morning_slots.append("Paracetamol 650mg (1 tab - 08:00 AM after breakfast)")
        night_slots.append("Paracetamol 650mg (1 tab - 08:30 PM after dinner)")
        diet_tips.append("Drink 2-3 liters of clean boiled water, ORS solution, and light khichdi.")

    # 2. High Blood Pressure / Chest Heaviness / Headache
    if any(k in s for k in ['bp', 'hypertension', 'pressure', 'headache', 'sir dard', 'talenovu', 'dizziness']):
        meds.append("Amlodipine 5mg - 1 tab OD Morning after food")
        morning_slots.append("Amlodipine 5mg (1 tab - 08:00 AM after breakfast)")
        diet_tips.append("Strictly reduce table salt, pickles, and salted papad.")

    # 3. Cough / Cold / Throat Irritation / Sneezing
    if any(k in s for k in ['cough', 'cold', 'khasi', 'zukam', 'kemmu', 'throat', 'gala', 'sneeze']):
        meds.append("Cetirizine 10mg - 1 tab Night after food x 5 days")
        meds.append("Cough Expectorant Syrup - 10ml TDS")
        afternoon_slots.append("Cough Syrup (10ml - 01:30 PM after lunch)")
        night_slots.append("Cetirizine 10mg (1 tab) + Cough Syrup (10ml - 08:30 PM)")
        diet_tips.append("Inhale steam with warm water twice daily; avoid cold drinks.")

    # 4. Acidity / Gastric Pain / Heartburn / Burning Sensation
    if any(k in s for k in ['acid', 'gas', 'pet dard', 'hottenovu', 'stomach', 'burning', 'jalans']):
        meds.append("Pantoprazole 40mg - 1 tab OD Morning on empty stomach x 7 days")
        morning_slots.append("Pantoprazole 40mg (1 tab - 08:00 AM empty stomach before breakfast)")
        diet_tips.append("Avoid excessively spicy curries, deep-fried snacks, and late-night dinners.")

    # 5. Diabetes / High Sugar / Frequent Urination
    if any(k in s for k in ['sugar', 'diabetes', 'meetha', 'sakkare', 'glucose', 'urination']):
        meds.append("Metformin 500mg - 1 tab BD with meals")
        morning_slots.append("Metformin 500mg (1 tab - 08:00 AM with breakfast)")
        night_slots.append("Metformin 500mg (1 tab - 08:30 PM with dinner)")
        diet_tips.append("Avoid refined sugar, jaggery, sweets, and white rice; walk 30 mins daily.")

    # 6. Bacterial Infection / Wound / Throat Soreness
    if any(k in s for k in ['infection', 'wound', 'pus', 'sore', 'swelling', 'tonsil']):
        meds.append("Amoxicillin 500mg - 1 cap BD after food x 5 days")
        morning_slots.append("Amoxicillin 500mg (1 cap - 08:00 AM after breakfast)")
        night_slots.append("Amoxicillin 500mg (1 cap - 08:30 PM after dinner)")
        diet_tips.append("Keep wounds clean and dry; maintain personal hygiene.")

    # 7. General Weakness / Fatigue / Joint Pain
    if any(k in s for k in ['weakness', 'fatigue', 'kamzori', 'joint', 'tired', 'chakkar', 'anemia']):
        meds.append("Multivitamin with Zinc - 1 tab OD Morning after food x 15 days")
        morning_slots.append("Multivitamin + Zinc (1 tab - 08:00 AM after breakfast)")
        diet_tips.append("Include fresh seasonal fruits, whole dal, dates, and boiled milk.")

    # Fallback if non-empty symptoms didn't match triggers
    if not meds:
        meds.append("Oral Rehydration Salts (ORS) & Multivitamin - 1 tab OD Morning")
        morning_slots.append("Multivitamin & Vital Electrolytes (08:00 AM after breakfast)")
        diet_tips.append("Stay well hydrated and take light wholesome meals.")

    prescription_text = "\n".join(meds)
    diet_text = " ".join(diet_tips) if diet_tips else "Maintain wholesome balanced nutrition and clean drinking water."

    return {
        'has_prescription': True,
        'symptoms_recorded': symptoms_clean,
        'suggested_prescription': prescription_text,
        'morning': morning_slots,
        'afternoon': afternoon_slots,
        'night': night_slots,
        'diet_tip': diet_text,
        'urgency_flag': urgency_level or 'NORMAL'
    }


# =============================================================================
# 4. GAMIFIED HEALTH CAMP DASHBOARD HERO BANNER & XP PROGRESS
# =============================================================================

def compute_camp_gamification(camps_list=None, patients_list=None, records_list=None, doctors_list=None, dispatch_logs_list=None) -> dict:
    """
    Computes gamified Community Health Impact metrics and Tier Level:
    - 🌟 Bronze Seva Starter (0 - 499 XP)
    - 🥈 Silver Responder (500 - 1199 XP)
    - 🥇 Gold Rural Healthcare Hero (1200 - 2499 XP)
    - 🏆 Platinum Health Champion (2500+ XP)
    """
    if patients_list is None:
        try:
            from models import Patient
            patients_list = Patient.query.all()
        except Exception:
            patients_list = []
    if records_list is None:
        try:
            from models import HealthRecord
            records_list = HealthRecord.query.all()
        except Exception:
            records_list = []
    if camps_list is None:
        try:
            from models import Camp
            camps_list = Camp.query.all()
        except Exception:
            camps_list = []
    if doctors_list is None:
        try:
            from models import Doctor
            doctors_list = Doctor.query.all()
        except Exception:
            doctors_list = []
    if dispatch_logs_list is None:
        try:
            from upgraded_features import AmbulanceDispatchLog
            dispatch_logs_list = AmbulanceDispatchLog.query.all()
        except Exception:
            dispatch_logs_list = []

    total_beneficiaries = len(patients_list) if patients_list else 0
    total_records = len(records_list) if records_list else 0
    total_camps = len(camps_list) if camps_list else 0
    total_doctors = len(doctors_list) if doctors_list else 0
    total_dispatches = len(dispatch_logs_list) if dispatch_logs_list else 0

    # Critical triage saves (records with is_critical or ambulance dispatches)
    critical_saves = sum(1 for r in records_list if getattr(r, 'is_critical', False)) + total_dispatches

    # Compute Gamification XP
    # 50 XP per patient screened + 150 XP per critical emergency save + 40 XP per prescription + 200 XP per camp
    total_xp = (total_beneficiaries * 50) + (critical_saves * 150) + (total_records * 40) + (total_camps * 200)
    total_xp = max(100, total_xp)

    # Tier Levels
    if total_xp < 500:
        level_tier = "Bronze Seva Starter"
        level_badge = "🌟 Bronze Seva Starter"
        level_color = "warning"
        level_icon = "fa-shield-heart"
        tier_min = 0
        tier_max = 500
    elif total_xp < 1200:
        level_tier = "Silver Responder"
        level_badge = "🥈 Silver Responder"
        level_color = "secondary"
        level_icon = "fa-medal"
        tier_min = 500
        tier_max = 1200
    elif total_xp < 2500:
        level_tier = "Gold Rural Healthcare Hero"
        level_badge = "🥇 Gold Rural Healthcare Hero"
        level_color = "warning"
        level_icon = "fa-crown"
        tier_min = 1200
        tier_max = 2500
    else:
        level_tier = "Platinum Health Champion"
        level_badge = "🏆 Platinum Health Champion"
        level_color = "info"
        level_icon = "fa-trophy"
        tier_min = 2500
        tier_max = 5000

    # Progress bar percentage in current tier
    tier_range = tier_max - tier_min
    progress_in_tier = max(0, total_xp - tier_min)
    progress_percent = min(100, max(5, int((progress_in_tier / float(tier_range)) * 100)))
    xp_to_next_tier = max(0, tier_max - total_xp)

    return {
        'total_xp': total_xp,
        'level_tier': level_tier,
        'level_badge': level_badge,
        'level_color': level_color,
        'level_icon': level_icon,
        'tier_min': tier_min,
        'tier_max': tier_max,
        'progress_percent': progress_percent,
        'xp_to_next_tier': xp_to_next_tier,
        'total_beneficiaries': total_beneficiaries,
        'critical_saves': critical_saves,
        'total_records': total_records,
        'total_camps': total_camps,
        'total_doctors': total_doctors,
        'volunteer_hours': total_doctors * 8
    }


# =============================================================================
# 5. PATIENT HEALTH WELLNESS SCORE & 4-STEP JOURNEY TRACKER
# =============================================================================

def calculate_patient_wellness_score(patient, latest_record=None) -> dict:
    """
    Computes a color-coded Patient Health Wellness Score (0 - 100)
    derived from vitals (BP, SpO2, Blood Sugar) and urgency status.
    """
    score = 100
    deductions = []

    # 1. Urgency status penalty
    urgency = getattr(patient, 'urgency_level', 'NORMAL') or 'NORMAL'
    if urgency == 'EMERGENCY':
        score -= 30
        deductions.append("Critical Emergency triage flag (-30)")
    elif urgency == 'URGENT':
        score -= 15
        deductions.append("Urgent triage priority flag (-15)")

    # 2. Vitals assessment from latest record
    if latest_record:
        sys = getattr(latest_record, 'systolic_bp', None)
        dia = getattr(latest_record, 'diastolic_bp', None)
        spo2 = getattr(latest_record, 'spo2', None)
        rbs = getattr(latest_record, 'blood_sugar', None)

        # BP
        if sys and dia:
            if sys >= 180 or dia >= 120 or sys < 90:
                score -= 30
                deductions.append("Critical Blood Pressure threshold (-30)")
            elif sys >= 140 or dia >= 90:
                score -= 15
                deductions.append("Elevated Blood Pressure (-15)")

        # SpO2
        if spo2:
            if spo2 < 92:
                score -= 30
                deductions.append("Severe Hypoxia / Low Oxygen (-30)")
            elif spo2 < 95:
                score -= 10
                deductions.append("Borderline Oxygen Saturation (-10)")

        # RBS
        if rbs:
            if rbs >= 300 or rbs <= 60:
                score -= 25
                deductions.append("Severe Glycemic Imbalance (-25)")
            elif rbs >= 200:
                score -= 10
                deductions.append("Elevated Random Blood Sugar (-10)")

    score = max(15, min(100, score))

    if score >= 80:
        label = "Stable & Good Wellness"
        badge_class = "success"
        icon = "fa-circle-check"
    elif score >= 55:
        label = "Moderate Care Needed"
        badge_class = "warning"
        icon = "fa-triangle-exclamation"
    else:
        label = "High Risk / Critical Priority"
        badge_class = "danger"
        icon = "fa-heart-pulse"

    return {
        'score': score,
        'label': label,
        'badge_class': badge_class,
        'icon': icon,
        'deductions': deductions
    }


def get_patient_journey_steps(patient, latest_record=None) -> list:
    """
    Returns the 4-Step Gamified Patient Journey:
    1. Registered ✅ -> 2. Vitals Triaged ✅ -> 3. Doctor Consulted 🩺 -> 4. Digital PDF & Meds Ready 💊
    """
    # Step 1: Registration
    s1_done = bool(patient)
    
    # Step 2: Vitals Triaged
    s2_done = bool(
        latest_record and (
            getattr(latest_record, 'systolic_bp', None) is not None or
            getattr(latest_record, 'spo2', None) is not None or
            getattr(latest_record, 'blood_sugar', None) is not None
        )
    )

    # Step 3: Doctor Consulted
    s3_done = bool(latest_record and getattr(latest_record, 'diagnosis', None))

    # Step 4: Digital PDF & Meds Ready
    s4_done = bool(latest_record and getattr(latest_record, 'prescription', None))

    return [
        {
            'step': 1,
            'title': 'Registered',
            'sub': f'UID: {patient.patient_uid if patient else "Active"}',
            'icon': 'fa-id-card',
            'completed': s1_done,
            'active': not s2_done
        },
        {
            'step': 2,
            'title': 'Vitals Triaged',
            'sub': 'BP, SpO2 & Sugar',
            'icon': 'fa-heart-pulse',
            'completed': s2_done,
            'active': s1_done and not s2_done
        },
        {
            'step': 3,
            'title': 'Doctor Consulted',
            'sub': 'Clinical Diagnosis',
            'icon': 'fa-user-doctor',
            'completed': s3_done,
            'active': s2_done and not s3_done
        },
        {
            'step': 4,
            'title': 'Meds & PDF Ready',
            'sub': 'Dosage & Digital Pass',
            'icon': 'fa-file-pdf',
            'completed': s4_done,
            'active': s3_done and not s4_done
        }
    ]


# =============================================================================
# 6. ROUTE ENDPOINTS
# =============================================================================

@features_v3_bp.route('/api/chatbot', methods=['POST'])
def api_multilingual_chatbot():
    """
    Universal Multilingual AI Chatbot endpoint answering in Hindi, Kannada, English, or Hinglish.
    """
    data = request.get_json(silent=True) or {}
    message = data.get('message') or request.form.get('message') or ""
    
    result = universal_health_chatbot(message)
    return jsonify({
        'reply': result['reply'],
        'language': result['language'],
        'source': result['source'],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    })


@features_v3_bp.route('/register', methods=['GET', 'POST'])
def standalone_register():
    """
    Dedicated Symptom & Urgency Status Patient Registration View.
    """
    from models import db, Patient
    from utils import generate_qr_code

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        age = request.form.get('age', type=int)
        gender = request.form.get('gender', 'Other').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        symptoms = request.form.get('symptoms', '').strip()
        urgency_level = request.form.get('urgency_level', 'NORMAL').strip().upper()

        if not name or not age or not gender:
            flash('Please enter full legal name, age, and gender.', 'danger')
            return redirect(url_for('features_v3_bp.standalone_register'))

        year_str = datetime.utcnow().strftime('%Y')
        count_existing = Patient.query.count() + 1
        patient_uid = f"PAT-{year_str}-{count_existing:04d}"
        while Patient.query.filter_by(patient_uid=patient_uid).first():
            count_existing += 1
            patient_uid = f"PAT-{year_str}-{count_existing:04d}"

        photo_filename = None
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            from werkzeug.utils import secure_filename
            ext = os.path.splitext(photo_file.filename)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                photo_filename = f"{patient_uid}_{int(datetime.utcnow().timestamp())}{ext}"
                upload_dir = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_dir, exist_ok=True)
                photo_file.save(os.path.join(upload_dir, photo_filename))

        qr_dir = current_app.config['QRCODE_FOLDER']
        if request.host_url and 'localhost' not in request.host_url:
            base = request.host_url.rstrip('/')
        else:
            base = os.environ.get('BASE_APP_URL', 'http://127.0.0.1:5000').rstrip('/')
        profile_url = f"{base}/patient_card/{patient_uid}"
        qr_path = generate_qr_code(patient_uid, qr_dir, profile_url=profile_url)

        new_pat = Patient(
            patient_uid=patient_uid,
            name=name,
            age=age,
            gender=gender,
            phone=phone if phone else None,
            address=address if address else None,
            photo_filename=photo_filename,
            qr_code_path=qr_path,
            symptoms=symptoms if symptoms else None,
            urgency_level=urgency_level if urgency_level in ['NORMAL', 'URGENT', 'EMERGENCY'] else 'NORMAL'
        )
        db.session.add(new_pat)
        db.session.commit()

        if urgency_level == 'EMERGENCY':
            flash(f"🚨 EMERGENCY: Patient {name} registered with critical symptoms. Auto-prioritized to #1 in Doctor Queue!", 'danger')
        elif urgency_level == 'URGENT':
            flash(f"⚠️ URGENT: Patient {name} registered with high-priority triage status.", 'warning')
        else:
            flash(f"✅ Patient {name} ({patient_uid}) registered successfully!", 'success')

        return redirect(url_for('patient_card', patient_id=patient_uid))

    return render_template('register.html')
