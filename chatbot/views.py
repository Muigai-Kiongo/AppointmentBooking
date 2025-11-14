import os
import hashlib
import logging
import json
import time
import re
from typing import Optional
from urllib.parse import quote

import requests
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.urls import reverse, NoReverseMatch
from django.shortcuts import render

from .models import ChatLog

logger = logging.getLogger("chatbot")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Rate limiting params (per-IP)
RATE_LIMIT_MAX = getattr(settings, "CHATBOT_RATE_LIMIT_MAX", 5)  # requests
RATE_LIMIT_WINDOW = getattr(settings, "CHATBOT_RATE_LIMIT_WINDOW", 60)  # seconds

# Message length limits
MAX_MESSAGE_LENGTH = getattr(settings, "CHATBOT_MAX_MESSAGE_LENGTH", 2000)
MAX_REPLY_LENGTH = getattr(settings, "CHATBOT_MAX_REPLY_LENGTH", 4000)


def hash_id(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# Basic PHI redaction to avoid sending direct identifiers to third-party APIs.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}(?!\d)")
_NATIONAL_ID_RE = re.compile(r"\b(?:ssn|ssnn|id|passport|nric)[:\s]*\d{3,11}\b", re.IGNORECASE)
_NUMBER_SEQ_RE = re.compile(r"\b\d{6,}\b")  # long numeric sequences


def redact_phi(text: str) -> str:
    """
    Redact obvious PHI-like tokens: emails, phone numbers, labelled national ids,
    and long number sequences. Returns a redacted copy; leaves original unchanged.
    """
    if not text:
        return text
    t = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    t = _PHONE_RE.sub("[REDACTED_PHONE]", t)
    t = _NATIONAL_ID_RE.sub("[REDACTED_ID]", t)
    t = _NUMBER_SEQ_RE.sub("[REDACTED_NUMBER]", t)
    return t


def safe_truncate(s: Optional[str], n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 3] + "..."


def get_client_ip(request) -> str:
    """
    Get client IP for basic rate-limiting. If behind a proxy, ensure your proxy sets X-Forwarded-For.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # X-Forwarded-For can be a comma-separated list; client is first
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def is_rate_limited(ip: str) -> (bool, int):
    """
    Simple sliding window counter using Django cache.
    Returns (is_limited, remaining).
    """
    key = f"chatbot:rl:{ip}"
    try:
        data = cache.get(key)
        if not data:
            # store a tuple (count, reset_ts)
            reset_ts = int(time.time()) + RATE_LIMIT_WINDOW
            cache.set(key, {"count": 1, "reset": reset_ts}, RATE_LIMIT_WINDOW)
            return False, RATE_LIMIT_MAX - 1
        count = data.get("count", 0) + 1
        reset_ts = data.get("reset", int(time.time()) + RATE_LIMIT_WINDOW)
        cache.set(key, {"count": count, "reset": reset_ts}, max(0, reset_ts - int(time.time())))
        if count > RATE_LIMIT_MAX:
            remaining = 0
            return True, remaining
        return False, RATE_LIMIT_MAX - count
    except Exception:
        # If cache fails, do not block traffic — fail open but log.
        logger.exception("Rate limit cache error")
        return False, RATE_LIMIT_MAX


def parse_gemini_response(j: dict) -> str:
    """
    Extract a string reply from a Gemini-style JSON response.
    Contains tolerant parsing for several common shapes.
    """
    if not isinstance(j, dict):
        return json.dumps(j)[:1500]

    # candidates -> content / text
    candidates = j.get("candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            for key in ("content", "text", "message"):
                val = first.get(key)
                if isinstance(val, str):
                    return val.strip()
                if isinstance(val, dict):
                    text = val.get("text") or val.get("content")
                    if isinstance(text, str):
                        return text.strip()

    # choices -> message -> content
    choices = j.get("choices")
    if isinstance(choices, list) and choices:
        c0 = choices[0]
        if isinstance(c0, dict):
            msg = c0.get("message")
            if isinstance(msg, dict):
                text = msg.get("content")
                if isinstance(text, str):
                    return text.strip()
            text = c0.get("text")
            if isinstance(text, str):
                return text.strip()

    # output array -> content/text
    output = j.get("output")
    if isinstance(output, list) and output:
        o0 = output[0]
        if isinstance(o0, dict):
            cont = o0.get("content")
            if isinstance(cont, list) and cont:
                part = cont[0]
                if isinstance(part, dict):
                    txt = part.get("text") or part.get("content")
                    if isinstance(txt, str):
                        return txt.strip()
            txt = o0.get("text") or o0.get("content")
            if isinstance(txt, str):
                return txt.strip()

    # top-level text fields
    for k in ("text", "response", "reply"):
        if k in j and isinstance(j[k], str):
            return j[k].strip()

    # fallback: stringify safely
    return json.dumps(j)[:1500]


def call_gemini_api(message: str, context: Optional[str] = None) -> str:
    """
    Adapter for calling a Gemini API endpoint with small retries and timeouts.
    Uses Django settings first (recommended). Raises on failure.
    """
    url = getattr(settings, "GEMINI_URL", None) or os.environ.get("GEMINI_URL")
    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GEMINI_API_KEY")
    model = getattr(settings, "GEMINI_MODEL", "gemini-lite") or os.environ.get("GEMINI_MODEL", "gemini-lite")

    if not url:
        raise RuntimeError("GEMINI_URL not configured")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        # generic shape; adjust if your endpoint expects different fields
        "model": model,
        "input": message,
        "context": context or "",
        "max_output_tokens": 512,
        "temperature": 0.2,
    }

    # Basic retry/backoff strategy for transient network errors
    backoff = [0, 1, 2]  # seconds
    last_exc = None
    for attempt, wait in enumerate(backoff):
        if attempt > 0:
            time.sleep(wait)
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            j = resp.json()
            return parse_gemini_response(j)
        except requests.RequestException as e:
            last_exc = e
            logger.warning("Gemini request attempt %s failed: %s", attempt + 1, e)
            continue
        except ValueError as e:
            # invalid JSON
            last_exc = e
            logger.exception("Invalid JSON from Gemini: %s", e)
            raise

    # if we reach here, all attempts failed
    raise RuntimeError(f"Gemini API error: {last_exc}")


def generate_reply_fallback(message: str, context: Optional[str] = None) -> str:
    """
    Robust fallback reply generator.

    Behavior:
    - If a primary 'generate_reply' function exists in this module, try calling it (safe-guarded).
    - Otherwise, use lightweight heuristics and canned replies for common medical keywords
      (for example 'rash', 'fever', 'headache', 'appointment') to provide useful guidance.
    - Always avoid raising exceptions; on unexpected errors returns a polite generic fallback.
    - Designed to be safe to call from the main chat view when external model calls fail.
    """
    try:
        # If a project defines a higher-fidelity generator in this module, try it first.
        gen = globals().get("generate_reply")
        if callable(gen):
            try:
                return safe_truncate(gen(message, context=context), MAX_REPLY_LENGTH)
            except Exception:
                logger.exception("generate_reply raised an exception inside fallback; continuing to canned replies.")

        # Attempt other common generator names (if your project added them)
        gen2 = globals().get("generate_reply_from_model") or globals().get("generate_model_reply")
        if callable(gen2):
            try:
                return safe_truncate(gen2(message, context=context), MAX_REPLY_LENGTH)
            except Exception:
                logger.exception("alternative generator failed inside fallback.")

    except Exception:
        # Defensive: ensure fallback never fails fatally
        logger.exception("Unexpected error while attempting to call primary reply generator.")

    # Lower-cased message for simple keyword matching
    text = (message or "").strip().lower()

    # Short, focused triage answers for specific keywords
    if any(k in text for k in ["rash", "rashes", "rashy", "rash-like"]):
        return (
            "I can help with general guidance about rashes. If you have difficulty breathing, facial or throat swelling, "
            "high fever, rapidly spreading rash, or widespread blisters — seek emergency care immediately. "
            "For milder rashes: stop new products, use cool compresses, keep the area clean and dry, apply fragrance-free "
            "moisturizers, and consider an oral antihistamine for itch. If you want, I can ask a few quick questions "
            "to help narrow the cause. (This is general information, not medical advice.)"
        )

    if any(k in text for k in ["fever", "temperature", "hot", "febrile"]):
        return (
            "A fever may be a sign of infection. Drink fluids, rest, and use antipyretics like paracetamol or ibuprofen "
            "as appropriate. Seek urgent care if the fever is very high, persistent, accompanied by severe headache, "
            "neck stiffness, difficulty breathing, or altered consciousness."
        )

    if any(k in text for k in ["headache", "migraine", "head pain"]):
        return (
            "Headaches are common and often caused by tension, dehydration, or migraine. Try rest, hydration, and over-the-counter "
            "pain relief. Seek urgent care if the headache is sudden and severe, accompanied by fever, weakness, confusion, or vision changes."
        )

    if any(k in text for k in ["appointment", "book", "schedule", "reserve"]):
        # Offer a short, actionable reply that the frontend can parse
        return "I can help you book an appointment. Would you like to search available doctors or pick a date and time?"

    if any(k in text for k in ["hi", "hello", "hey", "good morning", "good evening"]):
        return "Hello — how can I help you today? I can help with booking appointments, finding doctors, or answering basic health questions."

    if any(k in text for k in ["thank", "thanks", "thx"]):
        return "You're welcome! Anything else I can help with?"

    # Fallback: try a helpful generic reply that invites clarification
    try:
        # If an external small LLM or system prompt exists (e.g., via env), we might attempt a lightweight API call here.
        # But do not call external systems from fallback by default to avoid unexpected failures.
        return (
            "Sorry, I couldn't process that fully just now. Could you please provide a bit more detail "
            "(for example: symptoms, when they started, and any recent new medicines or exposures)?"
        )
    except Exception:
        logger.exception("Unexpected error inside final fallback.")
        return "Sorry, I couldn't process that right now. Please try again later."


@require_GET
def ping(request):
    return JsonResponse({"ok": True, "time": int(time.time())})


@csrf_exempt
@require_POST
def chat(request):
    """
    POST /chat/
    payload JSON: { "message": "...", "context": "...", "patient_id": "...", "consent": true }
    response JSON: { "reply": "...", "actions": { "suggest_booking": bool, "booking_url": "...",
                                                   "suggest_doctors": bool, "doctors_url": "...",
                                                   "suggest_view_appointments": bool, "appointments_url": "..." } }
    """
    client_ip = get_client_ip(request)
    rl_limited, rl_remaining = is_rate_limited(client_ip)
    if rl_limited:
        reset_key = f"chatbot:rl:{client_ip}"
        data = cache.get(reset_key) or {}
        reset_ts = data.get("reset", int(time.time()) + RATE_LIMIT_WINDOW)
        retry_after = max(0, reset_ts - int(time.time()))
        body = {"error": "rate_limited", "message": "Too many requests", "retry_after": retry_after}
        resp = JsonResponse(body, status=429)
        resp["X-RateLimit-Remaining"] = "0"
        resp["Retry-After"] = str(retry_after)
        return resp

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest(json.dumps({"error": "invalid_json"}), content_type="application/json")

    message = (data.get("message") or "").strip()
    context = data.get("context")
    patient_id = data.get("patient_id", "")
    consent = data.get("consent", False)

    if not message:
        return HttpResponseBadRequest(json.dumps({"error": "message_required"}), content_type="application/json")
    if not consent:
        return HttpResponseForbidden(json.dumps({"error": "consent_required", "message": "User consent required to process chat"}), content_type="application/json")

    if len(message) > MAX_MESSAGE_LENGTH:
        return HttpResponse(json.dumps({"error": "message_too_long", "max_length": MAX_MESSAGE_LENGTH}), status=413, content_type="application/json")

    # Redact PHI from the message before any logging or external API calls
    redacted_message = redact_phi(message)
    patient_hash = hash_id(patient_id)

    # minimal structured logging
    logger.info("chat_request patient_hash=%s ip=%s message_snippet=%s", patient_hash, client_ip, safe_truncate(redacted_message, 200))

    use_gemini = bool(getattr(settings, "USE_GEMINI", False))

    reply = None
    try:
        if use_gemini:
            try:
                # Send the redacted message to Gemini to avoid sending PHI
                reply_raw = call_gemini_api(redacted_message, context=context)
                reply = safe_truncate(reply_raw, MAX_REPLY_LENGTH)
            except Exception as e:
                logger.exception("Gemini API error, falling back to local generator: %s", e)
                reply = generate_reply_fallback(message, context=context)
        else:
            reply = generate_reply_fallback(message, context=context)
    except Exception:
        logger.exception("Error generating reply")
        reply = "Sorry, I couldn't process that right now. Please try again later."

    # Resolve accurate URLs for booking app (prefer namespaced reverses). If the user is anonymous,
    # return a login redirect URL with a next parameter so clients can redirect the user to login first.
    def maybe_wrap_with_login(request, url: str, login_url: str = None) -> str:
        if request.user and request.user.is_authenticated:
            return url
        login = login_url or getattr(settings, "LOGIN_URL", "/accounts/login/")
        # ensure next is a relative path or absolute path returned by reverse
        try:
            next_path = url
            # quote the next param
            return f"{login}?next={quote(next_path)}"
        except Exception:
            return login

    # Attempt to reverse using the booking namespace first, fall back to plain names or fixed paths.
    def resolve_booking_path(request) -> str:
        candidates = [
            "booking:appointmentBooking",
            "booking:book_appointment",
            "booking:startup",
            "appointmentBooking",
            "book_appointment",
            ""
        ]
        for name in candidates:
            if not name:
                continue
            try:
                return reverse(name)
            except NoReverseMatch:
                continue
        # fallback hard path
        return "/book_appointment/"

    def resolve_doctors_path(request) -> str:
        candidates = ["booking:list_doctors", "list_doctors", "/doctors/"]
        for name in candidates:
            try:
                if name.startswith("/"):
                    return name
                return reverse(name)
            except NoReverseMatch:
                continue
        return "/doctors/"

    def resolve_appointments_path(request) -> str:
        candidates = ["booking:appointment_list", "appointment_list", "/appointments/"]
        for name in candidates:
            try:
                if name.startswith("/"):
                    return name
                return reverse(name)
            except NoReverseMatch:
                continue
        return "/appointments/"

    booking_url = resolve_booking_path(request)
    doctors_url = resolve_doctors_path(request)
    appointments_url = resolve_appointments_path(request)

    # If user not authenticated, wrap links with a login redirect
    booking_url = maybe_wrap_with_login(request, booking_url)
    doctors_url = maybe_wrap_with_login(request, doctors_url)
    appointments_url = maybe_wrap_with_login(request, appointments_url)

    # Basic booking / navigation action detection
    actions = {
        "suggest_booking": False,
        "booking_url": None,
        "suggest_doctors": False,
        "doctors_url": None,
        "suggest_view_appointments": False,
        "appointments_url": None,
    }

    low = message.lower()
    # Booking intent
    if any(k in low for k in ["book", "appointment", "schedule", "reserve"]):
        actions["suggest_booking"] = True
        actions["booking_url"] = booking_url

    # Doctor discovery intent
    if any(k in low for k in ["doctor", "doctors", "specialist", "speciality", "specialty", "physician"]):
        actions["suggest_doctors"] = True
        actions["doctors_url"] = doctors_url

    # View appointments intent
    if any(k in low for k in ["my appointments", "appointments", "upcoming", "view appointments", "bookings"]):
        actions["suggest_view_appointments"] = True
        actions["appointments_url"] = appointments_url

    # If the assistant reply mentions appointments, suggest booking as well
    if "appointment" in (reply or "").lower():
        actions["suggest_booking"] = actions["suggest_booking"] or True
        actions["booking_url"] = actions["booking_url"] or booking_url

    # Save minimal log; ensure we never save raw PHI here. Use redacted_message.
    try:
        ChatLog.objects.create(
            patient_hash=patient_hash,
            message=safe_truncate(redacted_message, 2000),
            reply=safe_truncate(reply, 4000),
        )
    except Exception:
        logger.exception("Could not save chat log")

    logger.info("chat_response patient_hash=%s ip=%s reply_snippet=%s", patient_hash, client_ip, safe_truncate(reply, 200))

    response = JsonResponse({"reply": reply, "actions": actions})
    # Expose remaining quota to client (optional)
    response["X-RateLimit-Remaining"] = str(rl_remaining)
    return response


@require_GET
def chat_page(request):
    """
    Renders a full-page chat UI that behaves like other pages in the app.
    The actual chat API remains POST /chat/ (same module), so the page's JS posts to that endpoint.
    """
    return render(request, "chatbot/chat_page.html", {})