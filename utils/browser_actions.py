"""
BROWSER-NATIVE ACTIONS: PRINT + AI VOICE ASSISTANT
======================================================================
Actions that don't need any external paid service -- they use
capabilities every browser already has:

  - Print Report     -> the browser's native print dialog (window.print()).
  - Voice Assistant   -> the Web Speech API's speechSynthesis, reading
                         text aloud with the best available built-in
                         text-to-speech voice.

All are triggered via a tiny, invisible streamlit.components.v1.html
snippet. The calling page is responsible for only rendering the trigger
on the run right after the button click / condition (see the `*_now`
session_state pattern used in machine_detail.py / alert_center.py, and
the alert-id dedup pattern in utils/voice_alerts.py) so it fires exactly
once per event instead of replaying on every unrelated rerun.

VOICE FUNCTIONS
---------------
  trigger_voice(text)          Immediate single announcement. Cancels
                                anything currently speaking first -- use
                                for one-off manual "Voice Assistant"
                                buttons where the user wants to hear THIS
                                machine right now.

  queue_voice_alerts(texts)    Appends one or more announcements to the
                                speech queue WITHOUT cancelling what's
                                already playing -- use for the automatic
                                critical-alert system so multiple
                                simultaneous critical machines are
                                announced one after another instead of
                                talking over each other (see
                                utils/voice_alerts.py).

  stop_voice()                 Immediately stops current speech AND
                                clears anything queued. Wire this up to
                                every "Stop Voice Alert" button.
----------------------------------------------------------------------
"""

import json
import streamlit.components.v1 as components

# Shared voice-selection logic: prefer a natural/online English voice over
# the low-quality default robotic ones most browsers ship with, when one
# is available. Falls back gracefully to whatever voice the browser has.
_PICK_VOICE_JS = """
function __aegisPickVoice(synth) {
    const voices = synth.getVoices();
    if (!voices || voices.length === 0) return null;
    const byScore = (v) => {
        let score = 0;
        if (/^en/i.test(v.lang)) score += 10;
        if (/natural|online|neural/i.test(v.name)) score += 5;
        if (/google|microsoft/i.test(v.name)) score += 2;
        return score;
    };
    return voices.slice().sort((a, b) => byScore(b) - byScore(a))[0];
}
"""


def trigger_print():
    """Opens the browser's native print dialog for the current page."""
    components.html(
        """
        <script>
            try { window.parent.print(); } catch (e) { window.print(); }
        </script>
        """,
        height=0,
        width=0,
    )


def trigger_voice(text: str):
    """Speaks `text` aloud immediately, cancelling anything currently
    speaking first. Use for one-off manual voice-assistant buttons."""
    safe_text = json.dumps(text)
    components.html(
        f"""
        <script>
        {_PICK_VOICE_JS}
        (function() {{
            try {{
                const synth = window.parent.speechSynthesis || window.speechSynthesis;

                function speakNow() {{
                    synth.cancel();
                    const utter = new SpeechSynthesisUtterance({safe_text});
                    utter.rate = 0.98;
                    utter.pitch = 1.0;
                    const voice = __aegisPickVoice(synth);
                    if (voice) utter.voice = voice;
                    synth.speak(utter);
                }}

                if (synth.getVoices().length === 0) {{
                    synth.onvoiceschanged = speakNow;
                }} else {{
                    speakNow();
                }}
            }} catch (e) {{ console.error("Voice playback failed", e); }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def queue_voice_alerts(texts):
    """Speaks one or more announcements back-to-back WITHOUT cancelling
    anything already playing -- new critical alerts queue up behind the
    current announcement instead of interrupting it (Smart Alert Queue).

    `texts` can be a single string or a list of strings (already ordered
    most-severe-first by the caller)."""
    if isinstance(texts, str):
        texts = [texts]
    if not texts:
        return

    safe_texts = json.dumps(texts)
    components.html(
        f"""
        <script>
        {_PICK_VOICE_JS}
        (function() {{
            try {{
                const synth = window.parent.speechSynthesis || window.speechSynthesis;
                const texts = {safe_texts};

                function speakAll() {{
                    const voice = __aegisPickVoice(synth);
                    texts.forEach(function(t) {{
                        const utter = new SpeechSynthesisUtterance(t);
                        utter.rate = 0.98;
                        utter.pitch = 1.0;
                        if (voice) utter.voice = voice;
                        synth.speak(utter);  // queues -- does not cancel
                    }});
                }}

                if (synth.getVoices().length === 0) {{
                    synth.onvoiceschanged = speakAll;
                }} else {{
                    speakAll();
                }}
            }} catch (e) {{ console.error("Voice queue playback failed", e); }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def stop_voice():
    """Immediately stops current speech and clears the speech queue.
    Wire this up to every "Stop Voice Alert" button."""
    components.html(
        """
        <script>
            try {
                const synth = window.parent.speechSynthesis || window.speechSynthesis;
                synth.cancel();
            } catch (e) { console.error("Failed to stop voice playback", e); }
        </script>
        """,
        height=0,
        width=0,
    )
