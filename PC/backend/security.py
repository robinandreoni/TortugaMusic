"""
Tortuga Web / PC Edition - Security & Anti-Leakage Layer
Garantisce la cifratura dei token di streaming, la protezione delle sorgenti
e l'assenza di fughe di dati sensibili (Zero Client Leakage).
"""
import time
import hmac
import hashlib
import json
import base64
from functools import wraps
from flask import request, jsonify
from config import SECRET_KEY, STREAM_TOKEN_TTL

def generate_signed_stream_token(media_id: str, media_type: str = "video", extra: dict = None) -> str:
    """
    Genera un token firmato crittograficamente con HMAC-SHA256.
    Il browser riceve solo questo token opaco invece di URL interni o credenziali.
    """
    expires_at = int(time.time()) + STREAM_TOKEN_TTL
    payload = {
        "mid": str(media_id),
        "typ": media_type,
        "exp": expires_at,
        "ext": extra or {}
    }
    raw_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(raw_json).decode('utf-8').rstrip('=')
    
    # Calcolo firma HMAC con la chiave segreta del server
    signature = hmac.new(SECRET_KEY, b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()[:32]
    
    return f"{b64_payload}.{signature}"

def verify_signed_stream_token(token: str, expected_media_id: str = None) -> dict:
    """
    Verifica e decodifica un token firmato.
    Restituisce il payload se valido e non scaduto, altrimenti None.
    """
    if not token or '.' not in token:
        return None
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        b64_payload, signature = parts
        
        # Verifica firma crittografica
        expected_sig = hmac.new(SECRET_KEY, b64_payload.encode('utf-8'), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        # Decodifica payload
        padding = '=' * (4 - (len(b64_payload) % 4)) if len(b64_payload) % 4 != 0 else ''
        payload_data = base64.urlsafe_b64decode((b64_payload + padding).encode('utf-8'))
        payload = json.loads(payload_data.decode('utf-8'))
        
        # Verifica scadenza temporale
        if time.time() > payload.get("exp", 0):
            return None
        
        # Verifica id se richiesto
        if expected_media_id and str(payload.get("mid")) != str(expected_media_id):
            return None
            
        return payload
    except Exception:
        return None

def sanitize_error(exc: Exception) -> dict:
    """
    Sanitizza gli errori per impedire fughe di dati sul filesystem o stacktrace.
    Nel client viene inviato solo un messaggio sicuro.
    """
    error_msg = str(exc)
    # Rimuove percorsi assoluti Windows o Linux
    if "C:\\" in error_msg or "/home" in error_msg or "/data/" in error_msg:
        return {"error": "Si è verificato un errore interno durante l'elaborazione."}
    return {"error": error_msg[:120] if error_msg else "Errore sconosciuto"}

def apply_security_headers(response):
    """
    Inietta intestazioni di sicurezza HTTP di livello enterprise (Helmet equivalent).
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response
